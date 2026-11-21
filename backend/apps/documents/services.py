"""CFDI parsing and document ingestion services [E-05] [E-06] [E-24]."""

import os
from datetime import datetime
from decimal import Decimal, InvalidOperation
from uuid import UUID
from zoneinfo import ZoneInfo

from defusedxml import ElementTree as DefusedET
from defusedxml.common import DefusedXmlException
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.files.base import ContentFile
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.accounting.models import FiscalPeriod
from apps.accounting.services import get_or_create_period
from apps.documents.models import Document
from apps.documents.validators import (
    DocumentFileValidationError,
    validate_pdf_upload,
    validate_xml_upload,
)


CFDI_NS_40 = "http://www.sat.gob.mx/cfd/4"
CFDI_NS_33 = "http://www.sat.gob.mx/cfd/3"
TFD_NS = "http://www.sat.gob.mx/TimbreFiscalDigital"
SUPPORTED_CFDI_NAMESPACES = {CFDI_NS_40, CFDI_NS_33}
SUPPORTED_VERSIONS = {"4.0", "3.3"}
SUPPORTED_CFDI_TYPES = {"I", "E", "T", "N", "P"}
MEXICO_CITY = ZoneInfo("America/Mexico_City")

IVATRASLADO = "002"
IEPS = "003"
ISR = "001"


class CfdiParseError(Exception):
    """An XML that cannot be safely interpreted as a CFDI."""

    def __init__(self, code: str, message: str, uuid=None):
        self.code = code
        self.message = message
        self.uuid = uuid
        super().__init__(message)


class DocumentUploadError(Exception):
    """A per-document business-rule failure during ingestion."""

    def __init__(self, code: str, message: str, uuid=None):
        self.code = code
        self.message = message
        self.uuid = uuid
        super().__init__(message)


def _local_name(tag) -> str:
    if not isinstance(tag, str):
        return ""
    return tag.rsplit("}", 1)[-1]


def _namespace(tag) -> str:
    if not isinstance(tag, str) or not tag.startswith("{"):
        return ""
    return tag[1:].split("}", 1)[0]


def _children(element, name):
    if element is None:
        return []
    return [child for child in list(element) if _local_name(child.tag) == name]


def _child(element, name):
    for child in _children(element, name):
        return child
    return None


def _descendants(element, name):
    if element is None:
        return []
    return [node for node in element.iter() if _local_name(node.tag) == name]


def _first_descendant(element, name):
    for node in _descendants(element, name):
        return node
    return None


def _attribute(element, name, default=None):
    if element is None:
        return default
    value = element.attrib.get(name)
    return default if value is None else value


def _decimal(value, default="0.00") -> Decimal:
    if value is None or str(value).strip() == "":
        return Decimal(default)
    try:
        return Decimal(str(value).strip())
    except (InvalidOperation, ValueError):
        raise CfdiParseError(
            "invalid_xml",
            "El XML contiene un importe numérico inválido.",
        ) from None


def _local_datetime(value: datetime) -> datetime:
    if timezone.is_naive(value):
        value = value.replace(tzinfo=MEXICO_CITY)
    return value.astimezone(MEXICO_CITY)


def _parse_fecha(raw_value) -> datetime:
    if not raw_value:
        raise CfdiParseError(
            "invalid_xml",
            "El CFDI no contiene la fecha de emisión.",
        )
    text = str(raw_value).strip()
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        raise CfdiParseError(
            "invalid_xml",
            "La fecha de emisión del CFDI no es válida.",
        ) from None
    return _local_datetime(parsed)


def _tax_payload(node) -> dict:
    return {_local_name(key): value for key, value in node.attrib.items()}


def _taxes_from_impuestos(impuestos, kind: str) -> list[dict]:
    container = _child(impuestos, kind)
    if container is None:
        return []
    return [_tax_payload(node) for node in list(container)]


def _concept_payload(concept) -> dict:
    payload = {_local_name(key): value for key, value in concept.attrib.items()}
    taxes = _child(concept, "Impuestos")
    if taxes is not None:
        payload["Impuestos"] = {
            "Traslados": _taxes_from_impuestos(taxes, "Traslados"),
            "Retenciones": _taxes_from_impuestos(taxes, "Retenciones"),
        }
    return payload


def _gather_taxes(root):
    """Return tax nodes, falling back per category to concept-level ones."""
    impuestos = _child(root, "Impuestos")
    traslados = _taxes_from_impuestos(impuestos, "Traslados")
    retenciones = _taxes_from_impuestos(impuestos, "Retenciones")

    if traslados and retenciones:
        return traslados, retenciones

    concept_traslados = []
    concept_retenciones = []
    for concept in _children(_child(root, "Conceptos"), "Concepto"):
        concept_taxes = _child(concept, "Impuestos")
        concept_traslados.extend(
            _taxes_from_impuestos(concept_taxes, "Traslados")
        )
        concept_retenciones.extend(
            _taxes_from_impuestos(concept_taxes, "Retenciones")
        )
    return (
        traslados or concept_traslados,
        retenciones or concept_retenciones,
    )


def _sum_tax(nodes, tax_code: str) -> Decimal:
    total = Decimal("0.00")
    for node in nodes:
        if str(node.get("Impuesto", "")).strip() != tax_code:
            continue
        importe = node.get("Importe")
        if importe is not None and str(importe).strip() != "":
            total += _decimal(importe)
            continue
        # Some emitters only provide Base/TasaOCuota; calculate the amount.
        base = node.get("Base")
        rate = node.get("TasaOCuota")
        if base is not None and rate is not None:
            total += _decimal(base) * _decimal(rate)
    return total


def _element_payload(element, depth=0) -> dict:
    """Convert a complement element into a JSON-safe, attribute-first dict."""
    payload = {
        "tag": _local_name(element.tag),
        "namespace": _namespace(element.tag),
        "attributes": {
            _local_name(key): str(value)
            for key, value in element.attrib.items()
        },
    }
    text = (element.text or "").strip()
    if text:
        payload["text"] = text
    if depth < 6 and len(element):
        payload["children"] = [
            _element_payload(child, depth + 1) for child in list(element)
        ]
    return payload


def _complementos_payload(root) -> list[dict]:
    complemento = _child(root, "Complemento")
    if complemento is None:
        return []
    return [_element_payload(child) for child in list(complemento)]


def parse_cfdi_xml(source) -> dict:
    """Parse a CFDI 4.0/3.3 XML safely and return normalized fields.

    Raises :class:`CfdiParseError` with ``invalid_xml`` for malformed or
    unsafe XML and ``not_cfdi`` when the root is not a supported CFDI.
    Entity expansion and external entities are rejected by defusedxml.
    """
    if hasattr(source, "read"):
        source = source.read()
    elif isinstance(source, os.PathLike):
        with open(source, "rb") as handle:
            source = handle.read()
    elif isinstance(source, str) and not source.lstrip().startswith("<"):
        # Convenience for internal callers/tests that pass a fixture path.
        if os.path.exists(source):
            with open(source, "rb") as handle:
                source = handle.read()
        else:
            source = source.encode("utf-8")
    elif isinstance(source, str):
        source = source.encode("utf-8")
    if not isinstance(source, (bytes, bytearray)):
        raise CfdiParseError(
            "invalid_xml",
            "El contenido del archivo XML no es válido.",
        )

    try:
        root = DefusedET.fromstring(bytes(source))
    except (
        DefusedET.ParseError,
        DefusedXmlException,
        ValueError,
        TypeError,
    ):
        raise CfdiParseError(
            "invalid_xml",
            "El archivo XML no es válido o está mal formado.",
        ) from None

    if _local_name(root.tag) != "Comprobante":
        raise CfdiParseError(
            "not_cfdi",
            "El archivo no corresponde a un Comprobante CFDI.",
        )

    version = str(_attribute(root, "Version", "")).strip()
    namespace = _namespace(root.tag)
    if (
        version not in SUPPORTED_VERSIONS
        or (
            namespace
            and namespace not in SUPPORTED_CFDI_NAMESPACES
        )
    ):
        raise CfdiParseError(
            "not_cfdi",
            "El archivo no corresponde a un CFDI 4.0 o 3.3 soportado.",
        )

    cfdi_type = str(_attribute(root, "TipoDeComprobante", "I")).strip().upper()
    if cfdi_type not in SUPPORTED_CFDI_TYPES:
        raise CfdiParseError(
            "invalid_xml",
            "El tipo de comprobante del CFDI no es válido.",
        )

    tfd = _first_descendant(root, "TimbreFiscalDigital")
    uuid_raw = _attribute(tfd, "UUID") if tfd is not None else None
    if not uuid_raw:
        raise CfdiParseError(
            "invalid_xml",
            "El CFDI no contiene el UUID del Timbre Fiscal Digital.",
        )
    try:
        uuid = UUID(str(uuid_raw).strip().lower())
    except (ValueError, TypeError, AttributeError):
        raise CfdiParseError(
            "invalid_xml",
            "El UUID del Timbre Fiscal Digital no es válido.",
        ) from None

    emisor = _child(root, "Emisor")
    receptor = _child(root, "Receptor")
    issuer_rfc = str(_attribute(emisor, "Rfc", "")).strip().upper()
    receiver_rfc = str(_attribute(receptor, "Rfc", "")).strip().upper()
    if not issuer_rfc or not receiver_rfc:
        raise CfdiParseError(
            "invalid_xml",
            "El CFDI no contiene el RFC del emisor o del receptor.",
            uuid=uuid,
        )

    issue_date = _parse_fecha(_attribute(root, "Fecha"))
    traslados, retenciones = _gather_taxes(root)
    conceptos = [
        _concept_payload(concept)
        for concept in _children(_child(root, "Conceptos"), "Concepto")
    ]

    currency = str(_attribute(root, "Moneda", "MXN")).strip().upper() or "MXN"
    exchange_rate = _decimal(_attribute(root, "TipoCambio"), "1.0000")

    raw_metadata = {
        "conceptos": conceptos,
        "complementos": _complementos_payload(root),
        "impuestos": {
            "traslados": traslados,
            "retenciones": retenciones,
        },
    }

    return {
        "uuid": uuid,
        "cfdi_version": version,
        "cfdi_type": cfdi_type,
        "issue_date": issue_date,
        "series": str(_attribute(root, "Serie", "")).strip(),
        "folio": str(_attribute(root, "Folio", "")).strip(),
        "issuer_rfc": issuer_rfc,
        "issuer_name": str(_attribute(emisor, "Nombre", "")).strip(),
        "receiver_rfc": receiver_rfc,
        "receiver_name": str(_attribute(receptor, "Nombre", "")).strip(),
        "payment_method": str(_attribute(root, "MetodoPago", "")).strip(),
        "payment_form": str(_attribute(root, "FormaPago", "")).strip(),
        "currency": currency,
        "exchange_rate": exchange_rate,
        "subtotal": _decimal(_attribute(root, "SubTotal")),
        "discount": _decimal(_attribute(root, "Descuento")),
        "iva_transferred": _sum_tax(traslados, IVATRASLADO),
        "ieps_transferred": _sum_tax(traslados, IEPS),
        "iva_retained": _sum_tax(retenciones, IVATRASLADO),
        "isr_retained": _sum_tax(retenciones, ISR),
        "total": _decimal(_attribute(root, "Total")),
        "raw_metadata": raw_metadata,
    }


def infer_direction(parsed: dict, company) -> str:
    """Infer ISSUED/RECEIVED from the company RFC."""
    company_rfc = (company.rfc or "").upper().strip()
    if parsed["issuer_rfc"] == company_rfc:
        return Document.Direction.ISSUED
    if parsed["receiver_rfc"] == company_rfc:
        return Document.Direction.RECEIVED
    raise DocumentUploadError(
        "rfc_mismatch",
        "El RFC del emisor o receptor no corresponde con la empresa activa.",
        uuid=parsed["uuid"],
    )


def _read_upload(uploaded_file) -> bytes:
    try:
        uploaded_file.seek(0)
        return uploaded_file.read()
    except (AttributeError, OSError, ValueError):
        raise DocumentFileValidationError(
            "invalid_file_type",
            "No fue posible leer el archivo cargado.",
        ) from None


def _failure_from_validation(exc: DocumentFileValidationError, filename, uuid=None):
    return {
        "filename": filename,
        "uuid": str(uuid) if uuid else None,
        "code": exc.code,
        "message": exc.message,
    }


def _process_xml(
    uploaded_file,
    company,
    user,
    requested_direction,
    pdf_upload=None,
):
    """Process one XML in its own savepoint. Returns a processed/failed tuple."""
    filename = getattr(uploaded_file, "name", "archivo.xml")
    try:
        validate_xml_upload(uploaded_file)
        content = _read_upload(uploaded_file)
        parsed = parse_cfdi_xml(content)
    except DocumentFileValidationError as exc:
        return None, _failure_from_validation(exc, filename)
    except CfdiParseError as exc:
        return None, {
            "filename": filename,
            "uuid": str(exc.uuid) if exc.uuid else None,
            "code": exc.code,
            "message": exc.message,
        }

    uuid = parsed["uuid"]
    try:
        if requested_direction:
            direction = requested_direction
            company_rfc = (company.rfc or "").upper().strip()
            if company_rfc not in {
                parsed["issuer_rfc"],
                parsed["receiver_rfc"],
            }:
                raise DocumentUploadError(
                    "rfc_mismatch",
                    "El RFC del emisor o receptor no corresponde con la "
                    "empresa activa.",
                    uuid=uuid,
                )
        else:
            direction = infer_direction(parsed, company)

        period = get_or_create_period(company, parsed["issue_date"])
        if period.is_closed:
            raise DocumentUploadError(
                "period_closed",
                f"El periodo fiscal {period.year}-{period.month:02d} "
                "se encuentra cerrado.",
                uuid=uuid,
            )

        try:
            with transaction.atomic():
                if Document.objects.filter(
                    company=company,
                    uuid=uuid,
                ).exists():
                    raise DocumentUploadError(
                        "duplicate_cfdi_uuid",
                        "El UUID ya se encuentra registrado en esta empresa.",
                        uuid=uuid,
                    )

                document = Document(
                    company=company,
                    fiscal_period=period,
                    uuid=uuid,
                    direction=direction,
                    cfdi_type=parsed["cfdi_type"],
                    cfdi_version=parsed["cfdi_version"],
                    original_filename=filename,
                    sat_status=Document.SatStatus.UNVERIFIED,
                    series=parsed["series"],
                    folio=parsed["folio"],
                    issue_date=parsed["issue_date"],
                    issuer_rfc=parsed["issuer_rfc"],
                    issuer_name=parsed["issuer_name"],
                    receiver_rfc=parsed["receiver_rfc"],
                    receiver_name=parsed["receiver_name"],
                    payment_method=parsed["payment_method"],
                    payment_form=parsed["payment_form"],
                    currency=parsed["currency"],
                    exchange_rate=parsed["exchange_rate"],
                    subtotal=parsed["subtotal"],
                    discount=parsed["discount"],
                    iva_transferred=parsed["iva_transferred"],
                    ieps_transferred=parsed["ieps_transferred"],
                    iva_retained=parsed["iva_retained"],
                    isr_retained=parsed["isr_retained"],
                    total=parsed["total"],
                    raw_metadata=parsed["raw_metadata"],
                    uploaded_by=user,
                )
                document.xml_file.save(
                    filename,
                    ContentFile(content),
                    save=False,
                )
                if pdf_upload is not None:
                    pdf_name = getattr(pdf_upload, "name", "respaldo.pdf")
                    pdf_content = _read_upload(pdf_upload)
                    document.pdf_file.save(
                        pdf_name,
                        ContentFile(pdf_content),
                        save=False,
                    )
                document.full_clean(exclude=["xml_file", "pdf_file"])
                document.save()
        except IntegrityError:
            raise DocumentUploadError(
                "duplicate_cfdi_uuid",
                "El UUID ya se encuentra registrado en esta empresa.",
                uuid=uuid,
            ) from None
        except DocumentFileValidationError as exc:
            raise DocumentUploadError(
                exc.code,
                exc.message,
                uuid=uuid,
            ) from None
        except DjangoValidationError as exc:
            raise DocumentUploadError(
                "invalid_xml",
                " ".join(exc.messages)
                or "El CFDI no cumple las reglas de validación.",
                uuid=uuid,
            ) from None
    except DocumentUploadError as exc:
        return None, {
            "filename": filename,
            "uuid": str(exc.uuid) if exc.uuid else None,
            "code": exc.code,
            "message": exc.message,
        }

    return (
        {
            "filename": filename,
            "document_id": document.pk,
            "uuid": str(document.uuid),
            "direction": document.direction,
            "total": format(document.total, ".2f"),
        },
        None,
    )


def process_bulk_upload(files, company, user, direction=None):
    """Ingest a mixed XML/PDF batch with one transaction per file [E-24]."""
    files = list(files or [])
    processed = []
    failed = []
    xml_files = []
    pdfs_by_stem = {}

    for uploaded_file in files:
        filename = getattr(uploaded_file, "name", "")
        extension = os.path.splitext(filename)[1].lower()
        if extension == ".xml":
            xml_files.append(uploaded_file)
        elif extension == ".pdf":
            stem = os.path.splitext(filename)[0].lower()
            pdfs_by_stem.setdefault(stem, []).append(uploaded_file)
        else:
            failed.append(
                {
                    "filename": filename or "archivo",
                    "uuid": None,
                    "code": "invalid_file_type",
                    "message": (
                        "El tipo de archivo no está permitido. "
                        "Solo se aceptan XML y PDF."
                    ),
                }
            )

    for xml_file in xml_files:
        filename = getattr(xml_file, "name", "")
        stem = os.path.splitext(filename)[0].lower()
        pair = None
        pair_failure = None
        if pdfs_by_stem.get(stem):
            pair = pdfs_by_stem[stem].pop(0)
            try:
                validate_pdf_upload(pair)
            except DocumentFileValidationError as exc:
                pair_failure = _failure_from_validation(
                    exc,
                    getattr(pair, "name", "respaldo.pdf"),
                )
                pair = None

        result, failure = _process_xml(
            xml_file,
            company=company,
            user=user,
            requested_direction=direction,
            pdf_upload=pair,
        )
        if result is not None:
            processed.append(result)
        if failure is not None:
            failed.append(failure)
            if pair is not None:
                failed.append(
                    {
                        "filename": getattr(pair, "name", "respaldo.pdf"),
                        "uuid": None,
                        "code": "orphan_pdf",
                        "message": (
                            "El PDF no tiene un XML válido con el mismo "
                            "nombre base dentro del lote."
                        ),
                    }
                )
        if pair_failure is not None:
            failed.append(pair_failure)

    # PDFs without a matching XML are reported, never silently ignored.
    for pdf_files in pdfs_by_stem.values():
        for pdf_file in pdf_files:
            filename = getattr(pdf_file, "name", "respaldo.pdf")
            try:
                validate_pdf_upload(pdf_file)
            except DocumentFileValidationError as exc:
                failed.append(_failure_from_validation(exc, filename))
                continue
            failed.append(
                {
                    "filename": filename,
                    "uuid": None,
                    "code": "orphan_pdf",
                    "message": (
                        "El PDF no tiene un XML con el mismo nombre base "
                        "dentro del lote."
                    ),
                }
            )

    return {
        "summary": {
            "total_received": len(files),
            "processed_count": len(processed),
            "failed_count": len(failed),
        },
        "processed": processed,
        "failed": failed,
    }


def create_manual_document(
    company,
    user,
    *,
    direction,
    issue_date,
    issuer_rfc,
    issuer_name,
    subtotal,
    iva_transferred,
    total,
    pdf_file,
    **extra,
):
    """Create a manual supporting document (cfdi_type M) with its PDF."""
    try:
        validate_pdf_upload(pdf_file)
    except DocumentFileValidationError as exc:
        raise ValidationError(
            { "pdf_file": [exc.message] },
            code=exc.code,
        ) from None

    period = get_or_create_period(company, issue_date)
    if period.is_closed:
        raise DocumentUploadError(
            "period_closed",
            f"El periodo fiscal {period.year}-{period.month:02d} "
            "se encuentra cerrado.",
        )

    content = _read_upload(pdf_file)
    filename = getattr(pdf_file, "name", "respaldo.pdf")
    try:
        with transaction.atomic():
            document = Document(
                company=company,
                fiscal_period=period,
                uuid=None,
                direction=direction,
                cfdi_type=Document.CfdiType.MANUAL,
                cfdi_version="4.0",
                original_filename=filename,
                issue_date=issue_date,
                issuer_rfc=issuer_rfc,
                issuer_name=issuer_name,
                receiver_rfc=company.rfc,
                receiver_name=company.legal_name,
                subtotal=subtotal,
                iva_transferred=iva_transferred,
                total=total,
                raw_metadata={"manual": True},
                uploaded_by=user,
                **extra,
            )
            document.pdf_file.save(filename, ContentFile(content), save=False)
            document.full_clean(exclude=["xml_file", "pdf_file"])
            document.save()
    except DjangoValidationError as exc:
        raise ValidationError({"detail": exc.messages}) from None
    return document


def attach_pdf(document, pdf_file):
    """Attach or replace the PDF of an existing document [E-06]."""
    if document.fiscal_period.is_closed:
        raise DocumentUploadError(
            "period_closed",
            f"El periodo fiscal {document.fiscal_period.year}-"
            f"{document.fiscal_period.month:02d} se encuentra cerrado.",
        )
    try:
        validate_pdf_upload(pdf_file)
    except DocumentFileValidationError as exc:
        raise ValidationError(
            {"pdf_file": [exc.message]},
            code=exc.code,
        ) from None

    content = _read_upload(pdf_file)
    filename = getattr(pdf_file, "name", "respaldo.pdf")
    old_name = document.pdf_file.name if document.pdf_file else ""
    old_storage = document.pdf_file.storage if document.pdf_file else None

    with transaction.atomic():
        document.pdf_file.save(filename, ContentFile(content), save=False)
        document.save(update_fields=["pdf_file", "updated_at"])

    if old_name and old_storage is not None and old_name != document.pdf_file.name:
        try:
            old_storage.delete(old_name)
        except OSError:
            pass
    return document


def unaccounted_documents_count(period: FiscalPeriod) -> int:
    """Documents in the period without an accounting entry (block 5)."""
    return period.documents.filter(is_accounted=False).count()

"""Bank reconciliation services: CSV import, matching and suggestions [E-21]."""

import csv
import hashlib
import io
import re
import uuid
from datetime import date as date_type
from datetime import timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import ErrorDetail, ValidationError

from apps.accounting.models import AccountingEntry, FiscalPeriod
from apps.accounting.services import get_or_create_period
from apps.documents.models import Document
from apps.reconciliation.models import BankMovement


CSV_COLUMNS = ("date", "reference", "description", "deposit", "withdrawal")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
MONEY_QUANTUM = Decimal("0.01")
SUGGESTION_DATE_WINDOW_DAYS = 3


def _error(field, message, code):
    return ValidationError({field: ErrorDetail(message, code=code)})


def _parse_date(raw_value: str):
    if not DATE_RE.match(raw_value):
        raise ValueError("La fecha debe tener el formato AAAA-MM-DD.")
    try:
        return date_type.fromisoformat(raw_value)
    except ValueError:
        raise ValueError("La fecha no es válida.") from None


def _parse_money(raw_value: str):
    normalized = raw_value.strip().replace("$", "").replace(",", "")
    if not normalized:
        return Decimal("0.00")
    try:
        amount = Decimal(normalized)
    except InvalidOperation:
        raise ValueError("El monto debe ser un número decimal válido.") from None
    if not amount.is_finite():
        raise ValueError("El monto debe ser un número decimal válido.")
    return amount.quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)


def _row_hash(movement_date, reference, description, deposit, withdrawal) -> str:
    canonical = "|".join(
        (
            movement_date.isoformat(),
            (reference or "").strip(),
            (description or "").strip(),
            format(deposit, ".2f"),
            format(withdrawal, ".2f"),
        )
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _invalid_row(row_number, code, message):
    return {"row": row_number, "code": code, "message": message}


def _read_csv_rows(file_obj):
    try:
        raw = file_obj.read()
    except AttributeError:
        raw = file_obj

    if isinstance(raw, str):
        text = raw
    else:
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            raise _error(
                "file",
                "El archivo CSV debe estar codificado en UTF-8.",
                "invalid_encoding",
            ) from None

    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise _error(
            "file",
            "El archivo CSV está vacío o no contiene encabezados.",
            "invalid_csv_header",
        )

    headers = [str(header).strip().lower() for header in reader.fieldnames]
    if len(headers) != len(set(headers)):
        raise _error(
            "file",
            "El archivo CSV contiene columnas duplicadas.",
            "invalid_csv_header",
        )
    if set(headers) != set(CSV_COLUMNS) or len(headers) != len(CSV_COLUMNS):
        raise _error(
            "file",
            (
                "El archivo CSV debe contener exactamente las columnas "
                "date,reference,description,deposit,withdrawal."
            ),
            "invalid_csv_header",
        )

    reader.fieldnames = headers
    return reader


def _parse_csv_row(row_number, row):
    if None in row:
        return None, _invalid_row(
            row_number,
            "invalid_columns",
            "La fila contiene más valores que columnas declaradas.",
        )

    values = {
        column: (row.get(column) or "").strip()
        for column in CSV_COLUMNS
    }
    if not any(values.values()):
        return None, None

    try:
        movement_date = _parse_date(values["date"])
    except ValueError as exc:
        return None, _invalid_row(row_number, "invalid_date", str(exc))

    if not values["description"]:
        return None, _invalid_row(
            row_number,
            "missing_description",
            "El concepto (description) es obligatorio.",
        )
    if len(values["description"]) > 255:
        return None, _invalid_row(
            row_number,
            "description_too_long",
            "El concepto no puede exceder 255 caracteres.",
        )
    if len(values["reference"]) > 100:
        return None, _invalid_row(
            row_number,
            "reference_too_long",
            "La referencia no puede exceder 100 caracteres.",
        )

    try:
        deposit = _parse_money(values["deposit"])
        withdrawal = _parse_money(values["withdrawal"])
    except ValueError as exc:
        return None, _invalid_row(row_number, "invalid_amount", str(exc))

    if deposit < Decimal("0.00") or withdrawal < Decimal("0.00"):
        return None, _invalid_row(
            row_number,
            "negative_amount",
            "Los montos de depósito y retiro no pueden ser negativos.",
        )
    if deposit > Decimal("0.00") and withdrawal > Decimal("0.00"):
        return None, _invalid_row(
            row_number,
            "deposit_and_withdrawal",
            "La fila no puede tener depósito y retiro simultáneamente.",
        )
    if deposit == Decimal("0.00") and withdrawal == Decimal("0.00"):
        return None, _invalid_row(
            row_number,
            "zero_amount",
            "La fila debe tener un depósito o un retiro mayor a cero.",
        )

    return (
        {
            "row_number": row_number,
            "date": movement_date,
            "reference": values["reference"],
            "description": values["description"],
            "deposit": deposit,
            "withdrawal": withdrawal,
            "row_hash": _row_hash(
                movement_date,
                values["reference"],
                values["description"],
                deposit,
                withdrawal,
            ),
        },
        None,
    )


def _closed_period(company, movement_date):
    return FiscalPeriod.objects.filter(
        company=company,
        year=movement_date.year,
        month=movement_date.month,
        is_closed=True,
    ).first()


@transaction.atomic
def import_bank_movements(*, company, file_obj):
    """Import a strict CSV file, skipping duplicates and reporting bad rows."""
    reader = _read_csv_rows(file_obj)
    import_batch = uuid.uuid4()
    parsed_rows = []
    invalid_rows = []

    for row in reader:
        parsed, invalid = _parse_csv_row(reader.line_num, row)
        if invalid is not None:
            invalid_rows.append(invalid)
        elif parsed is not None:
            parsed_rows.append(parsed)

    hashes = [row["row_hash"] for row in parsed_rows]
    existing_hashes = set(
        BankMovement.objects.filter(
            company=company,
            row_hash__in=hashes,
        ).values_list("row_hash", flat=True)
    )

    skipped_duplicates = 0
    seen_hashes = set()
    movements = []

    for row in parsed_rows:
        if row["row_hash"] in existing_hashes or row["row_hash"] in seen_hashes:
            skipped_duplicates += 1
            continue

        closed_period = _closed_period(company, row["date"])
        if closed_period is not None:
            invalid_rows.append(
                _invalid_row(
                    row["row_number"],
                    "period_closed",
                    (
                        "El periodo "
                        f"{closed_period.year}-{closed_period.month:02d} "
                        "está cerrado."
                    ),
                )
            )
            continue

        get_or_create_period(company, row["date"])
        movement_data = {
            key: value
            for key, value in row.items()
            if key != "row_number"
        }
        movements.append(
            BankMovement(
                company=company,
                import_batch=import_batch,
                **movement_data,
            )
        )
        seen_hashes.add(row["row_hash"])

    if movements:
        BankMovement.objects.bulk_create(movements)

    invalid_rows.sort(key=lambda item: item["row"])
    return {
        "summary": {
            "imported": len(movements),
            "skipped_duplicates": skipped_duplicates,
            "invalid": len(invalid_rows),
        },
        "invalid_rows": invalid_rows,
        "import_batch": str(import_batch),
    }


def _local_date(value):
    if hasattr(value, "date") and callable(value.date):
        if timezone.is_aware(value):
            return timezone.localtime(value).date()
        return value.date()
    return value


def _movement_amount(movement):
    if movement.deposit > Decimal("0.00"):
        return movement.deposit
    return movement.withdrawal


def _movement_text(movement):
    return f"{movement.reference} {movement.description}".lower()


def _reference_matches(movement, candidate_text):
    reference = (movement.reference or "").strip().lower()
    if not reference:
        return False
    return reference in candidate_text.lower()


def _date_score(movement_date, candidate_date):
    distance = abs((movement_date - candidate_date).days)
    if distance > SUGGESTION_DATE_WINDOW_DAYS:
        return 0
    return max(0, 15 - (distance * 3))


def _document_rfcs(entry):
    rfcs = set()
    for item in entry.items.all():
        document = item.document
        if document is None:
            continue
        if document.issuer_rfc:
            rfcs.add(document.issuer_rfc.upper())
        if document.receiver_rfc:
            rfcs.add(document.receiver_rfc.upper())
    return rfcs


def _entry_candidate(movement, entry):
    amount = _movement_amount(movement)
    entry_amount = (
        entry.total_debit
        if movement.deposit > Decimal("0.00")
        else entry.total_credit
    )
    amount_exact = entry_amount == amount
    reference_match = _reference_matches(
        movement,
        f"{entry.folio} {entry.concept}",
    )
    text = _movement_text(movement)
    rfc_match = any(rfc.lower() in text for rfc in _document_rfcs(entry))
    date_points = _date_score(movement.date, entry.entry_date)

    if not (amount_exact or reference_match or rfc_match):
        return None
    if date_points == 0:
        return None

    score = 0
    if amount_exact:
        score += 50
    if reference_match:
        score += 20
    if rfc_match:
        score += 15
    score += date_points

    return {
        "kind": "entry",
        "id": entry.pk,
        "score": score,
        "folio": entry.folio,
        "concept": entry.concept,
        "entry_type": entry.entry_type,
        "entry_date": entry.entry_date,
        "amount": entry_amount,
        "total_debit": entry.total_debit,
        "total_credit": entry.total_credit,
        "amount_exact": amount_exact,
        "reference_match": reference_match,
        "rfc_match": rfc_match,
        "date_days": abs((movement.date - entry.entry_date).days),
    }


def _document_candidate(movement, document):
    amount = _movement_amount(movement)
    amount_exact = document.total == amount
    text = _movement_text(movement)
    rfc_match = any(
        rfc and rfc.lower() in text
        for rfc in (document.issuer_rfc, document.receiver_rfc)
    )
    reference_match = _reference_matches(
        movement,
        f"{document.uuid or ''} {document.series} {document.folio}",
    )
    document_date = _local_date(document.issue_date)
    date_points = _date_score(movement.date, document_date)

    if not (amount_exact or reference_match or rfc_match):
        return None
    if date_points == 0 and not (reference_match or rfc_match):
        return None

    score = 0
    if amount_exact:
        score += 50
    if reference_match:
        score += 20
    if rfc_match:
        score += 20
    score += date_points

    return {
        "kind": "document",
        "id": document.pk,
        "score": score,
        "uuid": str(document.uuid) if document.uuid else None,
        "series": document.series,
        "folio": document.folio,
        "direction": document.direction,
        "cfdi_type": document.cfdi_type,
        "issue_date": document.issue_date,
        "issuer_rfc": document.issuer_rfc,
        "receiver_rfc": document.receiver_rfc,
        "total": document.total,
        "amount_exact": amount_exact,
        "reference_match": reference_match,
        "rfc_match": rfc_match,
        "date_days": abs((movement.date - document_date).days),
    }


def suggest_matches(movement):
    """Return entry and document candidates ordered by descending score."""
    company = movement.company
    amount = _movement_amount(movement)
    window_start = movement.date - timedelta(days=SUGGESTION_DATE_WINDOW_DAYS)
    window_end = movement.date + timedelta(days=SUGGESTION_DATE_WINDOW_DAYS)

    entries = (
        AccountingEntry.objects.filter(
            company=company,
            status=AccountingEntry.Status.POSTED,
            entry_date__range=(window_start, window_end),
        )
        .select_related("fiscal_period")
        .prefetch_related("items__document")
        .order_by("entry_date", "pk")
    )
    documents = (
        Document.objects.filter(company=company)
        .filter(
            Q(issue_date__date__range=(window_start, window_end))
            | Q(total=amount)
        )
        .select_related("fiscal_period")
        .order_by("issue_date", "pk")[:200]
    )

    candidates = []
    for entry in entries:
        candidate = _entry_candidate(movement, entry)
        if candidate is not None:
            candidates.append(candidate)

    for document in documents:
        candidate = _document_candidate(movement, document)
        if candidate is not None:
            candidates.append(candidate)

    candidates.sort(key=lambda item: (-item["score"], item["kind"], item["id"]))
    return candidates


def _ensure_movement_period_open(movement):
    period = FiscalPeriod.objects.filter(
        company=movement.company,
        year=movement.date.year,
        month=movement.date.month,
    ).first()
    if period is not None and period.is_closed:
        raise ValidationError(
            {
                "fiscal_period": ErrorDetail(
                    (
                        "El periodo "
                        f"{period.year}-{period.month:02d} está cerrado."
                    ),
                    code="period_closed",
                )
            }
        )


@transaction.atomic
def match_movement(movement, *, entry_id=None, document_id=None):
    """Link a bank movement to an entry and/or document and mark it reconciled."""
    locked = (
        BankMovement.objects.select_for_update()
        .select_related("company")
        .get(pk=movement.pk)
    )
    _ensure_movement_period_open(locked)

    if entry_id is None and document_id is None:
        raise _error(
            "match",
            "Debe indicar entry_id o document_id para conciliar el movimiento.",
            "invalid_match_target",
        )
    if entry_id is not None and document_id is not None:
        raise _error(
            "match",
            "Solo puede indicar entry_id o document_id, no ambos.",
            "invalid_match_target",
        )

    if entry_id is not None:
        entry = AccountingEntry.objects.filter(
            company=locked.company,
            pk=entry_id,
        ).first()
        if entry is None:
            raise _error(
                "entry_id",
                "La póliza no existe en la empresa activa.",
                "invalid_entry",
            )
        if entry.status != AccountingEntry.Status.POSTED:
            raise _error(
                "entry_id",
                "Solo se pueden conciliar pólizas contabilizadas (POSTED).",
                "entry_not_posted",
            )
        locked.entry = entry

    if document_id is not None:
        document = Document.objects.filter(
            company=locked.company,
            pk=document_id,
        ).first()
        if document is None:
            raise _error(
                "document_id",
                "El documento no existe en la empresa activa.",
                "invalid_document",
            )
        locked.document = document

    locked.status = BankMovement.Status.RECONCILED
    locked.save(
        update_fields=[
            "entry",
            "document",
            "status",
            "updated_at",
        ]
    )
    return locked


@transaction.atomic
def unmatch_movement(movement):
    """Clear the links and return the movement to PENDING."""
    locked = (
        BankMovement.objects.select_for_update()
        .select_related("company")
        .get(pk=movement.pk)
    )
    _ensure_movement_period_open(locked)

    locked.entry = None
    locked.document = None
    locked.status = BankMovement.Status.PENDING
    locked.save(
        update_fields=[
            "entry",
            "document",
            "status",
            "updated_at",
        ]
    )
    return locked

"""Accounting services shared by the API and management commands."""

import json
from datetime import date as date_type
from datetime import datetime
from pathlib import Path

from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ErrorDetail, ValidationError

from apps.accounting.models import (
    AccountCatalog,
    AccountingEntry,
    AccountingEntryItem,
    FiscalPeriod,
)
from apps.core.models import AuditLog
from apps.documents.models import Document
from apps.tenants.models import Company


MASTER_CATALOG_FIXTURE = Path(settings.BASE_DIR) / "fixtures" / "sat_master_catalog.json"
JUSTIFICATION_MIN_LENGTH = 15
FOLIO_PREFIXES = {
    AccountingEntry.EntryType.INCOME: "ING",
    AccountingEntry.EntryType.EXPENSE: "EGR",
    AccountingEntry.EntryType.JOURNAL: "DIA",
}


def _load_master_catalog() -> list[dict]:
    with MASTER_CATALOG_FIXTURE.open(encoding="utf-8") as fixture:
        return json.load(fixture)


@transaction.atomic
def clone_master_sat_catalog(company) -> list[AccountCatalog]:
    """Clone the master SAT chart of accounts into ``company``.

    The operation is idempotent: accounts that already exist for the company
    are left untouched, and the remaining rows are inserted with
    ``bulk_create`` in hierarchy order.  It is safe to call inside the company
    creation transaction (nested atomic blocks use savepoints).
    """

    source = _load_master_catalog()
    source_by_code = {item["code"]: item for item in source}
    if len(source_by_code) != len(source):
        raise ValueError("El catálogo maestro SAT contiene códigos duplicados.")

    for item in source:
        parent_code = item.get("parent_code")
        if parent_code and parent_code not in source_by_code:
            raise ValueError(
                f"La cuenta {item['code']} referencia un padre inexistente: {parent_code}."
            )

    resolved = {
        account.code: account
        for account in AccountCatalog.objects.filter(company=company)
    }
    pending = [item for item in source if item["code"] not in resolved]
    created: list[AccountCatalog] = []

    while pending:
        batch = []
        next_pending = []
        for item in pending:
            parent_code = item.get("parent_code")
            if parent_code and parent_code not in resolved:
                next_pending.append(item)
                continue
            batch.append(item)

        if not batch:
            raise ValueError(
                "No fue posible resolver la jerarquía del catálogo maestro SAT."
            )

        objects = [
            AccountCatalog(
                company=company,
                parent=resolved.get(item.get("parent_code")),
                code=item["code"],
                sat_group_code=item["sat_group_code"],
                name=item["name"],
                account_type=item["account_type"],
                nature=item["nature"],
                is_selectable=item.get("is_selectable", True),
                is_active=item.get("is_active", True),
            )
            for item in batch
        ]
        AccountCatalog.objects.bulk_create(objects, batch_size=500)

        for account in objects:
            resolved[account.code] = account
            created.append(account)

        pending = next_pending

    return created


def _coerce_local_date(value) -> date_type:
    """Return the local calendar date for a date/datetime/ISO string."""
    if isinstance(value, datetime):
        if timezone.is_aware(value):
            value = timezone.localtime(value)
        return value.date()
    if isinstance(value, date_type):
        return value
    if isinstance(value, str):
        try:
            return date_type.fromisoformat(value)
        except ValueError:
            pass
    raise ValueError("La fecha proporcionada no es válida.")


def get_or_create_period(company, date) -> FiscalPeriod:
    """Resolve the monthly fiscal period from a local date [E-14]."""
    local_date = _coerce_local_date(date)
    period, _created = FiscalPeriod.objects.get_or_create(
        company=company,
        year=local_date.year,
        month=local_date.month,
    )
    return period


def _count_draft_entries(period) -> int:
    return period.entries.filter(
        status=AccountingEntry.Status.DRAFT
    ).count()


def _as_decimal(value, field="items") -> Decimal:
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except Exception:
        raise ValidationError(
            {
                field: ErrorDetail(
                    "El monto debe ser un número decimal válido.",
                    code="invalid_line_amounts",
                )
            }
        ) from None


def _raise_period_closed(period: FiscalPeriod):
    raise ValidationError(
        {
            "fiscal_period": ErrorDetail(
                f"El periodo {period.year}-{period.month:02d} está cerrado.",
                code="period_closed",
            )
        }
    )


def _ensure_period_open(period: FiscalPeriod):
    if period is not None and period.is_closed:
        _raise_period_closed(period)


def _locked_period(period: FiscalPeriod) -> FiscalPeriod:
    return FiscalPeriod.objects.select_for_update().get(pk=period.pk)


def _resolve_entry_period(
    company,
    entry_date,
    fiscal_period=None,
) -> FiscalPeriod:
    """Resolve and validate the period for an entry date [E-14]."""
    if fiscal_period is None:
        period = get_or_create_period(company, entry_date)
    else:
        if fiscal_period.company_id != company.pk:
            raise ValidationError(
                {
                    "fiscal_period": ErrorDetail(
                        "El periodo fiscal no pertenece a la empresa "
                        "seleccionada.",
                        code="invalid_fiscal_period",
                    )
                }
            )
        period = fiscal_period

    if (
        entry_date.year != period.year
        or entry_date.month != period.month
    ):
        raise ValidationError(
            {
                "entry_date": ErrorDetail(
                    "La fecha de la póliza debe caer dentro del periodo fiscal "
                    f"{period.year}-{period.month:02d}.",
                    code="entry_date_out_of_period",
                )
            }
        )

    _ensure_period_open(period)
    return period


@transaction.atomic
def next_folio(company, entry_type, year) -> str:
    """Return the next sequential folio for a company/type/year [E-15].

    The company row is locked with ``select_for_update`` so two concurrent
    transactions cannot request the same folio.
    """
    try:
        prefix = FOLIO_PREFIXES[entry_type]
    except KeyError:
        raise ValidationError(
            {
                "entry_type": ErrorDetail(
                    "El tipo de póliza no es válido.",
                    code="invalid",
                )
            }
        ) from None

    Company.objects.select_for_update().filter(pk=company.pk).first()

    last_folio = (
        AccountingEntry.objects.select_for_update()
        .filter(
            company=company,
            entry_type=entry_type,
            entry_date__year=year,
        )
        .order_by("-folio")
        .values_list("folio", flat=True)
        .first()
    )

    sequence = 0
    if last_folio:
        try:
            sequence = int(str(last_folio).rsplit("-", 1)[-1])
        except (TypeError, ValueError):
            sequence = 0
    return f"{prefix}-{year}-{sequence + 1:04d}"


def _validate_item_payload(item_data: dict, company) -> None:
    account = item_data.get("account")
    if account is not None:
        if account.company_id != company.pk:
            raise ValidationError(
                {
                    "account": ErrorDetail(
                        "La cuenta contable no pertenece a la empresa de la "
                        "póliza.",
                        code="non_selectable_account",
                    )
                }
            )
        if not account.is_selectable:
            raise ValidationError(
                {
                    "account": ErrorDetail(
                        f"La cuenta {account.code} es acumulativa y no acepta "
                        "movimientos directos.",
                        code="non_selectable_account",
                    )
                }
            )

    document = item_data.get("document")
    if document is not None and document.company_id != company.pk:
        raise ValidationError(
            {
                "document": ErrorDetail(
                    "El documento no pertenece a la empresa de la póliza.",
                    code="invalid_document",
                )
            }
        )

    debit = _as_decimal(item_data.get("debit", Decimal("0.00")), "debit")
    credit = _as_decimal(item_data.get("credit", Decimal("0.00")), "credit")
    if debit < Decimal("0.00") or credit < Decimal("0.00"):
        raise ValidationError(
            {
                "debit": ErrorDetail(
                    "Los cargos y abonos no pueden ser negativos.",
                    code="invalid_line_amounts",
                )
            }
        )
    if (debit > Decimal("0.00") and credit > Decimal("0.00")) or (
        debit == Decimal("0.00") and credit == Decimal("0.00")
    ):
        raise ValidationError(
            {
                "debit": ErrorDetail(
                    "Cada renglón debe tener un monto mayor a cero en Cargo o "
                    "Abono, pero no en ambos.",
                    code="invalid_line_amounts",
                )
            }
        )


def _create_items(entry: AccountingEntry, items_data) -> None:
    for index, raw_item in enumerate(items_data, start=1):
        item_data = dict(raw_item)
        item_data.pop("line_number", None)
        item_data["debit"] = _as_decimal(
            item_data.get("debit", Decimal("0.00")),
            "debit",
        )
        item_data["credit"] = _as_decimal(
            item_data.get("credit", Decimal("0.00")),
            "credit",
        )
        _validate_item_payload(item_data, entry.company)

        item = AccountingEntryItem(
            company=entry.company,
            entry=entry,
            line_number=index,
            **item_data,
        )
        try:
            item.full_clean()
        except DjangoValidationError as exc:
            raise ValidationError(
                {
                    "items": ErrorDetail(
                        " ".join(exc.messages),
                        code="invalid_line_amounts",
                    )
                }
            ) from None
        item.save()


def _sync_documents_accounted(company, document_ids) -> None:
    """Keep Document.is_accounted in sync with existing entry items."""
    document_ids = {pk for pk in document_ids if pk is not None}
    if not document_ids:
        return

    documents = Document.objects.filter(
        company=company,
        pk__in=document_ids,
    )
    for document in documents:
        referenced = AccountingEntryItem.objects.filter(
            company=company,
            document=document,
        ).exists()
        if document.is_accounted != referenced:
            document.is_accounted = referenced
            document.save(update_fields=["is_accounted", "updated_at"])


def _document_ids_for_entry(entry: AccountingEntry) -> set[int]:
    return set(
        entry.items.filter(document__isnull=False).values_list(
            "document_id",
            flat=True,
        )
    )


def _entry_snapshot(entry: AccountingEntry) -> dict:
    """JSON-safe immutable snapshot stored in AuditLog.previous_state."""
    period = entry.fiscal_period
    return {
        "id": entry.pk,
        "company_id": entry.company_id,
        "fiscal_period": period.pk,
        "period_label": f"{period.year}-{period.month:02d}",
        "entry_type": entry.entry_type,
        "folio": entry.folio,
        "entry_date": entry.entry_date.isoformat(),
        "concept": entry.concept,
        "status": entry.status,
        "total_debit": format(entry.total_debit, ".2f"),
        "total_credit": format(entry.total_credit, ".2f"),
        "items": [
            {
                "id": item.pk,
                "line_number": item.line_number,
                "account": item.account_id,
                "account_code": item.account.code,
                "account_name": item.account.name,
                "document": item.document_id,
                "description": item.description,
                "debit": format(item.debit, ".2f"),
                "credit": format(item.credit, ".2f"),
            }
            for item in entry.items.select_related("account").all()
        ],
    }


@transaction.atomic
def create_accounting_entry(
    *,
    company,
    fiscal_period=None,
    user,
    header_data,
    items_data,
):
    """Create a balanced entry and its items atomically (02 §4)."""
    header = dict(header_data)
    header.pop("fiscal_period", None)
    entry_date = header.get("entry_date")
    entry_type = header.get("entry_type")
    if entry_date is None or entry_type is None:
        raise ValidationError(
            {
                "detail": ErrorDetail(
                    "La fecha y el tipo de póliza son obligatorios.",
                    code="validation_error",
                )
            }
        )

    period = _resolve_entry_period(company, entry_date, fiscal_period)
    period = _locked_period(period)
    _ensure_period_open(period)

    entry = AccountingEntry(
        company=company,
        fiscal_period=period,
        created_by=user,
        folio=next_folio(company, entry_type, entry_date.year),
        **header,
    )
    try:
        entry.full_clean()
    except DjangoValidationError as exc:
        raise ValidationError(
            {
                "detail": ErrorDetail(
                    " ".join(exc.messages),
                    code="validation_error",
                )
            }
        ) from None
    entry.save()

    _create_items(entry, items_data)

    try:
        entry.validate_double_entry()
    except DjangoValidationError as exc:
        raise ValidationError(
            {
                "items": ErrorDetail(
                    " ".join(exc.messages),
                    code="unbalanced_entry",
                )
            }
        ) from None
    entry.save(update_fields=["total_debit", "total_credit", "updated_at"])

    _sync_documents_accounted(company, _document_ids_for_entry(entry))
    return entry


@transaction.atomic
def update_accounting_entry(
    entry: AccountingEntry,
    *,
    user,
    header_data,
    items_data=None,
):
    """Replace an entry atomically, validating original and target periods."""
    locked = (
        AccountingEntry.objects.select_for_update()
        .select_related("fiscal_period", "company")
        .get(pk=entry.pk)
    )

    original_period = _locked_period(locked.fiscal_period)
    _ensure_period_open(original_period)

    header = dict(header_data)
    period_payload = header.pop("fiscal_period", None)
    new_entry_date = header.get("entry_date", locked.entry_date)
    new_entry_type = header.get("entry_type", locked.entry_type)

    if period_payload is not None:
        new_period = _resolve_entry_period(
            locked.company,
            new_entry_date,
            period_payload,
        )
    else:
        new_period = get_or_create_period(locked.company, new_entry_date)
        if (
            new_entry_date.year != new_period.year
            or new_entry_date.month != new_period.month
        ):
            raise ValidationError(
                {
                    "entry_date": ErrorDetail(
                        "La fecha de la póliza debe caer dentro del periodo "
                        "fiscal.",
                        code="entry_date_out_of_period",
                    )
                }
            )
    new_period = _locked_period(new_period)
    _ensure_period_open(new_period)

    old_document_ids = _document_ids_for_entry(locked)
    old_year = locked.entry_date.year
    old_entry_type = locked.entry_type

    for field, value in header.items():
        setattr(locked, field, value)
    locked.fiscal_period = new_period

    if new_entry_type != old_entry_type or new_entry_date.year != old_year:
        locked.folio = next_folio(
            locked.company,
            new_entry_type,
            new_entry_date.year,
        )

    try:
        locked.full_clean()
    except DjangoValidationError as exc:
        raise ValidationError(
            {
                "detail": ErrorDetail(
                    " ".join(exc.messages),
                    code="validation_error",
                )
            }
        ) from None
    locked.save()

    if items_data is not None:
        locked.items.all().delete()
        _create_items(locked, items_data)

    try:
        locked.validate_double_entry()
    except DjangoValidationError as exc:
        raise ValidationError(
            {
                "items": ErrorDetail(
                    " ".join(exc.messages),
                    code="unbalanced_entry",
                )
            }
        ) from None
    locked.save(update_fields=["total_debit", "total_credit", "updated_at"])

    _sync_documents_accounted(
        locked.company,
        old_document_ids | _document_ids_for_entry(locked),
    )
    return locked


@transaction.atomic
def delete_accounting_entry(
    entry: AccountingEntry,
    *,
    user,
    ip_address=None,
) -> None:
    """Delete an entry, audit its snapshot and release linked documents."""
    locked = (
        AccountingEntry.objects.select_for_update()
        .select_related("fiscal_period", "company")
        .get(pk=entry.pk)
    )
    period = _locked_period(locked.fiscal_period)
    _ensure_period_open(period)

    snapshot = _entry_snapshot(locked)
    document_ids = _document_ids_for_entry(locked)
    target_id = str(locked.pk)
    company = locked.company

    locked.delete()

    AuditLog.objects.create(
        company=company,
        user=user,
        action=AuditLog.ActionType.ENTRY_DELETED,
        target_model="AccountingEntry",
        target_id=target_id,
        previous_state=snapshot,
        new_state={},
        ip_address=ip_address,
    )

    _sync_documents_accounted(company, document_ids)


def _period_state(period: FiscalPeriod) -> dict:
    return {
        "id": period.pk,
        "year": period.year,
        "month": period.month,
        "is_closed": period.is_closed,
        "closed_at": period.closed_at.isoformat() if period.closed_at else None,
        "closed_by_id": period.closed_by_id,
    }


@transaction.atomic
def close_period(period: FiscalPeriod, user, ip_address=None) -> FiscalPeriod:
    """Close a fiscal period and record the immutable audit event."""
    locked = FiscalPeriod.objects.select_for_update().get(pk=period.pk)

    if locked.is_closed:
        raise ValidationError(
            {
                "detail": ErrorDetail(
                    "El periodo fiscal ya se encuentra cerrado.",
                    code="period_already_closed",
                )
            }
        )

    draft_entries = _count_draft_entries(locked)
    if draft_entries:
        raise ValidationError(
            {
                "detail": ErrorDetail(
                    (
                        "Existen pólizas en borrador dentro del periodo. "
                        "Concluya o elimine las pólizas antes de cerrar."
                    ),
                    code="draft_entries_pending",
                )
            }
        )

    previous_state = _period_state(locked)
    locked.is_closed = True
    locked.closed_at = timezone.now()
    locked.closed_by = user
    locked.save(update_fields=["is_closed", "closed_at", "closed_by", "updated_at"])

    AuditLog.objects.create(
        company=locked.company,
        user=user,
        action=AuditLog.ActionType.PERIOD_CLOSED,
        target_model="FiscalPeriod",
        target_id=str(locked.pk),
        previous_state=previous_state,
        new_state=_period_state(locked),
        ip_address=ip_address,
    )
    return locked


@transaction.atomic
def reopen_period(
    period: FiscalPeriod,
    user,
    justification: str,
    ip_address=None,
) -> FiscalPeriod:
    """Reopen a closed period with a mandatory justification and audit trail."""
    justification = (justification or "").strip()
    if len(justification) < JUSTIFICATION_MIN_LENGTH:
        raise ValidationError(
            {
                "justification": ErrorDetail(
                    "La justificación es obligatoria y debe tener al menos "
                    f"{JUSTIFICATION_MIN_LENGTH} caracteres.",
                    code="min_length",
                )
            }
        )

    locked = FiscalPeriod.objects.select_for_update().get(pk=period.pk)
    if not locked.is_closed:
        raise ValidationError(
            {
                "detail": ErrorDetail(
                    "El periodo fiscal ya se encuentra abierto.",
                    code="period_already_open",
                )
            }
        )

    previous_state = _period_state(locked)
    locked.is_closed = False
    locked.closed_at = None
    locked.closed_by = None
    locked.save(update_fields=["is_closed", "closed_at", "closed_by", "updated_at"])

    AuditLog.objects.create(
        company=locked.company,
        user=user,
        action=AuditLog.ActionType.PERIOD_REOPENED,
        target_model="FiscalPeriod",
        target_id=str(locked.pk),
        justification=justification,
        previous_state=previous_state,
        new_state=_period_state(locked),
        ip_address=ip_address,
    )
    return locked

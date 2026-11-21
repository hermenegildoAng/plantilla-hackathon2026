"""Accounting services shared by the API and management commands."""

import json
from datetime import date as date_type
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ErrorDetail, ValidationError

from apps.accounting.models import AccountCatalog, FiscalPeriod
from apps.core.models import AuditLog


MASTER_CATALOG_FIXTURE = Path(settings.BASE_DIR) / "fixtures" / "sat_master_catalog.json"
JUSTIFICATION_MIN_LENGTH = 15


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
    # TODO(bloque 5): count AccountingEntry rows in DRAFT status for the period.
    return 0


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

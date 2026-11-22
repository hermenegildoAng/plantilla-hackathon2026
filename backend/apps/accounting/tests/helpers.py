"""Shared fixtures for accounting entry tests."""

from datetime import date, datetime
from decimal import Decimal
from uuid import uuid4

from django.utils import timezone

from apps.accounting.models import AccountCatalog, FiscalPeriod
from apps.accounting.services import (
    clone_master_sat_catalog,
    get_or_create_period,
)
from apps.documents.models import Document


def prepare_company(company):
    clone_master_sat_catalog(company)
    return company


def account_for(company, code):
    return AccountCatalog.objects.get(company=company, code=code)


def period_for(company, year=2026, month=5):
    return get_or_create_period(company, date(year, month, 1))


def make_document(
    company,
    period,
    user,
    *,
    direction=Document.Direction.ISSUED,
    total="1160.00",
    subtotal="1000.00",
    iva_transferred="160.00",
):
    issue_day = date(period.year, period.month, 15)
    return Document.objects.create(
        company=company,
        fiscal_period=period,
        uuid=uuid4(),
        direction=direction,
        cfdi_type=(
            Document.CfdiType.INGRESO
            if direction == Document.Direction.ISSUED
            else Document.CfdiType.EGRESO
        ),
        issue_date=timezone.make_aware(
            datetime.combine(issue_day, datetime.min.time())
        ),
        issuer_rfc=company.rfc,
        issuer_name=company.legal_name,
        receiver_rfc="SDA210515XY1",
        receiver_name="Receptor de Prueba",
        subtotal=Decimal(subtotal),
        iva_transferred=Decimal(iva_transferred),
        total=Decimal(total),
        uploaded_by=user,
    )


def entry_payload(
    period,
    debit_account,
    credit_account,
    *,
    amount="1000.00",
    entry_type="INCOME",
    status="POSTED",
    entry_date=None,
    concept="Póliza de prueba",
    document=None,
    include_period=True,
):
    payload = {
        "entry_type": entry_type,
        "entry_date": (entry_date or date(period.year, period.month, 15)).isoformat(),
        "concept": concept,
        "status": status,
        "items": [
            {
                "account": debit_account.pk,
                "debit": amount,
                "credit": "0.00",
                "description": "Cargo de prueba",
                **({"document": document.pk} if document else {}),
            },
            {
                "account": credit_account.pk,
                "debit": "0.00",
                "credit": amount,
                "description": "Abono de prueba",
                **({"document": document.pk} if document else {}),
            },
        ],
    }
    if include_period:
        payload["fiscal_period"] = period.pk
    return payload


def period_label(period: FiscalPeriod) -> str:
    return f"{period.year}-{period.month:02d}"

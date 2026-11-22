"""Shared helpers for reconciliation and report tests."""

import hashlib
import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal

from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from apps.accounting.models import AccountCatalog
from apps.accounting.services import (
    clone_master_sat_catalog,
    create_accounting_entry,
    get_or_create_period,
)
from apps.documents.models import Document
from apps.reconciliation.models import BankMovement


CSV_HEADER = "date,reference,description,deposit,withdrawal\n"


def prepare_company(company):
    clone_master_sat_catalog(company)
    return company


def account_for(company, code):
    return AccountCatalog.objects.get(company=company, code=code)


def period_for(company, year=2026, month=5):
    return get_or_create_period(company, date(year, month, 1))


def make_entry(
    company,
    user,
    period,
    *,
    amount="1000.00",
    entry_type="INCOME",
    entry_date=None,
    concept="Póliza de prueba",
    document=None,
):
    amount = Decimal(amount)
    entry_date = entry_date or date(period.year, period.month, 15)
    if entry_type == "EXPENSE":
        items = [
            {
                "account": account_for(company, "601.38"),
                "description": "Gasto",
                "debit": amount,
                "credit": Decimal("0.00"),
            },
            {
                "account": account_for(company, "102.01.001"),
                "description": "Pago bancario",
                "debit": Decimal("0.00"),
                "credit": amount,
            },
        ]
    else:
        items = [
            {
                "account": account_for(company, "105.01"),
                "description": "Cobro",
                "debit": amount,
                "credit": Decimal("0.00"),
            },
            {
                "account": account_for(company, "401.01"),
                "description": "Ingreso",
                "debit": Decimal("0.00"),
                "credit": amount,
            },
        ]
    if document is not None:
        for item in items:
            item["document"] = document

    return create_accounting_entry(
        company=company,
        fiscal_period=period,
        user=user,
        header_data={
            "entry_type": entry_type,
            "status": "POSTED",
            "entry_date": entry_date,
            "concept": concept,
        },
        items_data=items,
    )


def make_document(
    company,
    period,
    user,
    *,
    direction=Document.Direction.ISSUED,
    total="1160.00",
    subtotal="1000.00",
    iva_transferred="160.00",
    iva_retained="0.00",
    isr_retained="0.00",
    issuer_rfc=None,
    receiver_rfc=None,
    issue_date=None,
):
    issue_date = issue_date or date(period.year, period.month, 15)
    return Document.objects.create(
        company=company,
        fiscal_period=period,
        uuid=uuid.uuid4(),
        direction=direction,
        cfdi_type=(
            Document.CfdiType.INGRESO
            if direction == Document.Direction.ISSUED
            else Document.CfdiType.EGRESO
        ),
        issue_date=timezone.make_aware(
            datetime.combine(issue_date, datetime.min.time())
        ),
        issuer_rfc=issuer_rfc or (
            company.rfc
            if direction == Document.Direction.ISSUED
            else "SDA210515XY1"
        ),
        issuer_name="Emisor de Prueba",
        receiver_rfc=receiver_rfc or (
            "SDA210515XY1"
            if direction == Document.Direction.ISSUED
            else company.rfc
        ),
        receiver_name="Receptor de Prueba",
        subtotal=Decimal(subtotal),
        iva_transferred=Decimal(iva_transferred),
        iva_retained=Decimal(iva_retained),
        isr_retained=Decimal(isr_retained),
        total=Decimal(total),
        uploaded_by=user,
    )


def make_movement(
    company,
    *,
    movement_date=None,
    amount="1000.00",
    kind="deposit",
    reference="REF-001",
    description="Movimiento de prueba",
):
    amount = Decimal(amount)
    movement_date = movement_date or date(2026, 5, 15)
    deposit = amount if kind == "deposit" else Decimal("0.00")
    withdrawal = amount if kind == "withdrawal" else Decimal("0.00")
    row_hash = hashlib.sha256(
        f"{company.pk}-{uuid.uuid4()}".encode("utf-8")
    ).hexdigest()
    return BankMovement.objects.create(
        company=company,
        date=movement_date,
        reference=reference,
        description=description,
        deposit=deposit,
        withdrawal=withdrawal,
        row_hash=row_hash,
    )


def csv_upload(rows, header=CSV_HEADER):
    lines = [header]
    for row in rows:
        if isinstance(row, str):
            lines.append(row)
        else:
            lines.append(
                ",".join(str(value) for value in row)
            )
    content = "\n".join(line.rstrip("\n") for line in lines) + "\n"
    return SimpleUploadedFile(
        "movimientos.csv",
        content.encode("utf-8"),
        content_type="text/csv",
    )


def headers(company):
    return {"HTTP_X_COMPANY_ID": str(company.pk)}


def date_in_period(period, day=15):
    return date(period.year, period.month, day)


def next_day(value, days=1):
    return value + timedelta(days=days)

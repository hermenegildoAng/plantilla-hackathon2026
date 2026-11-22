from datetime import date
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.exceptions import ValidationError

from apps.accounting.models import AccountingEntry, AccountingEntryItem
from apps.accounting.services import (
    close_period,
    create_accounting_entry,
    delete_accounting_entry,
    next_folio,
    update_accounting_entry,
)
from apps.accounting.tests.helpers import (
    account_for,
    make_document,
    period_for,
    prepare_company,
)


pytestmark = pytest.mark.django_db


def _items(company, *, debit="1000.00", credit="1000.00"):
    return [
        {
            "account": account_for(company, "105.01"),
            "description": "Cargo",
            "debit": Decimal(debit),
            "credit": Decimal("0.00"),
        },
        {
            "account": account_for(company, "401.01"),
            "description": "Abono",
            "debit": Decimal("0.00"),
            "credit": Decimal(credit),
        },
    ]


def _create_entry(company, user, period, *, entry_type="INCOME"):
    return create_accounting_entry(
        company=company,
        fiscal_period=period,
        user=user,
        header_data={
            "entry_type": entry_type,
            "status": AccountingEntry.Status.POSTED,
            "entry_date": date(period.year, period.month, 15),
            "concept": "Póliza de servicio",
        },
        items_data=_items(company),
    )


def test_next_folio_sequences_by_type_and_year(make_user, make_company):
    user = make_user()
    company = prepare_company(make_company())
    period = period_for(company)

    assert next_folio(company, "INCOME", 2026) == "ING-2026-0001"
    first = _create_entry(company, user, period, entry_type="INCOME")
    assert first.folio == "ING-2026-0001"
    assert next_folio(company, "INCOME", 2026) == "ING-2026-0002"

    expense = _create_entry(company, user, period, entry_type="EXPENSE")
    assert expense.folio == "EGR-2026-0001"

    journal = _create_entry(company, user, period, entry_type="JOURNAL")
    assert journal.folio == "DIA-2026-0001"


def test_item_company_must_match_entry_company(
    make_user,
    make_company,
):
    user = make_user()
    company = prepare_company(make_company())
    other_company = prepare_company(make_company())
    period = period_for(company)
    entry = _create_entry(company, user, period)

    item = AccountingEntryItem(
        company=other_company,
        entry=entry,
        account=account_for(company, "105.01"),
        line_number=1,
        debit=Decimal("10.00"),
        credit=Decimal("0.00"),
    )

    with pytest.raises(DjangoValidationError) as exc_info:
        item.full_clean()

    assert "empresa de la póliza" in str(exc_info.value)


def test_zero_sum_model_validation_rejects_entry(make_user, make_company):
    user = make_user()
    company = prepare_company(make_company())
    period = period_for(company)
    entry = _create_entry(company, user, period)
    entry.items.all().delete()

    AccountingEntryItem.objects.bulk_create(
        [
            AccountingEntryItem(
                company=company,
                entry=entry,
                account=account_for(company, "105.01"),
                line_number=1,
                debit=Decimal("0.00"),
                credit=Decimal("0.00"),
            ),
            AccountingEntryItem(
                company=company,
                entry=entry,
                account=account_for(company, "401.01"),
                line_number=2,
                debit=Decimal("0.00"),
                credit=Decimal("0.00"),
            ),
        ]
    )

    with pytest.raises(DjangoValidationError) as exc_info:
        entry.validate_double_entry()

    assert "mayor a cero" in str(exc_info.value)


def test_update_rolls_back_line_replacement_on_error(
    make_user,
    make_company,
):
    user = make_user()
    company = prepare_company(make_company())
    period = period_for(company)
    entry = _create_entry(company, user, period)

    with pytest.raises(ValidationError) as exc_info:
        update_accounting_entry(
            entry,
            user=user,
            header_data={"concept": "No debe persistir"},
            items_data=[
                {
                    "account": account_for(company, "105.01"),
                    "debit": Decimal("100.00"),
                    "credit": Decimal("0.00"),
                }
            ],
        )

    assert exc_info.value.detail["items"].code == "unbalanced_entry"
    entry.refresh_from_db()
    assert entry.concept == "Póliza de servicio"
    assert entry.items.count() == 2
    assert entry.total_debit == Decimal("1000.00")
    assert entry.total_credit == Decimal("1000.00")


def test_close_period_rejects_draft_entries(make_user, make_company):
    user = make_user()
    company = prepare_company(make_company())
    period = period_for(company)
    draft = create_accounting_entry(
        company=company,
        fiscal_period=period,
        user=user,
        header_data={
            "entry_type": "JOURNAL",
            "status": AccountingEntry.Status.DRAFT,
            "entry_date": date(2026, 5, 15),
            "concept": "Borrador pendiente",
        },
        items_data=_items(company),
    )

    with pytest.raises(ValidationError) as exc_info:
        close_period(period, user=user)

    assert (
        exc_info.value.detail["detail"].code == "draft_entries_pending"
    )
    period.refresh_from_db()
    assert period.is_closed is False

    delete_accounting_entry(draft, user=user)
    closed = close_period(period, user=user)
    assert closed.is_closed is True


def test_delete_releases_document_only_without_other_references(
    make_user,
    make_company,
):
    user = make_user()
    company = prepare_company(make_company())
    period = period_for(company)
    document = make_document(company, period, user)

    items_with_document = [
        {
            "account": account_for(company, "105.01"),
            "document": document,
            "debit": Decimal("1000.00"),
            "credit": Decimal("0.00"),
        },
        {
            "account": account_for(company, "401.01"),
            "document": document,
            "debit": Decimal("0.00"),
            "credit": Decimal("1000.00"),
        },
    ]
    first = create_accounting_entry(
        company=company,
        fiscal_period=period,
        user=user,
        header_data={
            "entry_type": "INCOME",
            "entry_date": date(2026, 5, 15),
            "concept": "Primera póliza",
        },
        items_data=items_with_document,
    )
    second = create_accounting_entry(
        company=company,
        fiscal_period=period,
        user=user,
        header_data={
            "entry_type": "INCOME",
            "entry_date": date(2026, 5, 15),
            "concept": "Segunda póliza",
        },
        items_data=items_with_document,
    )

    document.refresh_from_db()
    assert document.is_accounted is True

    delete_accounting_entry(first, user=user)
    document.refresh_from_db()
    assert document.is_accounted is True

    delete_accounting_entry(second, user=user)
    document.refresh_from_db()
    assert document.is_accounted is False

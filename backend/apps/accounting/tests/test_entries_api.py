from datetime import date
from decimal import Decimal

import pytest

from apps.accounting.models import AccountingEntry
from apps.accounting.services import create_accounting_entry, close_period
from apps.accounting.tests.helpers import (
    account_for,
    entry_payload,
    make_document,
    period_for,
    prepare_company,
)
from apps.authentication.models import CompanyMembership
from apps.core.models import AuditLog


pytestmark = pytest.mark.django_db

ENTRIES_URL = "/api/v1/entries/"


def headers(company):
    return {"HTTP_X_COMPANY_ID": str(company.id)}


def detail_url(entry):
    return f"{ENTRIES_URL}{entry.pk}/"


def make_entry(company, user, period, *, entry_type="INCOME", status="POSTED",
               concept="Póliza de prueba", entry_date=None):
    return create_accounting_entry(
        company=company,
        fiscal_period=period,
        user=user,
        header_data={
            "entry_type": entry_type,
            "status": status,
            "entry_date": entry_date or date(period.year, period.month, 15),
            "concept": concept,
        },
        items_data=[
            {
                "account": account_for(company, "105.01"),
                "description": "Cargo",
                "debit": Decimal("1000.00"),
                "credit": Decimal("0.00"),
            },
            {
                "account": account_for(company, "401.01"),
                "description": "Abono",
                "debit": Decimal("0.00"),
                "credit": Decimal("1000.00"),
            },
        ],
    )


def test_create_balanced_entry_returns_strings_and_marks_document(
    tenant_user,
):
    user, company, _membership, client = tenant_user()
    prepare_company(company)
    period = period_for(company)
    document = make_document(company, period, user)

    response = client.post(
        ENTRIES_URL,
        entry_payload(
            period,
            account_for(company, "105.01"),
            account_for(company, "401.01"),
            document=document,
        ),
        format="json",
        **headers(company),
    )

    assert response.status_code == 201
    data = response.json()["data"]
    assert data["folio"] == "ING-2026-0001"
    assert data["period_label"] == "2026-05"
    assert data["total_debit"] == "1000.00"
    assert data["total_credit"] == "1000.00"
    assert [item["line_number"] for item in data["items"]] == [1, 2]
    assert data["items"][0]["debit"] == "1000.00"
    assert data["items"][0]["account_code"] == "105.01"

    document.refresh_from_db()
    assert document.is_accounted is True


def test_unbalanced_entry_is_rejected(tenant_user):
    user, company, _membership, client = tenant_user()
    prepare_company(company)
    period = period_for(company)
    payload = entry_payload(
        period,
        account_for(company, "105.01"),
        account_for(company, "401.01"),
    )
    payload["items"][1]["credit"] = "900.00"

    response = client.post(
        ENTRIES_URL,
        payload,
        format="json",
        **headers(company),
    )

    assert response.status_code == 400
    assert response.json()["errors"][0]["code"] == "unbalanced_entry"
    assert AccountingEntry.objects.filter(company=company).count() == 0


def test_zero_sum_entry_is_rejected(tenant_user):
    _user, company, _membership, client = tenant_user()
    prepare_company(company)
    period = period_for(company)
    payload = entry_payload(
        period,
        account_for(company, "105.01"),
        account_for(company, "401.01"),
    )
    payload["items"][0]["debit"] = "0.00"
    payload["items"][1]["credit"] = "0.00"

    response = client.post(
        ENTRIES_URL,
        payload,
        format="json",
        **headers(company),
    )

    assert response.status_code == 400
    assert response.json()["errors"][0]["code"] in {
        "invalid_line_amounts",
        "unbalanced_entry",
    }


def test_line_with_debit_and_credit_is_rejected(tenant_user):
    _user, company, _membership, client = tenant_user()
    prepare_company(company)
    period = period_for(company)
    payload = entry_payload(
        period,
        account_for(company, "105.01"),
        account_for(company, "401.01"),
    )
    payload["items"][0]["credit"] = "10.00"
    payload["items"][1]["credit"] = "1000.00"

    response = client.post(
        ENTRIES_URL,
        payload,
        format="json",
        **headers(company),
    )

    assert response.status_code == 400
    assert response.json()["errors"][0]["code"] == "invalid_line_amounts"


def test_cumulative_account_is_rejected(tenant_user):
    _user, company, _membership, client = tenant_user()
    prepare_company(company)
    period = period_for(company)
    payload = entry_payload(
        period,
        account_for(company, "105"),
        account_for(company, "401.01"),
    )

    response = client.post(
        ENTRIES_URL,
        payload,
        format="json",
        **headers(company),
    )

    assert response.status_code == 400
    assert response.json()["errors"][0]["code"] == "non_selectable_account"


def test_account_from_another_company_is_rejected(
    tenant_user,
    make_company,
):
    _user, company, _membership, client = tenant_user()
    prepare_company(company)
    foreign_company = make_company()
    prepare_company(foreign_company)
    period = period_for(company)
    payload = entry_payload(
        period,
        account_for(foreign_company, "105.01"),
        account_for(company, "401.01"),
    )

    response = client.post(
        ENTRIES_URL,
        payload,
        format="json",
        **headers(company),
    )

    assert response.status_code == 400
    assert response.json()["errors"][0]["code"] == "non_selectable_account"


def test_entry_date_outside_period_is_rejected(tenant_user):
    _user, company, _membership, client = tenant_user()
    prepare_company(company)
    period = period_for(company)
    payload = entry_payload(
        period,
        account_for(company, "105.01"),
        account_for(company, "401.01"),
        entry_date=date(2026, 6, 2),
    )

    response = client.post(
        ENTRIES_URL,
        payload,
        format="json",
        **headers(company),
    )

    assert response.status_code == 400
    assert response.json()["errors"][0]["code"] == "entry_date_out_of_period"


def test_create_in_closed_period_is_rejected(tenant_user):
    user, company, _membership, client = tenant_user()
    prepare_company(company)
    period = period_for(company)
    close_period(period, user=user)

    response = client.post(
        ENTRIES_URL,
        entry_payload(
            period,
            account_for(company, "105.01"),
            account_for(company, "401.01"),
        ),
        format="json",
        **headers(company),
    )

    assert response.status_code == 400
    assert response.json()["errors"][0]["code"] == "period_closed"


def test_update_with_closed_original_period_is_rejected(tenant_user):
    user, company, _membership, client = tenant_user()
    prepare_company(company)
    period = period_for(company)
    entry = make_entry(company, user, period)
    close_period(period, user=user)

    response = client.put(
        detail_url(entry),
        entry_payload(
            period,
            account_for(company, "105.01"),
            account_for(company, "401.01"),
        ),
        format="json",
        **headers(company),
    )

    assert response.status_code == 400
    assert response.json()["errors"][0]["code"] == "period_closed"
    assert AccountingEntry.objects.get(pk=entry.pk).items.count() == 2


def test_update_to_closed_period_is_rejected(tenant_user):
    user, company, _membership, client = tenant_user()
    prepare_company(company)
    may = period_for(company, 2026, 5)
    june = period_for(company, 2026, 6)
    close_period(june, user=user)
    entry = make_entry(company, user, may)

    response = client.put(
        detail_url(entry),
        entry_payload(
            june,
            account_for(company, "105.01"),
            account_for(company, "401.01"),
            entry_date=date(2026, 6, 15),
        ),
        format="json",
        **headers(company),
    )

    assert response.status_code == 400
    assert response.json()["errors"][0]["code"] == "period_closed"
    entry.refresh_from_db()
    assert entry.fiscal_period_id == may.pk


def test_delete_in_closed_period_is_rejected(tenant_user):
    user, company, _membership, client = tenant_user()
    prepare_company(company)
    period = period_for(company)
    entry = make_entry(company, user, period)
    close_period(period, user=user)

    response = client.delete(detail_url(entry), **headers(company))

    assert response.status_code == 400
    assert response.json()["errors"][0]["code"] == "period_closed"
    assert AccountingEntry.objects.filter(pk=entry.pk).exists()


def test_folios_are_consecutive(tenant_user):
    user, company, _membership, client = tenant_user()
    prepare_company(company)
    period = period_for(company)
    accounts = (
        account_for(company, "105.01"),
        account_for(company, "401.01"),
    )

    first = make_entry(company, user, period, concept="Primera")
    second = make_entry(company, user, period, concept="Segunda")

    assert first.folio == "ING-2026-0001"
    assert second.folio == "ING-2026-0002"
    assert accounts[0].company_id == company.pk


def test_is_accounted_only_released_when_no_other_entry_references_document(
    tenant_user,
):
    user, company, _membership, client = tenant_user()
    prepare_company(company)
    period = period_for(company)
    document = make_document(company, period, user)

    first = client.post(
        ENTRIES_URL,
        entry_payload(
            period,
            account_for(company, "105.01"),
            account_for(company, "401.01"),
            document=document,
        ),
        format="json",
        **headers(company),
    ).json()["data"]
    second = client.post(
        ENTRIES_URL,
        entry_payload(
            period,
            account_for(company, "105.01"),
            account_for(company, "401.01"),
            document=document,
            concept="Segunda póliza",
        ),
        format="json",
        **headers(company),
    ).json()["data"]

    document.refresh_from_db()
    assert document.is_accounted is True

    assert client.delete(
        f"{ENTRIES_URL}{first['id']}/",
        **headers(company),
    ).status_code == 204
    document.refresh_from_db()
    assert document.is_accounted is True

    assert client.delete(
        f"{ENTRIES_URL}{second['id']}/",
        **headers(company),
    ).status_code == 204
    document.refresh_from_db()
    assert document.is_accounted is False


def test_delete_creates_audit_log_snapshot(tenant_user):
    user, company, _membership, client = tenant_user()
    prepare_company(company)
    period = period_for(company)
    entry = make_entry(company, user, period, concept="Póliza a eliminar")

    response = client.delete(
        detail_url(entry),
        REMOTE_ADDR="198.51.100.30",
        **headers(company),
    )

    assert response.status_code == 204
    assert not AccountingEntry.objects.filter(pk=entry.pk).exists()

    log = AuditLog.objects.get(
        company=company,
        action=AuditLog.ActionType.ENTRY_DELETED,
    )
    assert log.user == user
    assert log.target_model == "AccountingEntry"
    assert log.target_id == str(entry.pk)
    assert log.ip_address == "198.51.100.30"
    assert log.previous_state["folio"] == entry.folio
    assert log.previous_state["concept"] == "Póliza a eliminar"
    assert log.previous_state["total_debit"] == "1000.00"
    assert len(log.previous_state["items"]) == 2
    assert log.new_state == {}


@pytest.mark.parametrize(
    "role,expected_status",
    [
        (CompanyMembership.Role.PARTNER, 200),
        (CompanyMembership.Role.ACCOUNTANT, 200),
        (CompanyMembership.Role.AUDITOR, 200),
        (CompanyMembership.Role.CLIENT, 403),
    ],
)
def test_entries_list_permission_matrix(role, expected_status, tenant_user):
    _user, company, _membership, client = tenant_user(role=role)
    prepare_company(company)

    response = client.get(ENTRIES_URL, **headers(company))

    assert response.status_code == expected_status


@pytest.mark.parametrize(
    "role,expected_status",
    [
        (CompanyMembership.Role.PARTNER, 201),
        (CompanyMembership.Role.ACCOUNTANT, 201),
        (CompanyMembership.Role.AUDITOR, 403),
        (CompanyMembership.Role.CLIENT, 403),
    ],
)
def test_entries_create_permission_matrix(role, expected_status, tenant_user):
    _user, company, _membership, client = tenant_user(role=role)
    prepare_company(company)
    period = period_for(company)

    response = client.post(
        ENTRIES_URL,
        entry_payload(
            period,
            account_for(company, "105.01"),
            account_for(company, "401.01"),
        ),
        format="json",
        **headers(company),
    )

    assert response.status_code == expected_status


@pytest.mark.parametrize(
    "role,expected_status",
    [
        (CompanyMembership.Role.PARTNER, 204),
        (CompanyMembership.Role.ACCOUNTANT, 403),
        (CompanyMembership.Role.AUDITOR, 403),
        (CompanyMembership.Role.CLIENT, 403),
    ],
)
def test_only_partner_can_delete_entries(role, expected_status, tenant_user):
    user, company, _membership, client = tenant_user(role=role)
    prepare_company(company)
    period = period_for(company)
    entry = make_entry(company, user, period)

    response = client.delete(detail_url(entry), **headers(company))

    assert response.status_code == expected_status
    if expected_status == 204:
        assert not AccountingEntry.objects.filter(pk=entry.pk).exists()
    else:
        assert AccountingEntry.objects.filter(pk=entry.pk).exists()


def test_entry_filters(tenant_user):
    user, company, _membership, client = tenant_user()
    prepare_company(company)
    period = period_for(company)

    income = make_entry(
        company,
        user,
        period,
        entry_type="INCOME",
        concept="Venta de servicios norte",
        entry_date=date(2026, 5, 10),
    )
    expense = make_entry(
        company,
        user,
        period,
        entry_type="EXPENSE",
        concept="Gasto de papelería sur",
        entry_date=date(2026, 5, 15),
    )
    draft = make_entry(
        company,
        user,
        period,
        entry_type="JOURNAL",
        status="DRAFT",
        concept="Ajuste contable",
        entry_date=date(2026, 5, 20),
    )

    response = client.get(
        ENTRIES_URL,
        {"entry_type": "INCOME"},
        **headers(company),
    )
    assert [item["id"] for item in response.json()["data"]["results"]] == [
        income.pk
    ]

    response = client.get(
        ENTRIES_URL,
        {"status": "DRAFT"},
        **headers(company),
    )
    assert [item["id"] for item in response.json()["data"]["results"]] == [
        draft.pk
    ]

    response = client.get(
        ENTRIES_URL,
        {"date_from": "2026-05-14", "date_to": "2026-05-19"},
        **headers(company),
    )
    assert [item["id"] for item in response.json()["data"]["results"]] == [
        expense.pk
    ]

    response = client.get(
        ENTRIES_URL,
        {"search": "venta"},
        **headers(company),
    )
    assert [item["id"] for item in response.json()["data"]["results"]] == [
        income.pk
    ]

    response = client.get(
        ENTRIES_URL,
        {"fiscal_period": period.pk},
        **headers(company),
    )
    assert response.json()["data"]["count"] == 3


def test_fiscal_period_is_optional_and_resolved_from_date(tenant_user):
    _user, company, _membership, client = tenant_user()
    prepare_company(company)
    period = period_for(company)

    response = client.post(
        ENTRIES_URL,
        entry_payload(
            period,
            account_for(company, "105.01"),
            account_for(company, "401.01"),
            include_period=False,
        ),
        format="json",
        **headers(company),
    )

    assert response.status_code == 201
    data = response.json()["data"]
    assert data["fiscal_period"] == period.pk
    assert data["period_label"] == "2026-05"


def test_period_entries_count_reflects_entries(tenant_user):
    user, company, _membership, client = tenant_user()
    prepare_company(company)
    period = period_for(company)
    make_entry(company, user, period, concept="Primera")
    make_entry(company, user, period, concept="Segunda")

    response = client.get("/api/v1/periods/", **headers(company))

    assert response.status_code == 200
    results = response.json()["data"]["results"]
    assert results[0]["entries_count"] == 2


def test_update_replaces_lines_atomically(tenant_user):
    user, company, _membership, client = tenant_user()
    prepare_company(company)
    period = period_for(company)
    entry = make_entry(company, user, period)

    payload = {
        "fiscal_period": period.pk,
        "entry_type": "JOURNAL",
        "entry_date": "2026-05-16",
        "concept": "Póliza actualizada",
        "status": "POSTED",
        "items": [
            {
                "account": account_for(company, "105.01").pk,
                "debit": "1500.00",
                "credit": "0.00",
            },
            {
                "account": account_for(company, "401.01").pk,
                "debit": "0.00",
                "credit": "1000.00",
            },
            {
                "account": account_for(company, "207.01").pk,
                "debit": "0.00",
                "credit": "500.00",
            },
        ],
    }

    response = client.put(
        detail_url(entry),
        payload,
        format="json",
        **headers(company),
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["concept"] == "Póliza actualizada"
    assert data["total_debit"] == "1500.00"
    assert data["total_credit"] == "1500.00"
    assert len(data["items"]) == 3
    assert [item["line_number"] for item in data["items"]] == [1, 2, 3]
    entry.refresh_from_db()
    assert entry.items.count() == 3

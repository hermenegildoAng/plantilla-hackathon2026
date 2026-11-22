from decimal import Decimal

import pytest

from apps.authentication.models import CompanyMembership
from apps.reconciliation.tests.helpers import (
    headers,
    make_document,
    make_entry,
    period_for,
    prepare_company,
)


pytestmark = pytest.mark.django_db

TRIAL_BALANCE_URL = "/api/v1/reports/trial-balance/"
EXECUTIVE_SUMMARY_URL = "/api/v1/reports/executive-summary/"


def _account_row(payload, code):
    return next(
        row for row in payload["accounts"] if row["code"] == code
    )


def test_trial_balance_balances_debits_and_credits(tenant_user):
    user, company, _membership, client = tenant_user()
    prepare_company(company)
    period = period_for(company, 2026, 5)
    make_entry(company, user, period, amount="500.00")

    response = client.get(
        f"{TRIAL_BALANCE_URL}?period={period.pk}",
        **headers(company),
    )

    assert response.status_code == 200
    data = response.json()["data"]
    total_debit = sum(Decimal(row["total_debit"]) for row in data["accounts"])
    total_credit = sum(Decimal(row["total_credit"]) for row in data["accounts"])
    assert total_debit == total_credit == Decimal("500.00")
    assert data["totals"]["difference"] == "0.00"
    assert data["totals"]["total_debit"] == "500.00"
    assert data["totals"]["total_credit"] == "500.00"


def test_trial_balance_opening_accumulates_previous_periods_of_exercise(
    tenant_user,
):
    user, company, _membership, client = tenant_user()
    prepare_company(company)

    december_2025 = period_for(company, 2025, 12)
    march = period_for(company, 2026, 3)
    april = period_for(company, 2026, 4)
    may = period_for(company, 2026, 5)

    make_entry(company, user, december_2025, amount="999.00")
    make_entry(company, user, march, amount="200.00")
    make_entry(company, user, april, amount="1000.00")
    make_entry(company, user, may, amount="500.00")

    response = client.get(
        f"{TRIAL_BALANCE_URL}?period={may.pk}",
        **headers(company),
    )

    data = response.json()["data"]
    clientes = _account_row(data, "105.01")
    ventas = _account_row(data, "401.01")

    # December 2025 belongs to a different fiscal year and is excluded.
    assert clientes["opening_balance"] == "1200.00"
    assert clientes["total_debit"] == "500.00"
    assert clientes["total_credit"] == "0.00"
    assert clientes["closing_balance"] == "1700.00"

    assert ventas["opening_balance"] == "1200.00"
    assert ventas["total_debit"] == "0.00"
    assert ventas["total_credit"] == "500.00"
    assert ventas["closing_balance"] == "1700.00"


def test_trial_balance_ignores_draft_entries(tenant_user):
    user, company, _membership, client = tenant_user()
    prepare_company(company)
    period = period_for(company)
    entry = make_entry(company, user, period, amount="500.00")
    entry.status = "DRAFT"
    entry.save(update_fields=["status"])

    response = client.get(
        f"{TRIAL_BALANCE_URL}?period={period.pk}",
        **headers(company),
    )

    data = response.json()["data"]
    assert data["accounts"] == []
    assert data["totals"]["difference"] == "0.00"


def test_executive_summary_full_for_partner(tenant_user):
    user, company, _membership, client = tenant_user()
    prepare_company(company)
    period = period_for(company)
    make_document(
        company,
        period,
        user,
        direction="ISSUED",
        total="1160.00",
        subtotal="1000.00",
        iva_transferred="160.00",
    )
    make_document(
        company,
        period,
        user,
        direction="RECEIVED",
        total="580.00",
        subtotal="500.00",
        iva_transferred="80.00",
        iva_retained="20.00",
        isr_retained="10.00",
    )

    response = client.get(
        f"{EXECUTIVE_SUMMARY_URL}?period={period.pk}",
        **headers(company),
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["iva_transferred"] == "160.00"
    assert data["iva_creditable"] == "80.00"
    assert data["iva_retained"] == "20.00"
    assert data["isr_retained"] == "10.00"
    assert data["income_total"] == "1160.00"
    assert data["expense_total"] == "580.00"


def test_executive_summary_is_reduced_for_client(
    tenant_user,
    make_user,
    make_membership,
    authenticate,
    api_client,
):
    user, company, _membership, _client = tenant_user()
    prepare_company(company)
    period = period_for(company)
    make_document(company, period, user, total="1160.00", iva_transferred="160.00")
    make_document(
        company,
        period,
        user,
        direction="RECEIVED",
        total="580.00",
        iva_transferred="80.00",
        iva_retained="20.00",
        isr_retained="10.00",
    )

    client_user = make_user()
    make_membership(
        client_user,
        company,
        role=CompanyMembership.Role.CLIENT,
    )
    authenticate(api_client, client_user)

    response = api_client.get(
        f"{EXECUTIVE_SUMMARY_URL}?period={period.pk}",
        **headers(company),
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["income_total"] == "1160.00"
    assert data["expense_total"] == "580.00"
    assert data["iva_transferred"] == "160.00"
    assert data["iva_creditable"] == "80.00"
    assert "iva_retained" not in data
    assert "isr_retained" not in data


def test_client_cannot_read_trial_balance(
    tenant_user,
    make_user,
    make_membership,
    authenticate,
    api_client,
):
    user, company, _membership, _client = tenant_user()
    prepare_company(company)
    period = period_for(company)
    make_entry(company, user, period)

    client_user = make_user()
    make_membership(
        client_user,
        company,
        role=CompanyMembership.Role.CLIENT,
    )
    authenticate(api_client, client_user)

    response = api_client.get(
        f"{TRIAL_BALANCE_URL}?period={period.pk}",
        **headers(company),
    )

    assert response.status_code == 403


def test_period_parameter_is_validated(tenant_user, make_company):
    _user, company, _membership, client = tenant_user()
    prepare_company(company)

    missing = client.get(TRIAL_BALANCE_URL, **headers(company))
    invalid = client.get(
        f"{TRIAL_BALANCE_URL}?period=abc",
        **headers(company),
    )

    other_company = make_company()
    foreign_period = period_for(other_company, 2026, 5)
    foreign = client.get(
        f"{TRIAL_BALANCE_URL}?period={foreign_period.pk}",
        **headers(company),
    )

    assert missing.status_code == 400
    assert missing.json()["errors"][0]["code"] == "required"
    assert invalid.status_code == 400
    assert invalid.json()["errors"][0]["code"] == "invalid"
    assert foreign.status_code == 404
    assert foreign.json()["errors"][0]["code"] == "not_found"


def test_reports_require_tenant_header(tenant_user):
    _user, _company, _membership, client = tenant_user()

    response = client.get(f"{TRIAL_BALANCE_URL}?period=1")

    assert response.status_code == 400
    assert (
        response.json()["errors"][0]["code"]
        == "missing_or_invalid_tenant_header"
    )

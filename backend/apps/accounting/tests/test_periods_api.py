from datetime import date

import pytest

from apps.accounting.models import FiscalPeriod
from apps.accounting.services import get_or_create_period
from apps.authentication.models import CompanyMembership
from apps.core.models import AuditLog


pytestmark = pytest.mark.django_db

PERIODS_URL = "/api/v1/periods/"


def headers(company):
    return {"HTTP_X_COMPANY_ID": str(company.id)}


def close_url(period):
    return f"{PERIODS_URL}{period.id}/close/"


def reopen_url(period):
    return f"{PERIODS_URL}{period.id}/reopen/"


@pytest.mark.parametrize(
    "role,expected_status",
    [
        (CompanyMembership.Role.PARTNER, 200),
        (CompanyMembership.Role.ACCOUNTANT, 200),
        (CompanyMembership.Role.AUDITOR, 200),
        (CompanyMembership.Role.CLIENT, 403),
    ],
)
def test_periods_list_permission_matrix(role, expected_status, tenant_user):
    _user, company, _membership, client = tenant_user(role=role)
    get_or_create_period(company, date(2026, 5, 1))

    response = client.get(PERIODS_URL, **headers(company))

    assert response.status_code == expected_status
    if expected_status == 200:
        data = response.json()["data"]["results"]
        assert len(data) == 1
        assert data[0]["year"] == 2026
        assert data[0]["month"] == 5
        assert data[0]["entries_count"] == 0
        assert data[0]["unaccounted_documents_count"] == 0


def test_partner_closes_period_and_audit_log_records_ip(tenant_user):
    user, company, _membership, client = tenant_user()
    period = get_or_create_period(company, date(2026, 5, 1))

    response = client.post(
        close_url(period),
        format="json",
        REMOTE_ADDR="198.51.100.7",
        **headers(company),
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["is_closed"] is True
    assert data["closed_by_name"] == user.full_name

    period.refresh_from_db()
    assert period.is_closed is True
    assert period.closed_by == user

    log = AuditLog.objects.get(
        company=company,
        action=AuditLog.ActionType.PERIOD_CLOSED,
    )
    assert log.ip_address == "198.51.100.7"


@pytest.mark.parametrize(
    "role",
    [
        CompanyMembership.Role.ACCOUNTANT,
        CompanyMembership.Role.AUDITOR,
        CompanyMembership.Role.CLIENT,
    ],
)
def test_only_partner_can_close_period(role, tenant_user):
    _user, company, _membership, client = tenant_user(role=role)
    period = get_or_create_period(company, date(2026, 5, 1))

    response = client.post(close_url(period), format="json", **headers(company))

    assert response.status_code == 403
    period.refresh_from_db()
    assert period.is_closed is False


def test_closing_an_already_closed_period_returns_400(tenant_user):
    _user, company, _membership, client = tenant_user()
    period = get_or_create_period(company, date(2026, 5, 1))
    client.post(close_url(period), format="json", **headers(company))

    response = client.post(close_url(period), format="json", **headers(company))

    assert response.status_code == 400
    assert response.json()["errors"][0]["code"] == "period_already_closed"


def test_reopen_without_justification_returns_400(tenant_user):
    _user, company, _membership, client = tenant_user()
    period = get_or_create_period(company, date(2026, 5, 1))
    client.post(close_url(period), format="json", **headers(company))

    response = client.post(
        reopen_url(period),
        {},
        format="json",
        **headers(company),
    )

    assert response.status_code == 400
    assert response.json()["errors"][0]["field"] == "justification"
    assert not AuditLog.objects.filter(
        company=company,
        action=AuditLog.ActionType.PERIOD_REOPENED,
    ).exists()


def test_reopen_with_short_justification_returns_400(tenant_user):
    _user, company, _membership, client = tenant_user()
    period = get_or_create_period(company, date(2026, 5, 1))
    client.post(close_url(period), format="json", **headers(company))

    response = client.post(
        reopen_url(period),
        {"justification": "muy corta"},
        format="json",
        **headers(company),
    )

    assert response.status_code == 400
    assert response.json()["errors"][0]["field"] == "justification"
    assert "15" in response.json()["errors"][0]["message"]


def test_reopen_with_justification_creates_audit_log(tenant_user):
    user, company, _membership, client = tenant_user()
    period = get_or_create_period(company, date(2026, 5, 1))
    client.post(close_url(period), format="json", **headers(company))

    justification = "Reclasificación de factura complementaria de pago."
    response = client.post(
        reopen_url(period),
        {"justification": justification},
        format="json",
        REMOTE_ADDR="198.51.100.8",
        **headers(company),
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["is_closed"] is False
    assert data["closed_at"] is None
    assert data["closed_by_name"] is None

    period.refresh_from_db()
    assert period.is_closed is False

    log = AuditLog.objects.get(
        company=company,
        action=AuditLog.ActionType.PERIOD_REOPENED,
    )
    assert log.user == user
    assert log.justification == justification
    assert log.ip_address == "198.51.100.8"
    assert log.previous_state["is_closed"] is True
    assert log.new_state["is_closed"] is False


def test_periods_are_isolated_by_tenant(tenant_user, make_company):
    _user, company, _membership, client = tenant_user()
    get_or_create_period(company, date(2026, 5, 1))
    foreign_company = make_company()
    foreign_period = get_or_create_period(foreign_company, date(2026, 6, 1))

    response = client.get(PERIODS_URL, **headers(company))
    assert response.status_code == 200
    results = response.json()["data"]["results"]
    assert len(results) == 1
    assert results[0]["month"] == 5

    foreign_close = client.post(
        close_url(foreign_period),
        format="json",
        **headers(company),
    )
    assert foreign_close.status_code == 404
    assert FiscalPeriod.objects.get(pk=foreign_period.pk).is_closed is False

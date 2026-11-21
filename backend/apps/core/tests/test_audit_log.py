import pytest
from django.core.exceptions import ValidationError

from apps.authentication.models import CompanyMembership
from apps.core.models import AuditLog


pytestmark = pytest.mark.django_db

AUDIT_URL = "/api/v1/audit-logs/"


def headers(company):
    return {"HTTP_X_COMPANY_ID": str(company.id)}


def make_log(user, company, action=AuditLog.ActionType.PERIOD_CLOSED, **extra):
    return AuditLog.objects.create(
        company=company,
        user=user,
        action=action,
        target_model="FiscalPeriod",
        target_id="1",
        **extra,
    )


def test_audit_log_instance_cannot_be_modified_or_deleted(
    make_user, make_company
):
    user = make_user()
    company = make_company()
    log = make_log(user, company)

    log.justification = "Intento de modificación"
    with pytest.raises(ValidationError):
        log.save()

    with pytest.raises(ValidationError):
        log.delete()

    assert AuditLog.objects.get(pk=log.pk).justification == ""


def test_audit_log_queryset_cannot_update_or_delete(make_user, make_company):
    user = make_user()
    company = make_company()
    make_log(user, company, justification="Registro original")

    with pytest.raises(ValidationError):
        AuditLog.objects.all().update(justification="Modificado")

    with pytest.raises(ValidationError):
        AuditLog.objects.all().delete()

    with pytest.raises(ValidationError):
        AuditLog.objects.filter(company=company).delete()

    assert AuditLog.objects.filter(company=company).count() == 1
    assert AuditLog.objects.get(company=company).justification == "Registro original"


@pytest.mark.parametrize(
    "role,expected_status",
    [
        (CompanyMembership.Role.PARTNER, 200),
        (CompanyMembership.Role.AUDITOR, 200),
        (CompanyMembership.Role.ACCOUNTANT, 403),
        (CompanyMembership.Role.CLIENT, 403),
    ],
)
def test_audit_log_list_permission_matrix(role, expected_status, tenant_user):
    user, company, _membership, client = tenant_user(role=role)
    make_log(user, company)

    response = client.get(AUDIT_URL, **headers(company))

    assert response.status_code == expected_status
    if expected_status == 200:
        results = response.json()["data"]["results"]
        assert len(results) == 1
        assert results[0]["action"] == AuditLog.ActionType.PERIOD_CLOSED
        assert results[0]["action_display"] == "Cierre de Periodo Fiscal"
        assert results[0]["user_email"] == user.email


def test_audit_log_list_is_tenant_scoped_and_filterable(tenant_user, make_company):
    user, company, _membership, client = tenant_user()
    make_log(
        user,
        company,
        action=AuditLog.ActionType.PERIOD_CLOSED,
        justification="Periodo de mayo",
    )
    make_log(
        user,
        company,
        action=AuditLog.ActionType.PERIOD_REOPENED,
        justification="Reapertura de mayo",
    )
    foreign_company = make_company()
    make_log(user, foreign_company)

    response = client.get(
        AUDIT_URL,
        {"action": AuditLog.ActionType.PERIOD_REOPENED},
        **headers(company),
    )

    assert response.status_code == 200
    results = response.json()["data"]["results"]
    assert len(results) == 1
    assert results[0]["action"] == AuditLog.ActionType.PERIOD_REOPENED
    assert results[0]["justification"] == "Reapertura de mayo"


def test_audit_log_invalid_date_filter_returns_400(tenant_user):
    _user, company, _membership, client = tenant_user()

    response = client.get(
        AUDIT_URL,
        {"date_from": "2026-13-99"},
        **headers(company),
    )

    assert response.status_code == 400
    assert response.json()["errors"][0]["field"] == "date_from"

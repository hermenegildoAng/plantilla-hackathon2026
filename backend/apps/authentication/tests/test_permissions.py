from types import SimpleNamespace

import pytest
from rest_framework.exceptions import PermissionDenied

from apps.authentication.models import CompanyMembership
from apps.authentication.permissions import (
    CanManageAccounting,
    IsClientPortalAllowed,
    IsFiscalPeriodOpen,
    IsPartnerRole,
    IsReadOnlyAuditor,
    IsTenantMember,
    ensure_fiscal_period_open,
)


def build_request(method="GET", role=None, superuser=False):
    membership = None
    if role is not None:
        membership = SimpleNamespace(
            role=role,
            is_active=True,
        )
    user = SimpleNamespace(
        is_authenticated=True,
        is_superuser=superuser,
    )
    return SimpleNamespace(
        method=method,
        user=user,
        membership=membership,
    )


def test_is_tenant_member_accepts_every_active_role():
    permission = IsTenantMember()

    for role in CompanyMembership.Role.values:
        assert permission.has_permission(build_request(role=role), None) is True


def test_is_tenant_member_requires_membership_and_authentication():
    permission = IsTenantMember()

    assert permission.has_permission(build_request(), None) is False

    request = build_request()
    request.user = SimpleNamespace(is_authenticated=False, is_superuser=False)
    assert permission.has_permission(request, None) is False


def test_superuser_passes_tenant_permissions_without_membership():
    request = build_request(superuser=True)

    assert IsTenantMember().has_permission(request, None) is True
    assert IsPartnerRole().has_permission(request, None) is True


def test_is_partner_role_only_allows_partner():
    permission = IsPartnerRole()

    assert (
        permission.has_permission(
            build_request(role=CompanyMembership.Role.PARTNER), None
        )
        is True
    )
    for role in (
        CompanyMembership.Role.ACCOUNTANT,
        CompanyMembership.Role.AUDITOR,
        CompanyMembership.Role.CLIENT,
    ):
        assert permission.has_permission(build_request(role=role), None) is False


def test_can_manage_accounting_denies_delete_to_accountant():
    permission = CanManageAccounting()

    partner = build_request("DELETE", CompanyMembership.Role.PARTNER)
    accountant_delete = build_request("DELETE", CompanyMembership.Role.ACCOUNTANT)
    accountant_post = build_request("POST", CompanyMembership.Role.ACCOUNTANT)
    auditor_get = build_request("GET", CompanyMembership.Role.AUDITOR)

    assert permission.has_permission(partner, None) is True
    assert permission.has_permission(accountant_delete, None) is False
    assert permission.has_permission(accountant_post, None) is True
    assert permission.has_permission(auditor_get, None) is False


def test_is_read_only_auditor_allows_only_safe_methods():
    permission = IsReadOnlyAuditor()

    auditor_get = build_request("GET", CompanyMembership.Role.AUDITOR)
    auditor_post = build_request("POST", CompanyMembership.Role.AUDITOR)
    partner_post = build_request("POST", CompanyMembership.Role.PARTNER)
    client_get = build_request("GET", CompanyMembership.Role.CLIENT)

    assert permission.has_permission(auditor_get, None) is True
    assert permission.has_permission(auditor_post, None) is False
    assert permission.has_permission(partner_post, None) is True
    assert permission.has_permission(client_get, None) is False


def test_client_portal_permission_is_read_only_by_default():
    permission = IsClientPortalAllowed()
    view = SimpleNamespace()

    client_get = build_request("GET", CompanyMembership.Role.CLIENT)
    client_post = build_request("POST", CompanyMembership.Role.CLIENT)
    accountant_get = build_request("GET", CompanyMembership.Role.ACCOUNTANT)

    assert permission.has_permission(client_get, view) is True
    assert permission.has_permission(client_post, view) is False
    assert permission.has_permission(accountant_get, view) is False

    view.allow_client_write = True
    assert permission.has_permission(client_post, view) is True


def test_is_fiscal_period_open_blocks_unsafe_methods_on_closed_period():
    permission = IsFiscalPeriodOpen()
    closed = SimpleNamespace(is_closed=True)
    view = SimpleNamespace(get_fiscal_period=lambda request: closed)

    with pytest.raises(PermissionDenied) as exc_info:
        permission.has_permission(build_request("POST"), view)

    assert exc_info.value.detail.code == "period_closed"
    assert permission.has_permission(build_request("GET"), view) is True


def test_is_fiscal_period_open_allows_open_or_missing_period():
    permission = IsFiscalPeriodOpen()

    open_view = SimpleNamespace(
        get_fiscal_period=lambda request: SimpleNamespace(is_closed=False)
    )
    no_period_view = SimpleNamespace()

    assert permission.has_permission(build_request("PATCH"), open_view) is True
    assert permission.has_permission(build_request("DELETE"), no_period_view) is True


def test_is_fiscal_period_open_object_permission():
    permission = IsFiscalPeriodOpen()
    obj = SimpleNamespace(fiscal_period=SimpleNamespace(is_closed=True))

    with pytest.raises(PermissionDenied) as exc_info:
        permission.has_object_permission(build_request("PUT"), None, obj)

    assert exc_info.value.detail.code == "period_closed"


def test_ensure_fiscal_period_open_is_reusable():
    with pytest.raises(PermissionDenied) as exc_info:
        ensure_fiscal_period_open(SimpleNamespace(is_closed=True))

    assert exc_info.value.detail.code == "period_closed"
    assert ensure_fiscal_period_open(None) is None
    assert ensure_fiscal_period_open(SimpleNamespace(is_closed=False)) is None

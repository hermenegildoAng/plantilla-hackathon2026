"""DRF role permissions for the multi-tenant RBAC matrix [E-03].

Every class expects ``TenantContextMixin`` to have injected ``request.company``
and ``request.membership`` before permissions are evaluated.  Superusers are
treated as PARTNER for convenience; regular users always need an active
``CompanyMembership``.
"""

from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import SAFE_METHODS, BasePermission

from apps.authentication.models import CompanyMembership


def get_membership_role(request):
    """Return the active membership role for the current tenant, if any."""
    membership = getattr(request, "membership", None)
    if membership is not None and membership.is_active:
        return membership.role
    return None


def ensure_fiscal_period_open(fiscal_period):
    """Raise ``period_closed`` when the given fiscal period is closed.

    Reusable utility for views/services that resolve a period from a payload
    before calling the accounting services (used from block 4 onwards).
    """
    if fiscal_period is not None and getattr(fiscal_period, "is_closed", False):
        raise PermissionDenied(
            detail="El periodo contable está cerrado y no admite cambios.",
            code="period_closed",
        )


class TenantRolePermission(BasePermission):
    """Common checks shared by all tenant role permissions."""

    message = "No tiene permisos para realizar esta acción."

    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        if user is None or not user.is_authenticated:
            return False
        if user.is_superuser:
            return True
        return get_membership_role(request) is not None


class IsTenantMember(TenantRolePermission):
    """Any active role (PARTNER, ACCOUNTANT, AUDITOR, CLIENT) may pass."""

    def has_permission(self, request, view):
        return super().has_permission(request, view)


class IsPartnerRole(TenantRolePermission):
    """Only PARTNER (or a superuser) may pass."""

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        if request.user.is_superuser:
            return True
        return get_membership_role(request) == CompanyMembership.Role.PARTNER


class CanManageAccounting(TenantRolePermission):
    """PARTNER and ACCOUNTANT manage the books; ACCOUNTANT cannot delete."""

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        if request.user.is_superuser:
            return True

        role = get_membership_role(request)
        if role == CompanyMembership.Role.PARTNER:
            return True
        if role == CompanyMembership.Role.ACCOUNTANT:
            return request.method != "DELETE"
        return False


class IsReadOnlyAuditor(TenantRolePermission):
    """AUDITOR is limited to safe methods; PARTNER keeps full access."""

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        if request.user.is_superuser:
            return True

        role = get_membership_role(request)
        if role == CompanyMembership.Role.PARTNER:
            return True
        if role == CompanyMembership.Role.AUDITOR:
            return request.method in SAFE_METHODS
        return False


class IsClientPortalAllowed(TenantRolePermission):
    """CLIENT only reaches the external portal endpoints.

    Portal endpoints are read-only in this block.  Views that explicitly
    support client uploads must set ``allow_client_write = True``.
    """

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        if request.user.is_superuser:
            return True
        if get_membership_role(request) != CompanyMembership.Role.CLIENT:
            return False
        if request.method in SAFE_METHODS:
            return True
        # TODO(bloque 4): enable the exact document upload actions for CLIENT.
        return bool(getattr(view, "allow_client_write", False))


class IsFiscalPeriodOpen(TenantRolePermission):
    """Block unsafe methods when the resolved fiscal period is closed.

    The period can be provided by the view through ``get_fiscal_period()`` or
    attached to ``request.fiscal_period``.  When no period is resolved the
    permission allows the request so other validations can report the error.
    """

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True

        fiscal_period = None
        resolver = getattr(view, "get_fiscal_period", None)
        if callable(resolver):
            fiscal_period = resolver(request)
        else:
            fiscal_period = getattr(request, "fiscal_period", None)

        ensure_fiscal_period_open(fiscal_period)
        return True

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        ensure_fiscal_period_open(getattr(obj, "fiscal_period", None))
        return True

"""Role permissions specific to document endpoints (03 §3.4)."""

from apps.authentication.models import CompanyMembership
from apps.authentication.permissions import (
    TenantRolePermission,
    get_membership_role,
)


class CanUploadDocuments(TenantRolePermission):
    """PARTNER, ACCOUNTANT and CLIENT may upload; AUDITOR is read-only."""

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        if request.user.is_superuser:
            return True
        return get_membership_role(request) in {
            CompanyMembership.Role.PARTNER,
            CompanyMembership.Role.ACCOUNTANT,
            CompanyMembership.Role.CLIENT,
        }

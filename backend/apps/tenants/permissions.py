"""Tenant-specific permissions."""

from rest_framework.permissions import BasePermission

from apps.authentication.models import CompanyMembership


class CanCreateCompany(BasePermission):
    """PARTNER in at least one tenant, or a superuser [E-22]."""

    message = "No tiene permisos para crear empresas."

    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        if user is None or not user.is_authenticated:
            return False
        if user.is_superuser:
            return True
        return CompanyMembership.objects.filter(
            user=user,
            role=CompanyMembership.Role.PARTNER,
            is_active=True,
            company__is_active=True,
        ).exists()

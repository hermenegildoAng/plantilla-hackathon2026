"""Multi-tenant context helpers for DRF views [E-03].

Tenant validation happens inside DRF (``initial()``), not in a Django
middleware, because the JWT authentication runs after the middleware chain.
"""

from django.core.exceptions import ObjectDoesNotExist
from rest_framework.exceptions import (
    ErrorDetail,
    NotAuthenticated,
    PermissionDenied,
    ValidationError,
)

from apps.authentication.models import CompanyMembership
from apps.tenants.models import Company


TENANT_HEADER = "X-Company-ID"


def _invalid_header_error():
    return ValidationError(
        {
            TENANT_HEADER: [
                ErrorDetail(
                    "Debe proporcionar un encabezado X-Company-ID válido.",
                    code="missing_or_invalid_tenant_header",
                )
            ]
        }
    )


def _tenant_access_denied_error():
    return PermissionDenied(
        detail=ErrorDetail(
            "No tiene permisos para operar sobre esta empresa.",
            code="tenant_access_denied",
        )
    )


class TenantContextMixin:
    """Resolve the tenant from ``X-Company-ID`` before permission checks.

    On success the view gets ``request.company`` (``Company``) and
    ``request.membership`` (active ``CompanyMembership`` or ``None`` for a
    superuser that is not a member).

    ViewSets that mix tenant-scoped and global actions can list the exempt
    actions in ``tenant_exempt_actions`` (for example ``{"list", "create"}``).
    """

    tenant_exempt_actions = frozenset()

    def initial(self, request, *args, **kwargs):
        # Authenticate first so request.user is available; DRF's own initial()
        # call below reuses the cached user.
        self.perform_authentication(request)

        if not self.is_tenant_context_exempt():
            self.resolve_tenant_context(request)

        super().initial(request, *args, **kwargs)

    def is_tenant_context_exempt(self) -> bool:
        action = getattr(self, "action", None)
        return action in self.tenant_exempt_actions

    def resolve_tenant_context(self, request) -> None:
        if not request.user or not request.user.is_authenticated:
            raise NotAuthenticated()

        company_id = self._parse_company_id(request)
        membership = self._find_active_membership(request.user, company_id)

        if membership is not None:
            request.company = membership.company
            request.membership = membership
            return

        if request.user.is_superuser:
            company = Company.objects.filter(pk=company_id, is_active=True).first()
            if company is None:
                raise _tenant_access_denied_error()
            request.company = company
            request.membership = None
            return

        raise _tenant_access_denied_error()

    @staticmethod
    def _parse_company_id(request) -> int:
        raw_company_id = request.headers.get(TENANT_HEADER)
        if raw_company_id is None:
            raise _invalid_header_error()

        raw_company_id = raw_company_id.strip()
        if not raw_company_id:
            raise _invalid_header_error()

        try:
            company_id = int(raw_company_id)
        except (TypeError, ValueError):
            raise _invalid_header_error() from None

        if company_id <= 0:
            raise _invalid_header_error()
        return company_id

    @staticmethod
    def _find_active_membership(user, company_id):
        try:
            return (
                CompanyMembership.objects.select_related("company")
                .filter(
                    user=user,
                    company_id=company_id,
                    is_active=True,
                    company__is_active=True,
                )
                .get()
            )
        except ObjectDoesNotExist:
            return None


class TenantQuerySetMixin:
    """Restrict every queryset and creation to ``request.company``.

    Subclasses must be operational views protected by ``TenantContextMixin``.
    """

    def get_queryset(self):
        return super().get_queryset().filter(company=self.request.company)

    def perform_create(self, serializer):
        serializer.save(company=self.request.company)

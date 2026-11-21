"""Core endpoints: health and the read-only audit log."""

from datetime import date

from rest_framework import mixins, viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.authentication.permissions import IsPartnerOrAuditor
from apps.core.models import AuditLog
from apps.core.serializers import AuditLogSerializer
from apps.tenants.mixins import TenantContextMixin


class HealthView(APIView):
    """Unauthenticated liveness endpoint."""

    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({"status": "ok"})


def _parse_date(raw_value, field):
    try:
        return date.fromisoformat(raw_value)
    except (TypeError, ValueError):
        raise ValidationError(
            {field: "Formato de fecha inválido. Use AAAA-MM-DD."}
        ) from None


class AuditLogViewSet(
    TenantContextMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    """GET /api/v1/audit-logs/ — PARTNER and AUDITOR only [E-21]."""

    http_method_names = ["get", "head", "options"]
    serializer_class = AuditLogSerializer
    permission_classes = [IsAuthenticated, IsPartnerOrAuditor]

    def get_queryset(self):
        queryset = AuditLog.objects.filter(
            company=self.request.company
        ).select_related("user")

        action = self.request.query_params.get("action")
        if action:
            queryset = queryset.filter(action=action)

        exact_date = self.request.query_params.get("date")
        if exact_date:
            queryset = queryset.filter(
                created_at__date=_parse_date(exact_date, "date")
            )

        date_from = self.request.query_params.get("date_from")
        if date_from:
            queryset = queryset.filter(
                created_at__date__gte=_parse_date(date_from, "date_from")
            )

        date_to = self.request.query_params.get("date_to")
        if date_to:
            queryset = queryset.filter(
                created_at__date__lte=_parse_date(date_to, "date_to")
            )

        return queryset

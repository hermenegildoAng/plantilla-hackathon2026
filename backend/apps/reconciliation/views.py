"""Reconciliation and report endpoints [E-21]."""

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ErrorDetail, NotFound, ValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounting.models import FiscalPeriod
from apps.authentication.models import CompanyMembership
from apps.authentication.permissions import (
    CanManageAccounting,
    CanReadAccounting,
    IsTenantMember,
)
from apps.reconciliation.models import BankMovement
from apps.reconciliation.reports import (
    build_executive_summary,
    build_trial_balance,
    reduce_executive_summary_for_client,
)
from apps.reconciliation.serializers import (
    BankMovementImportSerializer,
    BankMovementMatchSerializer,
    BankMovementSerializer,
)
from apps.reconciliation.services import (
    import_bank_movements,
    match_movement,
    suggest_matches,
    unmatch_movement,
)
from apps.tenants.mixins import TenantContextMixin


def _requested_period(request):
    raw_period = request.query_params.get("period")
    if raw_period in (None, ""):
        raise ValidationError(
            {
                "period": ErrorDetail(
                    "El periodo fiscal es obligatorio.",
                    code="required",
                )
            }
        )

    try:
        period_id = int(raw_period)
    except (TypeError, ValueError):
        raise ValidationError(
            {
                "period": ErrorDetail(
                    "El periodo fiscal debe ser un número entero.",
                    code="invalid",
                )
            }
        ) from None

    period = FiscalPeriod.objects.filter(
        pk=period_id,
        company=request.company,
    ).first()
    if period is None:
        raise NotFound(
            detail=ErrorDetail(
                "El periodo fiscal no existe en la empresa activa.",
                code="not_found",
            )
        )
    return period


class BankMovementViewSet(
    TenantContextMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """Bank movement list and reconciliation actions [E-21]."""

    http_method_names = ["get", "post", "head", "options"]

    def get_permissions(self):
        if self.action in {"import_csv", "match", "unmatch"}:
            return [IsAuthenticated(), CanManageAccounting()]
        return [IsAuthenticated(), CanReadAccounting()]

    def get_queryset(self):
        company = getattr(self.request, "company", None)
        if company is None:
            # Schema generation has no tenant context; keep the model visible.
            return BankMovement.objects.none()

        queryset = (
            BankMovement.objects.filter(company=company)
            .select_related("entry", "document")
        )

        movement_status = self.request.query_params.get("status")
        if movement_status:
            normalized = movement_status.strip().upper()
            valid_statuses = {choice for choice, _label in BankMovement.Status.choices}
            if normalized not in valid_statuses:
                raise ValidationError(
                    {
                        "status": ErrorDetail(
                            "El estado debe ser PENDING o RECONCILED.",
                            code="invalid",
                        )
                    }
                )
            queryset = queryset.filter(status=normalized)

        return queryset

    def get_serializer_class(self):
        if self.action == "import_csv":
            return BankMovementImportSerializer
        if self.action == "match":
            return BankMovementMatchSerializer
        return BankMovementSerializer

    @action(
        detail=False,
        methods=["post"],
        url_path="import",
        parser_classes=[MultiPartParser, FormParser],
    )
    def import_csv(self, request):
        payload = BankMovementImportSerializer(data=request.data)
        payload.is_valid(raise_exception=True)

        result = import_bank_movements(
            company=request.company,
            file_obj=payload.validated_data["file"],
        )
        response = Response(result, status=status.HTTP_200_OK)
        response.response_message = "Importación de movimientos procesada."
        return response

    @action(detail=True, methods=["get"], url_path="suggestions")
    def suggestions(self, request, pk=None):
        movement = self.get_object()
        candidates = suggest_matches(movement)
        response = Response(
            {
                "movement_id": movement.pk,
                "count": len(candidates),
                "candidates": candidates,
            },
            status=status.HTTP_200_OK,
        )
        response.response_message = "Sugerencias de conciliación obtenidas."
        return response

    @action(detail=True, methods=["post"], url_path="match")
    def match(self, request, pk=None):
        movement = self.get_object()
        payload = BankMovementMatchSerializer(data=request.data)
        payload.is_valid(raise_exception=True)

        movement = match_movement(
            movement,
            entry_id=payload.validated_data.get("entry_id"),
            document_id=payload.validated_data.get("document_id"),
        )
        response = Response(
            BankMovementSerializer(movement).data,
            status=status.HTTP_200_OK,
        )
        response.response_message = "Movimiento bancario conciliado correctamente."
        return response

    @action(detail=True, methods=["post"], url_path="unmatch")
    def unmatch(self, request, pk=None):
        movement = self.get_object()
        movement = unmatch_movement(movement)
        response = Response(
            BankMovementSerializer(movement).data,
            status=status.HTTP_200_OK,
        )
        response.response_message = (
            "Conciliación del movimiento bancario revertida correctamente."
        )
        return response


class TrialBalanceView(TenantContextMixin, APIView):
    """GET /api/v1/reports/trial-balance/?period=<id>."""

    permission_classes = [IsAuthenticated, CanReadAccounting]

    @extend_schema(
        parameters=[
            OpenApiParameter(
                "period",
                OpenApiTypes.INT,
                OpenApiParameter.QUERY,
                required=True,
                description="ID del periodo fiscal de la empresa activa.",
            )
        ],
        responses={200: OpenApiTypes.OBJECT},
    )
    def get(self, request):
        period = _requested_period(request)
        response = Response(
            build_trial_balance(request.company, period),
            status=status.HTTP_200_OK,
        )
        response.response_message = "Balanza de comprobación generada."
        return response


class ExecutiveSummaryView(TenantContextMixin, APIView):
    """GET /api/v1/reports/executive-summary/?period=<id>."""

    permission_classes = [IsAuthenticated, IsTenantMember]

    @extend_schema(
        parameters=[
            OpenApiParameter(
                "period",
                OpenApiTypes.INT,
                OpenApiParameter.QUERY,
                required=True,
                description="ID del periodo fiscal de la empresa activa.",
            )
        ],
        responses={200: OpenApiTypes.OBJECT},
    )
    def get(self, request):
        period = _requested_period(request)
        summary = build_executive_summary(request.company, period)

        membership = getattr(request, "membership", None)
        is_client = (
            membership is not None
            and membership.role == CompanyMembership.Role.CLIENT
        )
        if is_client:
            summary = reduce_executive_summary_for_client(summary)

        response = Response(summary, status=status.HTTP_200_OK)
        response.response_message = "Resumen ejecutivo generado."
        return response

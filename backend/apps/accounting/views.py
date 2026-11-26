"""Accounting endpoints: accounts, periods, entries and close/reopen."""

import ipaddress
from datetime import date

from django.db.models import Q
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ErrorDetail, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounting.models import (
    AccountCatalog,
    AccountingEntry,
    FiscalPeriod,
)
from apps.accounting.serializers import (
    AccountCatalogSerializer,
    AccountCatalogTreeSerializer,
    AccountingEntryDetailSerializer,
    AccountingEntryWriteSerializer,
    FiscalPeriodSerializer,
    PeriodReopenSerializer,
)
from apps.accounting.services import (
    close_period,
    create_accounting_entry,
    delete_accounting_entry,
    reopen_period,
    update_accounting_entry,
)
from apps.authentication.permissions import (
    CanEditAccountCatalog,
    CanManageAccounting,
    CanReadAccounting,
    IsPartnerRole,
)
from apps.tenants.mixins import TenantContextMixin


def get_client_ip(request):
    """Best-effort client IP, taken from the proxy header when present."""
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR", "")
    candidate = forwarded_for.split(",")[0].strip() if forwarded_for else ""
    candidate = candidate or request.META.get("REMOTE_ADDR", "")
    if not candidate:
        return None
    try:
        return str(ipaddress.ip_address(candidate))
    except ValueError:
        return None


class AccountCatalogViewSet(
    TenantContextMixin,
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """GET/POST/PATCH/DELETE /api/v1/accounts/ [E-12]."""

    http_method_names = ["get", "post", "patch", "delete", "head", "options"]
    serializer_class = AccountCatalogSerializer

    def get_permissions(self):
        if self.action in {"list"}:
            return [IsAuthenticated(), CanReadAccounting()]
        if self.action in {"create", "destroy"}:
            return [IsAuthenticated(), IsPartnerRole()]
        return [IsAuthenticated(), CanEditAccountCatalog()]

    def get_queryset(self):
        queryset = self._base_queryset()
        search = self.request.query_params.get("search")
        if search:
            from django.db.models import Q

            queryset = queryset.filter(
                Q(code__icontains=search) | Q(name__icontains=search)
            )

        account_type = self.request.query_params.get("account_type")
        if account_type:
            queryset = queryset.filter(account_type=account_type.upper())

        is_selectable = self.request.query_params.get("is_selectable")
        if is_selectable is not None:
            normalized = is_selectable.strip().lower()
            if normalized in {"true", "1", "yes"}:
                queryset = queryset.filter(is_selectable=True)
            elif normalized in {"false", "0", "no"}:
                queryset = queryset.filter(is_selectable=False)

        is_active = self.request.query_params.get("is_active")
        if is_active is not None:
            normalized = is_active.strip().lower()
            if normalized in {"true", "1", "yes"}:
                queryset = queryset.filter(is_active=True)
            elif normalized in {"false", "0", "no"}:
                queryset = queryset.filter(is_active=False)

        return queryset

    def _base_queryset(self):
        return (
            AccountCatalog.objects.filter(company=self.request.company)
            .select_related("parent")
            .prefetch_related("children")
        )

    def get_serializer_class(self):
        if self.action == "list" and self._is_tree_request():
            return AccountCatalogTreeSerializer
        return AccountCatalogSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["company"] = getattr(self.request, "company", None)
        return context

    def _is_tree_request(self) -> bool:
        raw_value = self.request.query_params.get("tree", "")
        return raw_value.strip().lower() in {"true", "1", "yes"}

    def list(self, request, *args, **kwargs):
        if not self._is_tree_request():
            queryset = self.filter_queryset(self.get_queryset())
            page = self.paginate_queryset(queryset)
            if page is not None:
                serializer = self.get_serializer(page, many=True)
                return self.get_paginated_response(serializer.data)
            serializer = self.get_serializer(queryset, many=True)
            return Response(serializer.data)

        queryset = self.filter_queryset(self.get_queryset())
        accounts = list(queryset)
        selected_ids = {account.pk for account in accounts}

        has_filters = bool(
            {"search", "account_type", "is_selectable", "is_active"}
            & set(request.query_params.keys())
        )

        all_accounts = {
            account.pk: account for account in self._base_queryset()
        }
        if has_filters:
            # Keep the ancestors of every matching account so the tree stays
            # navigable even when the filter matches a leaf.
            for account in accounts:
                parent_id = account.parent_id
                while parent_id is not None:
                    selected_ids.add(parent_id)
                    parent = all_accounts.get(parent_id)
                    parent_id = parent.parent_id if parent is not None else None
            roots = [
                account
                for account in all_accounts.values()
                if account.pk in selected_ids
                and (
                    account.parent_id is None
                    or account.parent_id not in selected_ids
                )
            ]
        else:
            roots = [
                account
                for account in all_accounts.values()
                if account.parent_id is None
            ]

        page = self.paginate_queryset(roots)
        serializer_context = self.get_serializer_context()
        serializer_context["tree_selected_ids"] = selected_ids
        if page is not None:
            serializer = self.get_serializer(
                page,
                many=True,
                context=serializer_context,
            )
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(
            roots,
            many=True,
            context=serializer_context,
        )
        return Response(serializer.data)

    def perform_create(self, serializer):
        serializer.save(company=self.request.company)

    def destroy(self, request, *args, **kwargs):
        account = self.get_object()
        if account.children.exists():
            raise ValidationError(
                {
                    "detail": ErrorDetail(
                        "La cuenta tiene cuentas hijas. Reasígnelas o "
                        "desactívela antes de eliminarla.",
                        code="account_has_children",
                    )
                }
            )
        if account.entry_items.exists():
            raise ValidationError(
                {
                    "detail": ErrorDetail(
                        "La cuenta tiene movimientos contables y no puede "
                        "eliminarse. Desactívela para conservar el historial.",
                        code="account_has_movements",
                    )
                }
            )

        account.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class AccountingEntryViewSet(
    TenantContextMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """CRUD /api/v1/entries/ with the RBAC matrix from 03 §2.2."""

    http_method_names = ["get", "post", "put", "patch", "delete", "head", "options"]

    def get_permissions(self):
        if self.action in {"list", "retrieve"}:
            return [IsAuthenticated(), CanReadAccounting()]
        if self.action in {"create", "update", "partial_update"}:
            return [IsAuthenticated(), CanManageAccounting()]
        if self.action == "destroy":
            return [IsAuthenticated(), IsPartnerRole()]
        return [IsAuthenticated(), CanReadAccounting()]

    def get_queryset(self):
        queryset = (
            AccountingEntry.objects.filter(company=self.request.company)
            .select_related("fiscal_period")
            .prefetch_related("items__account", "items__document")
        )

        fiscal_period = self.request.query_params.get("fiscal_period")
        if fiscal_period:
            try:
                fiscal_period_id = int(fiscal_period)
            except (TypeError, ValueError):
                raise ValidationError(
                    {
                        "fiscal_period": ErrorDetail(
                            "El periodo fiscal debe ser un número entero.",
                            code="invalid",
                        )
                    }
                ) from None
            queryset = queryset.filter(fiscal_period_id=fiscal_period_id)

        entry_type = self.request.query_params.get("entry_type")
        if entry_type:
            queryset = queryset.filter(entry_type=entry_type.upper())

        entry_status = self.request.query_params.get("status")
        if entry_status:
            queryset = queryset.filter(status=entry_status.upper())

        date_from = self._parse_date_param("date_from")
        if date_from is not None:
            queryset = queryset.filter(entry_date__gte=date_from)

        date_to = self._parse_date_param("date_to")
        if date_to is not None:
            queryset = queryset.filter(entry_date__lte=date_to)

        search = self.request.query_params.get("search")
        if search:
            term = search.strip()
            queryset = queryset.filter(
                Q(folio__icontains=term) | Q(concept__icontains=term)
            )

        return queryset

    def _parse_date_param(self, field):
        raw_value = self.request.query_params.get(field)
        if not raw_value:
            return None
        try:
            return date.fromisoformat(raw_value.strip())
        except ValueError:
            raise ValidationError(
                {
                    field: ErrorDetail(
                        "La fecha debe tener el formato AAAA-MM-DD.",
                        code="invalid",
                    )
                }
            ) from None

    def get_serializer_class(self):
        if self.action in {"list", "retrieve"}:
            return AccountingEntryDetailSerializer
        return AccountingEntryWriteSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["company"] = getattr(self.request, "company", None)
        return context

    @staticmethod
    def _split_payload(validated_data):
        data = dict(validated_data)
        items_data = data.pop("items", None)
        fiscal_period = data.pop("fiscal_period", None)
        return data, fiscal_period, items_data

    def create(self, request, *args, **kwargs):
        payload = self.get_serializer(data=request.data)
        payload.is_valid(raise_exception=True)
        header_data, fiscal_period, items_data = self._split_payload(
            payload.validated_data
        )

        entry = create_accounting_entry(
            company=request.company,
            fiscal_period=fiscal_period,
            user=request.user,
            header_data=header_data,
            items_data=items_data,
        )
        response = Response(
            AccountingEntryDetailSerializer(
                entry,
                context=self.get_serializer_context(),
            ).data,
            status=status.HTTP_201_CREATED,
        )
        response.response_message = "Póliza registrada correctamente."
        return response

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        payload = self.get_serializer(
            instance,
            data=request.data,
            partial=partial,
        )
        payload.is_valid(raise_exception=True)
        header_data, fiscal_period, items_data = self._split_payload(
            payload.validated_data
        )
        if fiscal_period is not None:
            header_data["fiscal_period"] = fiscal_period

        entry = update_accounting_entry(
            instance,
            user=request.user,
            header_data=header_data,
            items_data=items_data,
        )
        response = Response(
            AccountingEntryDetailSerializer(
                entry,
                context=self.get_serializer_context(),
            ).data,
            status=status.HTTP_200_OK,
        )
        response.response_message = "Póliza actualizada correctamente."
        return response

    def destroy(self, request, *args, **kwargs):
        entry = self.get_object()
        delete_accounting_entry(
            entry,
            user=request.user,
            ip_address=get_client_ip(request),
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


class FiscalPeriodViewSet(
    TenantContextMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    """GET /periods/ plus close/reopen actions (03 §3.6)."""

    http_method_names = ["get", "post", "head", "options"]
    serializer_class = FiscalPeriodSerializer

    def get_permissions(self):
        if self.action == "list":
            return [IsAuthenticated(), CanReadAccounting()]
        return [IsAuthenticated(), IsPartnerRole()]

    def get_queryset(self):
        return FiscalPeriod.objects.filter(
            company=self.request.company
        ).select_related("closed_by")

    @action(detail=True, methods=["post"])
    def close(self, request, pk=None):
        period = self.get_object()
        period = close_period(
            period,
            user=request.user,
            ip_address=get_client_ip(request),
        )
        serializer = self.get_serializer(period)
        response = Response(serializer.data, status=status.HTTP_200_OK)
        response.response_message = "Periodo fiscal cerrado correctamente."
        return response

    @action(detail=True, methods=["post"])
    def reopen(self, request, pk=None):
        period = self.get_object()
        payload = PeriodReopenSerializer(data=request.data)
        payload.is_valid(raise_exception=True)

        period = reopen_period(
            period,
            user=request.user,
            justification=payload.validated_data["justification"],
            ip_address=get_client_ip(request),
        )
        serializer = self.get_serializer(period)
        response = Response(serializer.data, status=status.HTTP_200_OK)
        response.response_message = "Periodo fiscal reabierto correctamente."
        return response

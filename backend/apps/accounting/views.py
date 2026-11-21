"""Accounting endpoints: chart of accounts, fiscal periods and close/reopen."""

import ipaddress

from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounting.models import AccountCatalog, FiscalPeriod
from apps.accounting.serializers import (
    AccountCatalogSerializer,
    AccountCatalogTreeSerializer,
    FiscalPeriodSerializer,
    PeriodReopenSerializer,
)
from apps.accounting.services import close_period, reopen_period
from apps.authentication.permissions import (
    CanEditAccountCatalog,
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
    viewsets.GenericViewSet,
):
    """GET/POST/PATCH /api/v1/accounts/ [E-12]."""

    http_method_names = ["get", "post", "patch", "head", "options"]
    serializer_class = AccountCatalogSerializer

    def get_permissions(self):
        if self.action in {"list"}:
            return [IsAuthenticated(), CanReadAccounting()]
        if self.action == "create":
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

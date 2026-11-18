"""Company and membership endpoints (03 §3.2)."""

from django.db.models import Prefetch
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.authentication.models import CompanyMembership
from apps.authentication.permissions import IsPartnerRole, IsTenantMember
from apps.tenants.mixins import TenantContextMixin
from apps.tenants.models import Company
from apps.tenants.permissions import CanCreateCompany
from apps.tenants.serializers import (
    CompanyCreateSerializer,
    CompanyDetailSerializer,
    CompanyListSerializer,
    CompanyMembershipCreateSerializer,
    CompanyMembershipSerializer,
)


class CompanyViewSet(TenantContextMixin, viewsets.ModelViewSet):
    """Companies are global to list/create and tenant-scoped afterwards."""

    http_method_names = ["get", "post", "patch", "delete", "head", "options"]
    tenant_exempt_actions = frozenset({"list", "create"})

    def get_permissions(self):
        if self.action == "list":
            return [IsAuthenticated()]
        if self.action == "create":
            return [IsAuthenticated(), CanCreateCompany()]
        if self.action == "members":
            return [IsAuthenticated(), IsTenantMember(), IsPartnerRole()]
        if self.action == "retrieve":
            return [IsAuthenticated(), IsTenantMember()]
        return [IsAuthenticated(), IsTenantMember(), IsPartnerRole()]

    def get_serializer_class(self):
        if self.action == "list":
            return CompanyListSerializer
        if self.action == "create":
            return CompanyCreateSerializer
        return CompanyDetailSerializer

    def get_queryset(self):
        user = self.request.user
        membership_prefetch = Prefetch(
            "user_memberships",
            queryset=CompanyMembership.objects.filter(user=user),
            to_attr="current_user_memberships",
        )

        if self.action == "list":
            queryset = Company.objects.filter(is_active=True)
            if not user.is_superuser:
                queryset = queryset.filter(
                    user_memberships__user=user,
                    user_memberships__is_active=True,
                )
            return queryset.distinct().prefetch_related(membership_prefetch)

        company = getattr(self.request, "company", None)
        if company is None:
            return Company.objects.none()
        return Company.objects.filter(pk=company.pk).prefetch_related(
            membership_prefetch
        )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)

        response_serializer = CompanyDetailSerializer(
            serializer.instance,
            context=self.get_serializer_context(),
        )
        return Response(
            response_serializer.data,
            status=status.HTTP_201_CREATED,
        )

    def destroy(self, request, *args, **kwargs):
        company = self.get_object()
        company.is_active = False
        company.save(update_fields=["is_active", "updated_at"])
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["get", "post"], url_path="members")
    def members(self, request, pk=None):
        company = self.get_object()

        if request.method == "POST":
            serializer = CompanyMembershipCreateSerializer(
                data=request.data,
                context={"company": company, "request": request},
            )
            serializer.is_valid(raise_exception=True)
            membership = serializer.save()
            return Response(
                CompanyMembershipSerializer(membership).data,
                status=status.HTTP_201_CREATED,
            )

        queryset = (
            CompanyMembership.objects.filter(company=company)
            .select_related("user")
            .order_by("user__email")
        )
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = CompanyMembershipSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = CompanyMembershipSerializer(queryset, many=True)
        return Response(serializer.data)

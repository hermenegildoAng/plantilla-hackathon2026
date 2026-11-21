"""Serializers for the accounting catalog, periods and governance actions."""

from rest_framework import serializers
from rest_framework.exceptions import ErrorDetail, PermissionDenied

from apps.accounting.models import AccountCatalog, FiscalPeriod
from apps.accounting.services import JUSTIFICATION_MIN_LENGTH
from apps.authentication.models import CompanyMembership


class AccountCatalogSerializer(serializers.ModelSerializer):
    """Chart-of-accounts row used by GET/POST/PATCH /accounts/."""

    parent = serializers.PrimaryKeyRelatedField(
        queryset=AccountCatalog.objects.all(),
        required=False,
        allow_null=True,
    )

    class Meta:
        model = AccountCatalog
        fields = [
            "id",
            "parent",
            "code",
            "sat_group_code",
            "name",
            "account_type",
            "nature",
            "is_selectable",
            "is_active",
        ]
        read_only_fields = ["id"]

    def _company(self):
        company = self.context.get("company")
        if company is None:
            request = self.context.get("request")
            company = getattr(request, "company", None)
        return company

    def validate_code(self, value):
        code = (value or "").strip()
        if not code:
            raise serializers.ValidationError("El código de la cuenta es obligatorio.")

        company = self._company()
        if company is None:
            raise serializers.ValidationError(
                "No se pudo determinar la empresa para validar el código."
            )

        queryset = AccountCatalog.objects.filter(company=company, code=code)
        if self.instance is not None:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise serializers.ValidationError(
                "Ya existe una cuenta con este código en la empresa."
            )
        return code

    def validate_parent(self, parent):
        if parent is None:
            return parent

        company = self._company()
        if company is None or parent.company_id != company.pk:
            raise serializers.ValidationError(
                "La cuenta padre debe pertenecer a la misma empresa."
            )

        if self.instance is not None and parent.pk == self.instance.pk:
            raise serializers.ValidationError(
                "Una cuenta no puede ser su propia cuenta padre."
            )

        # Walk up to prevent cycles when reassigning a parent.
        current = parent
        while current is not None:
            if self.instance is not None and current.pk == self.instance.pk:
                raise serializers.ValidationError(
                    "La jerarquía de cuentas no puede contener ciclos."
                )
            current = current.parent
        return parent

    def validate(self, attrs):
        request = self.context.get("request")
        membership = getattr(request, "membership", None)
        is_partner = bool(request and request.user.is_superuser)
        if membership is not None:
            is_partner = membership.role == CompanyMembership.Role.PARTNER

        if self.instance is not None and not is_partner:
            sent_fields = set(self.initial_data.keys())
            if sent_fields - {"name"}:
                raise PermissionDenied(
                    detail=ErrorDetail(
                        "El auxiliar contable solo puede modificar el nombre de la cuenta.",
                        code="accountant_name_only",
                    )
                )

        # TODO(bloque 5): reject account_type/nature changes when the account
        # already has AccountingEntryItem rows.
        # TODO(bloque 5): reject using an account with posted movements as parent.
        return attrs


class AccountCatalogTreeSerializer(AccountCatalogSerializer):
    """Nested representation used by GET /accounts/?tree=true."""

    children = serializers.SerializerMethodField()

    class Meta(AccountCatalogSerializer.Meta):
        fields = AccountCatalogSerializer.Meta.fields + ["children"]

    def get_children(self, obj):
        children = obj.children.all()
        selected_ids = self.context.get("tree_selected_ids")
        if selected_ids is not None:
            children = [
                child for child in children if child.pk in selected_ids
            ]
        return AccountCatalogTreeSerializer(
            children,
            many=True,
            context=self.context,
        ).data


class FiscalPeriodSerializer(serializers.ModelSerializer):
    """Period payload from 03 §3.6."""

    closed_by_name = serializers.SerializerMethodField()
    entries_count = serializers.SerializerMethodField()
    unaccounted_documents_count = serializers.SerializerMethodField()

    class Meta:
        model = FiscalPeriod
        fields = [
            "id",
            "year",
            "month",
            "is_closed",
            "closed_at",
            "closed_by_name",
            "entries_count",
            "unaccounted_documents_count",
        ]
        read_only_fields = fields

    def get_closed_by_name(self, obj):
        return obj.closed_by.full_name if obj.closed_by_id else None

    def get_entries_count(self, obj):
        # TODO(bloque 5): count AccountingEntry rows for this period.
        return 0

    def get_unaccounted_documents_count(self, obj):
        # Documents without a linked accounting entry (block 5 will link them).
        return obj.documents.filter(is_accounted=False).count()


class PeriodReopenSerializer(serializers.Serializer):
    """Validate the mandatory justification for POST /periods/{id}/reopen/."""

    justification = serializers.CharField(
        min_length=JUSTIFICATION_MIN_LENGTH,
        allow_blank=False,
        trim_whitespace=True,
        error_messages={
            "required": "La justificación es obligatoria.",
            "blank": "La justificación es obligatoria.",
            "min_length": (
                "La justificación debe tener al menos "
                f"{JUSTIFICATION_MIN_LENGTH} caracteres."
            ),
        },
    )

    def validate_justification(self, value):
        value = value.strip()
        if len(value) < JUSTIFICATION_MIN_LENGTH:
            raise serializers.ValidationError(
                "La justificación debe tener al menos "
                f"{JUSTIFICATION_MIN_LENGTH} caracteres."
            )
        return value

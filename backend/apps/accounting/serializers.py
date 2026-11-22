"""Serializers for the accounting catalog, periods, entries and governance."""

from decimal import Decimal

from rest_framework import serializers
from rest_framework.exceptions import ErrorDetail, PermissionDenied

from apps.accounting.models import (
    AccountCatalog,
    AccountingEntry,
    AccountingEntryItem,
    FiscalPeriod,
)
from apps.accounting.services import (
    JUSTIFICATION_MIN_LENGTH,
    get_or_create_period,
)
from apps.authentication.models import CompanyMembership
from apps.documents.models import Document


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
        return obj.entries.count()

    def get_unaccounted_documents_count(self, obj):
        # Documents without a linked accounting entry (block 5 will link them).
        return obj.documents.filter(is_accounted=False).count()


class AccountingEntryItemReadSerializer(serializers.ModelSerializer):
    """Journal entry line returned by GET /entries/."""

    account_code = serializers.CharField(source="account.code", read_only=True)
    account_name = serializers.CharField(source="account.name", read_only=True)
    document_uuid = serializers.UUIDField(
        source="document.uuid",
        read_only=True,
        allow_null=True,
    )

    class Meta:
        model = AccountingEntryItem
        fields = [
            "id",
            "line_number",
            "account",
            "account_code",
            "account_name",
            "document",
            "document_uuid",
            "description",
            "debit",
            "credit",
        ]
        read_only_fields = fields


class AccountingEntryDetailSerializer(serializers.ModelSerializer):
    """Entry payload from 03 §3.5."""

    period_label = serializers.SerializerMethodField()
    items = AccountingEntryItemReadSerializer(many=True, read_only=True)

    class Meta:
        model = AccountingEntry
        fields = [
            "id",
            "fiscal_period",
            "period_label",
            "entry_type",
            "folio",
            "entry_date",
            "concept",
            "status",
            "total_debit",
            "total_credit",
            "items",
        ]
        read_only_fields = fields

    def get_period_label(self, obj):
        return f"{obj.fiscal_period.year}-{obj.fiscal_period.month:02d}"


class AccountingEntryItemWriteSerializer(serializers.Serializer):
    """Validate one journal entry line (03 §3.5 rules 4 and 5)."""

    account = serializers.PrimaryKeyRelatedField(
        queryset=AccountCatalog.objects.all(),
    )
    document = serializers.PrimaryKeyRelatedField(
        queryset=Document.objects.all(),
        required=False,
        allow_null=True,
    )
    description = serializers.CharField(
        max_length=255,
        required=False,
        allow_blank=True,
        default="",
    )
    debit = serializers.DecimalField(
        max_digits=14,
        decimal_places=2,
        min_value=Decimal("0.00"),
        default=Decimal("0.00"),
    )
    credit = serializers.DecimalField(
        max_digits=14,
        decimal_places=2,
        min_value=Decimal("0.00"),
        default=Decimal("0.00"),
    )

    def _company(self):
        company = self.context.get("company")
        if company is None:
            request = self.context.get("request")
            company = getattr(request, "company", None)
        return company

    def validate(self, attrs):
        company = self._company()
        account = attrs.get("account")
        if company is not None and account is not None:
            if account.company_id != company.pk:
                raise serializers.ValidationError(
                    {
                        "account": ErrorDetail(
                            "La cuenta contable no pertenece a la empresa de la "
                            "póliza.",
                            code="non_selectable_account",
                        )
                    }
                )
            if not account.is_selectable:
                raise serializers.ValidationError(
                    {
                        "account": ErrorDetail(
                            f"La cuenta {account.code} es acumulativa y no "
                            "acepta movimientos directos.",
                            code="non_selectable_account",
                        )
                    }
                )

        document = attrs.get("document")
        if (
            company is not None
            and document is not None
            and document.company_id != company.pk
        ):
            raise serializers.ValidationError(
                {
                    "document": ErrorDetail(
                        "El documento no pertenece a la empresa de la póliza.",
                        code="invalid_document",
                    )
                }
            )

        debit = attrs.get("debit", Decimal("0.00"))
        credit = attrs.get("credit", Decimal("0.00"))
        if (debit > Decimal("0.00") and credit > Decimal("0.00")) or (
            debit == Decimal("0.00") and credit == Decimal("0.00")
        ):
            raise serializers.ValidationError(
                {
                    "debit": ErrorDetail(
                        "Cada renglón debe tener un monto mayor a cero en Cargo "
                        "o Abono, pero no en ambos.",
                        code="invalid_line_amounts",
                    )
                }
            )
        return attrs


class AccountingEntryWriteSerializer(serializers.Serializer):
    """Validate an entry payload with the seven rules from 03 §3.5."""

    fiscal_period = serializers.PrimaryKeyRelatedField(
        queryset=FiscalPeriod.objects.all(),
        required=False,
        allow_null=True,
    )
    entry_type = serializers.ChoiceField(choices=AccountingEntry.EntryType.choices)
    entry_date = serializers.DateField()
    concept = serializers.CharField(max_length=500)
    status = serializers.ChoiceField(
        choices=AccountingEntry.Status.choices,
        required=False,
    )
    items = AccountingEntryItemWriteSerializer(many=True)

    def _company(self):
        company = self.context.get("company")
        if company is None:
            request = self.context.get("request")
            company = getattr(request, "company", None)
        return company

    def _raise_period_closed(self, period):
        raise serializers.ValidationError(
            {
                "fiscal_period": ErrorDetail(
                    f"El periodo {period.year}-{period.month:02d} está cerrado.",
                    code="period_closed",
                )
            }
        )

    def validate(self, attrs):
        company = self._company()
        instance = self.instance

        entry_date = attrs.get(
            "entry_date",
            getattr(instance, "entry_date", None),
        )
        if entry_date is None:
            raise serializers.ValidationError(
                {"entry_date": "La fecha de la póliza es obligatoria."}
            )

        if instance is not None and instance.fiscal_period.is_closed:
            self._raise_period_closed(instance.fiscal_period)

        period = attrs.get("fiscal_period")
        if period is not None:
            if company is not None and period.company_id != company.pk:
                raise serializers.ValidationError(
                    {
                        "fiscal_period": ErrorDetail(
                            "El periodo fiscal no pertenece a la empresa "
                            "seleccionada.",
                            code="invalid_fiscal_period",
                        )
                    }
                )
            if (
                entry_date.year != period.year
                or entry_date.month != period.month
            ):
                raise serializers.ValidationError(
                    {
                        "entry_date": ErrorDetail(
                            "La fecha de la póliza debe caer dentro del periodo "
                            f"fiscal {period.year}-{period.month:02d}.",
                            code="entry_date_out_of_period",
                        )
                    }
                )
            if period.is_closed:
                self._raise_period_closed(period)
        elif company is not None:
            resolved = get_or_create_period(company, entry_date)
            if resolved.is_closed:
                self._raise_period_closed(resolved)

        if "items" in attrs:
            items = attrs["items"]
        elif instance is not None:
            items = [
                {
                    "debit": item.debit,
                    "credit": item.credit,
                }
                for item in instance.items.all()
            ]
        else:
            items = []

        if len(items) < 2:
            raise serializers.ValidationError(
                {
                    "items": ErrorDetail(
                        "La póliza debe contener al menos dos renglones.",
                        code="invalid_line_amounts",
                    )
                }
            )

        total_debit = sum(
            (
                item.get("debit", Decimal("0.00"))
                if isinstance(item, dict)
                else item.debit
                for item in items
            ),
            Decimal("0.00"),
        )
        total_credit = sum(
            (
                item.get("credit", Decimal("0.00"))
                if isinstance(item, dict)
                else item.credit
                for item in items
            ),
            Decimal("0.00"),
        )

        if total_debit <= Decimal("0.00") or total_credit <= Decimal("0.00"):
            raise serializers.ValidationError(
                {
                    "items": ErrorDetail(
                        "La suma de cargos y abonos debe ser estrictamente "
                        "mayor a cero.",
                        code="unbalanced_entry",
                    )
                }
            )

        if total_debit != total_credit:
            raise serializers.ValidationError(
                {
                    "items": ErrorDetail(
                        "Póliza descuadrada: "
                        f"Cargos (${total_debit:.2f}) != "
                        f"Abonos (${total_credit:.2f}).",
                        code="unbalanced_entry",
                    )
                }
            )

        return attrs


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

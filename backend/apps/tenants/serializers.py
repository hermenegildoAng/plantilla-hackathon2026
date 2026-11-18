"""Serializers for companies and memberships."""

from django.db import transaction
from rest_framework import serializers

from apps.authentication.models import CompanyMembership, User
from apps.tenants.models import Company
from apps.tenants.services import clone_master_sat_catalog


class CompanyBaseSerializer(serializers.ModelSerializer):
    """Shared read-only fields for company responses."""

    tax_regime_display = serializers.CharField(
        source="get_tax_regime_display",
        read_only=True,
    )
    user_role = serializers.SerializerMethodField()

    def get_user_role(self, obj):
        request = self.context.get("request")
        if request is None:
            return None

        membership = getattr(request, "membership", None)
        if membership is not None and membership.company_id == obj.pk:
            return membership.role

        prefetched = getattr(obj, "current_user_memberships", None)
        if prefetched is not None:
            for item in prefetched:
                if item.is_active:
                    return item.role
            return None

        user = getattr(request, "user", None)
        if user is None or not user.is_authenticated:
            return None
        membership = obj.user_memberships.filter(user=user, is_active=True).first()
        return membership.role if membership else None


class CompanyListSerializer(CompanyBaseSerializer):
    """Payload for GET /companies/ (03 §3.2)."""

    class Meta:
        model = Company
        fields = [
            "id",
            "rfc",
            "legal_name",
            "tax_regime",
            "tax_regime_display",
            "currency",
            "user_role",
        ]
        read_only_fields = fields


class CompanyDetailSerializer(CompanyBaseSerializer):
    """Payload for the company detail and PATCH responses."""

    class Meta:
        model = Company
        fields = [
            "id",
            "rfc",
            "legal_name",
            "tax_regime",
            "tax_regime_display",
            "currency",
            "fiscal_year_start",
            "is_active",
            "user_role",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "tax_regime_display",
            "is_active",
            "user_role",
            "created_at",
            "updated_at",
        ]


class CompanyCreateSerializer(serializers.ModelSerializer):
    """Create a company, its PARTNER membership and clone the SAT catalog."""

    class Meta:
        model = Company
        fields = [
            "id",
            "rfc",
            "legal_name",
            "tax_regime",
            "currency",
            "fiscal_year_start",
        ]
        read_only_fields = ["id"]
        extra_kwargs = {
            "fiscal_year_start": {"required": False},
        }

    def validate_rfc(self, value):
        normalized = value.upper().strip()
        if Company.objects.filter(rfc=normalized).exists():
            raise serializers.ValidationError(
                "Ya existe una empresa registrada con este RFC."
            )
        return normalized

    @transaction.atomic
    def create(self, validated_data):
        request = self.context["request"]
        company = Company.objects.create(**validated_data)
        CompanyMembership.objects.create(
            user=request.user,
            company=company,
            role=CompanyMembership.Role.PARTNER,
        )
        # TODO(bloque 3): clone_master_sat_catalog is still a stub.
        clone_master_sat_catalog(company)
        return company


class MembershipSummarySerializer(serializers.ModelSerializer):
    """Company + role shown after login and in GET /auth/me/."""

    company_id = serializers.IntegerField(read_only=True)
    rfc = serializers.CharField(source="company.rfc", read_only=True)
    legal_name = serializers.CharField(source="company.legal_name", read_only=True)
    tax_regime = serializers.CharField(source="company.tax_regime", read_only=True)

    class Meta:
        model = CompanyMembership
        fields = [
            "company_id",
            "rfc",
            "legal_name",
            "tax_regime",
            "role",
        ]
        read_only_fields = fields


class CompanyMembershipSerializer(serializers.ModelSerializer):
    """Membership row returned by GET /companies/{id}/members/."""

    user_id = serializers.IntegerField(read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)
    full_name = serializers.CharField(source="user.full_name", read_only=True)

    class Meta:
        model = CompanyMembership
        fields = [
            "id",
            "user_id",
            "email",
            "full_name",
            "role",
            "is_active",
            "created_at",
        ]
        read_only_fields = fields


class CompanyMembershipCreateSerializer(serializers.Serializer):
    """Add an existing user to the current company [E-22]."""

    email = serializers.EmailField()
    role = serializers.ChoiceField(
        choices=CompanyMembership.Role.choices,
        default=CompanyMembership.Role.ACCOUNTANT,
    )

    def validate(self, attrs):
        email = attrs["email"].strip().lower()
        user = User.objects.filter(email__iexact=email).first()
        if user is None:
            raise serializers.ValidationError(
                {
                    "email": (
                        "No existe un usuario con ese correo electrónico. "
                        "Los usuarios se crean desde el admin o el seed."
                    )
                }
            )

        company = self.context["company"]
        if CompanyMembership.objects.filter(user=user, company=company).exists():
            raise serializers.ValidationError(
                {"email": "El usuario ya pertenece a esta empresa."}
            )

        attrs["email"] = user.email
        attrs["user"] = user
        return attrs

    def create(self, validated_data):
        validated_data.pop("email")
        user = validated_data.pop("user")
        return CompanyMembership.objects.create(
            user=user,
            company=self.context["company"],
            **validated_data,
        )

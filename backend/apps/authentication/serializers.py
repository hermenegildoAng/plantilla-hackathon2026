"""Authentication serializers: JWT login, session payload and logout."""

from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.tokens import RefreshToken

from apps.authentication.models import CompanyMembership, User
from apps.tenants.serializers import MembershipSummarySerializer


def active_memberships(user):
    """Active memberships of a user in active companies."""
    return (
        CompanyMembership.objects.filter(
            user=user,
            is_active=True,
            company__is_active=True,
        )
        .select_related("company")
        .order_by("company__legal_name")
    )


class UserSessionSerializer(serializers.ModelSerializer):
    """User part of the login and /auth/me/ payloads."""

    full_name = serializers.CharField(read_only=True)
    default_company_id = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "full_name",
            "default_company_id",
        ]
        read_only_fields = fields

    def get_default_company_id(self, obj):
        profile = getattr(obj, "profile", None)
        return profile.default_company_id if profile is not None else None


class LoginSerializer(TokenObtainPairSerializer):
    """Validate credentials, add custom claims and hydrate the session."""

    default_error_messages = {
        "no_active_account": "Correo electrónico o contraseña incorrectos.",
    }

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        # simplejwt 5.5 serializes user_id as a string; the API contract (03
        # §1.1) exposes it as an integer.
        token["user_id"] = user.id
        token["email"] = user.email
        token["full_name"] = user.full_name
        token["is_superuser"] = user.is_superuser
        return token

    def validate(self, attrs):
        try:
            data = super().validate(attrs)
        except AuthenticationFailed as exc:
            raise AuthenticationFailed(
                detail="Correo electrónico o contraseña incorrectos.",
                code="authentication_failed",
            ) from exc

        memberships = active_memberships(self.user)
        return {
            "tokens": {
                "access": data["access"],
                "refresh": data["refresh"],
            },
            "user": UserSessionSerializer(self.user).data,
            "memberships": MembershipSummarySerializer(
                memberships,
                many=True,
            ).data,
        }


class LogoutSerializer(serializers.Serializer):
    """Blacklist the refresh token sent on logout."""

    refresh = serializers.CharField()

    def validate_refresh(self, value):
        try:
            self.token = RefreshToken(value)
        except TokenError as exc:
            raise serializers.ValidationError(
                "El token de actualización es inválido o expiró.",
                code="token_not_valid",
            ) from exc
        return value

    def save(self, **kwargs):
        self.token.blacklist()

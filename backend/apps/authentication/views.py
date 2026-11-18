"""Authentication endpoints: login, refresh, logout and me."""

from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from apps.authentication.serializers import (
    LoginSerializer,
    LogoutSerializer,
    UserSessionSerializer,
    active_memberships,
)
from apps.tenants.serializers import MembershipSummarySerializer


class LoginView(TokenObtainPairView):
    """POST /auth/login/ — JWT + user + memberships, 5/min per IP [E-09]."""

    serializer_class = LoginSerializer
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"


class RefreshView(TokenRefreshView):
    """POST /auth/refresh/ — rotate the refresh token and blacklist the old one."""

    permission_classes = [AllowAny]
    authentication_classes = []


class LogoutView(APIView):
    """POST /auth/logout/ — blacklist the provided refresh token."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        response = Response({"detail": "Sesión cerrada correctamente."})
        response.response_message = "Sesión cerrada correctamente."
        return response


class MeView(APIView):
    """GET /auth/me/ — current user and active memberships."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(
            {
                "user": UserSessionSerializer(request.user).data,
                "memberships": MembershipSummarySerializer(
                    active_memberships(request.user),
                    many=True,
                ).data,
            },
            status=status.HTTP_200_OK,
        )

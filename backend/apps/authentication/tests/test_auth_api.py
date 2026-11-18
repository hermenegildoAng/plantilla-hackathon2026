from datetime import timedelta

import pytest
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from apps.authentication.models import CompanyMembership, Profile


pytestmark = pytest.mark.django_db

LOGIN_URL = "/api/v1/auth/login/"
REFRESH_URL = "/api/v1/auth/refresh/"
LOGOUT_URL = "/api/v1/auth/logout/"
ME_URL = "/api/v1/auth/me/"


def login(client, email, password="s3cret-pass"):
    return client.post(LOGIN_URL, {"email": email, "password": password}, format="json")


def test_login_returns_tokens_user_and_memberships(
    api_client, make_user, make_company, make_membership
):
    user = make_user(
        "laura.mendez@despacho.mx",
        first_name="Laura",
        last_name="Méndez",
    )
    company = make_company(
        rfc="CME210514AB9",
        legal_name="Comercializadora Mexicana del Centro",
    )
    make_membership(user, company, CompanyMembership.Role.PARTNER)
    Profile.objects.create(user=user, default_company=company)

    response = login(api_client, user.email)

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    data = body["data"]

    assert set(data["tokens"]) == {"access", "refresh"}
    assert data["user"] == {
        "id": user.id,
        "email": "laura.mendez@despacho.mx",
        "full_name": "Laura Méndez",
        "default_company_id": company.id,
    }
    assert data["memberships"] == [
        {
            "company_id": company.id,
            "rfc": "CME210514AB9",
            "legal_name": "Comercializadora Mexicana del Centro",
            "tax_regime": "601",
            "role": "PARTNER",
        }
    ]

    access = AccessToken(data["tokens"]["access"])
    assert access["user_id"] == user.id
    assert access["email"] == user.email
    assert access["full_name"] == "Laura Méndez"
    assert access["is_superuser"] is False
    assert access.lifetime == timedelta(minutes=30)

    refresh = RefreshToken(data["tokens"]["refresh"])
    assert refresh.lifetime == timedelta(hours=12)


def test_login_without_profile_returns_null_default_company(api_client, make_user):
    user = make_user()

    response = login(api_client, user.email)

    assert response.status_code == 200
    assert response.json()["data"]["user"]["default_company_id"] is None


def test_login_invalid_credentials_returns_spanish_message(api_client, make_user):
    user = make_user()

    response = login(api_client, user.email, password="wrong-password")

    assert response.status_code == 401
    body = response.json()
    assert body["success"] is False
    assert body["errors"][0]["code"] == "authentication_failed"
    assert body["errors"][0]["message"] == (
        "Correo electrónico o contraseña incorrectos."
    )


def test_login_throttles_sixth_attempt_per_minute(api_client, make_user):
    user = make_user()

    for _ in range(5):
        response = login(api_client, user.email, password="wrong-password")
        assert response.status_code == 401

    throttled = login(api_client, user.email)

    assert throttled.status_code == 429
    body = throttled.json()
    assert body["errors"][0]["code"] == "throttled"
    assert body["message"] == "Demasiados intentos."


def test_me_returns_user_and_memberships_without_tenant_header(
    api_client, make_user, make_company, make_membership, authenticate
):
    user = make_user(first_name="Ana", last_name="Ruiz")
    company = make_company()
    make_membership(user, company, CompanyMembership.Role.AUDITOR)
    authenticate(api_client, user)

    response = api_client.get(ME_URL)

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["user"]["email"] == user.email
    assert data["user"]["full_name"] == "Ana Ruiz"
    assert data["memberships"][0]["company_id"] == company.id
    assert data["memberships"][0]["role"] == "AUDITOR"


def test_refresh_rotates_and_blacklists_previous_token(api_client, make_user):
    user = make_user()
    login_data = login(api_client, user.email).json()["data"]
    old_refresh = login_data["tokens"]["refresh"]

    response = api_client.post(REFRESH_URL, {"refresh": old_refresh}, format="json")

    assert response.status_code == 200
    new_tokens = response.json()["data"]
    assert new_tokens["access"]
    assert new_tokens["refresh"] != old_refresh

    reused = api_client.post(REFRESH_URL, {"refresh": old_refresh}, format="json")
    assert reused.status_code == 401
    assert reused.json()["errors"][0]["code"] == "token_not_valid"


def test_logout_blacklists_refresh_token(api_client, make_user, authenticate):
    user = make_user()
    tokens = login(api_client, user.email).json()["data"]["tokens"]
    authenticate(api_client, user)

    response = api_client.post(
        LOGOUT_URL,
        {"refresh": tokens["refresh"]},
        format="json",
    )

    assert response.status_code == 200
    assert response.json()["message"] == "Sesión cerrada correctamente."

    refresh_attempt = api_client.post(
        REFRESH_URL,
        {"refresh": tokens["refresh"]},
        format="json",
    )
    assert refresh_attempt.status_code == 401


def test_logout_requires_authentication(api_client):
    response = api_client.post(
        LOGOUT_URL,
        {"refresh": "whatever"},
        format="json",
    )

    assert response.status_code == 401

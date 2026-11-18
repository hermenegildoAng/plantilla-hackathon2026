import itertools

import pytest
from django.core.cache import cache
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.authentication.models import CompanyMembership, User
from apps.tenants.models import Company


_company_counter = itertools.count(1)


@pytest.fixture(autouse=True)
def clear_throttle_cache():
    """Keep login throttling isolated between tests."""
    cache.clear()
    yield


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def make_user(db):
    def _make_user(email=None, password="s3cret-pass", **extra):
        index = next(_company_counter)
        email = email or f"user{index}@example.com"
        return User.objects.create_user(email, password, **extra)

    return _make_user


@pytest.fixture
def make_company(db):
    def _make_company(**overrides):
        index = next(_company_counter)
        data = {
            "rfc": f"TST200101{index % 100:02d}A",
            "legal_name": f"Empresa de Prueba {index}",
            "tax_regime": Company.TaxRegime.GENERAL_PM,
        }
        data.update(overrides)
        return Company.objects.create(**data)

    return _make_company


@pytest.fixture
def make_membership(db):
    def _make_membership(user, company, role=CompanyMembership.Role.PARTNER, **extra):
        return CompanyMembership.objects.create(
            user=user,
            company=company,
            role=role,
            **extra,
        )

    return _make_membership


@pytest.fixture
def authenticate():
    def _authenticate(client, user):
        token = AccessToken.for_user(user)
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        return client

    return _authenticate


@pytest.fixture
def tenant_user(make_user, make_company, make_membership, authenticate, api_client):
    """Create a user with a role in a company and an authenticated client."""

    def _build(role=CompanyMembership.Role.PARTNER, **company_overrides):
        user = make_user()
        company = make_company(**company_overrides)
        membership = make_membership(user, company, role)
        authenticate(api_client, user)
        return user, company, membership, api_client

    return _build

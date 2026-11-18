import pytest

from apps.authentication.models import CompanyMembership
from apps.tenants.models import Company


pytestmark = pytest.mark.django_db

COMPANIES_URL = "/api/v1/companies/"


def company_url(company, suffix=""):
    return f"{COMPANIES_URL}{company.id}/{suffix}"


def headers(company):
    return {"HTTP_X_COMPANY_ID": str(company.id)}


def create_payload(**overrides):
    data = {
        "rfc": "GARC850912H10",
        "legal_name": "Carlos García Rodríguez",
        "tax_regime": "626",
        "currency": "MXN",
    }
    data.update(overrides)
    return data


@pytest.mark.parametrize(
    "role,can_manage",
    [
        (CompanyMembership.Role.PARTNER, True),
        (CompanyMembership.Role.ACCOUNTANT, False),
        (CompanyMembership.Role.AUDITOR, False),
        (CompanyMembership.Role.CLIENT, False),
    ],
)
def test_company_permission_matrix(role, can_manage, tenant_user, make_user):
    user, company, _membership, client = tenant_user(role=role)
    other_user = make_user()

    list_response = client.get(COMPANIES_URL)
    assert list_response.status_code == 200
    results = list_response.json()["data"]["results"]
    assert results[0]["user_role"] == role

    detail_response = client.get(company_url(company), **headers(company))
    assert detail_response.status_code == 200
    assert detail_response.json()["data"]["id"] == company.id

    patch_response = client.patch(
        company_url(company),
        {"legal_name": "Razón social actualizada"},
        format="json",
        **headers(company),
    )
    assert patch_response.status_code == (200 if can_manage else 403)

    members_get = client.get(company_url(company, "members/"), **headers(company))
    assert members_get.status_code == (200 if can_manage else 403)

    members_post = client.post(
        company_url(company, "members/"),
        {"email": other_user.email, "role": "AUDITOR"},
        format="json",
        **headers(company),
    )
    assert members_post.status_code == (201 if can_manage else 403)

    create_response = client.post(
        COMPANIES_URL,
        create_payload(),
        format="json",
    )
    assert create_response.status_code == (201 if can_manage else 403)

    delete_response = client.delete(company_url(company), **headers(company))
    assert delete_response.status_code == (204 if can_manage else 403)


def test_partner_create_company_assigns_partner_and_calls_catalog_clone(
    tenant_user, monkeypatch
):
    user, _company, _membership, client = tenant_user()
    calls = {}

    def fake_clone(company):
        calls["company"] = company

    monkeypatch.setattr(
        "apps.tenants.serializers.clone_master_sat_catalog",
        fake_clone,
    )

    response = client.post(
        COMPANIES_URL,
        create_payload(),
        format="json",
    )

    assert response.status_code == 201
    data = response.json()["data"]
    assert data["rfc"] == "GARC850912H10"
    assert data["tax_regime"] == "626"
    assert data["user_role"] == "PARTNER"

    created = Company.objects.get(rfc="GARC850912H10")
    membership = CompanyMembership.objects.get(user=user, company=created)
    assert membership.role == CompanyMembership.Role.PARTNER
    assert calls["company"] == created

    list_response = client.get(COMPANIES_URL)
    company_ids = {item["id"] for item in list_response.json()["data"]["results"]}
    assert company_ids == {_company.id, created.id}


def test_superuser_without_membership_can_create_company(api_client, make_user, authenticate):
    admin = make_user(is_staff=True, is_superuser=True)
    authenticate(api_client, admin)

    response = api_client.post(COMPANIES_URL, create_payload(), format="json")

    assert response.status_code == 201
    created = Company.objects.get(rfc="GARC850912H10")
    assert CompanyMembership.objects.filter(
        user=admin,
        company=created,
        role=CompanyMembership.Role.PARTNER,
    ).exists()


def test_company_list_without_tenant_header_only_returns_own_companies(
    tenant_user, make_company
):
    _user, company, _membership, client = tenant_user()
    make_company()  # company without membership for this user

    response = client.get(COMPANIES_URL)

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["count"] == 1
    assert [item["id"] for item in data["results"]] == [company.id]


@pytest.mark.parametrize("invalid_header", ["abc", "0", "-5", "1.5"])
def test_operational_route_rejects_invalid_tenant_header(
    invalid_header, tenant_user
):
    _user, company, _membership, client = tenant_user()

    response = client.get(
        company_url(company),
        HTTP_X_COMPANY_ID=invalid_header,
    )

    assert response.status_code == 400
    body = response.json()
    assert body["errors"][0]["code"] == "missing_or_invalid_tenant_header"
    assert body["errors"][0]["field"] == "X-Company-ID"


def test_operational_route_without_tenant_header_returns_400(tenant_user):
    _user, company, _membership, client = tenant_user()

    response = client.get(company_url(company))

    assert response.status_code == 400
    body = response.json()
    assert body["message"] == "Contexto de empresa inválido."
    assert body["errors"][0]["code"] == "missing_or_invalid_tenant_header"


def test_foreign_company_header_returns_403(tenant_user, make_company):
    _user, _company, _membership, client = tenant_user()
    foreign_company = make_company()

    response = client.get(
        company_url(foreign_company),
        HTTP_X_COMPANY_ID=str(foreign_company.id),
    )

    assert response.status_code == 403
    body = response.json()
    assert body["errors"][0]["code"] == "tenant_access_denied"
    assert body["message"] == "Acceso denegado a la empresa."


def test_inactive_membership_returns_403(tenant_user, make_membership, make_company):
    user, _company, _membership, client = tenant_user()
    inactive_company = make_company()
    make_membership(
        user,
        inactive_company,
        CompanyMembership.Role.PARTNER,
        is_active=False,
    )

    response = client.get(
        company_url(inactive_company),
        HTTP_X_COMPANY_ID=str(inactive_company.id),
    )

    assert response.status_code == 403
    assert response.json()["errors"][0]["code"] == "tenant_access_denied"


def test_other_tenant_company_id_returns_404_not_403(tenant_user, make_company, make_membership):
    user, company_a, _membership, client = tenant_user()
    company_b = make_company()
    make_membership(user, company_b, CompanyMembership.Role.PARTNER)

    detail = client.get(company_url(company_b), **headers(company_a))
    assert detail.status_code == 404
    assert detail.json()["errors"][0]["code"] == "not_found"

    members = client.get(company_url(company_b, "members/"), **headers(company_a))
    assert members.status_code == 404
    assert members.json()["errors"][0]["code"] == "not_found"

    patch = client.patch(
        company_url(company_b),
        {"legal_name": "Intento cruzado"},
        format="json",
        **headers(company_a),
    )
    assert patch.status_code == 404


def test_user_with_two_companies_and_different_roles(
    tenant_user, make_company, make_membership, api_client
):
    user, company_a, _membership, client = tenant_user(
        role=CompanyMembership.Role.PARTNER
    )
    company_b = make_company()
    make_membership(user, company_b, CompanyMembership.Role.ACCOUNTANT)

    login_response = api_client.post(
        "/api/v1/auth/login/",
        {"email": user.email, "password": "s3cret-pass"},
        format="json",
    )
    assert login_response.status_code == 200
    roles = {
        item["company_id"]: item["role"]
        for item in login_response.json()["data"]["memberships"]
    }
    assert roles == {
        company_a.id: "PARTNER",
        company_b.id: "ACCOUNTANT",
    }

    list_response = client.get(COMPANIES_URL)
    listed = {
        item["id"]: item["user_role"]
        for item in list_response.json()["data"]["results"]
    }
    assert listed == {
        company_a.id: "PARTNER",
        company_b.id: "ACCOUNTANT",
    }

    assert client.get(company_url(company_a), **headers(company_a)).status_code == 200
    assert client.get(company_url(company_b), **headers(company_b)).status_code == 200

    # PARTNER in A can manage members; ACCOUNTANT in B cannot.
    assert (
        client.get(company_url(company_a, "members/"), **headers(company_a)).status_code
        == 200
    )
    assert (
        client.get(company_url(company_b, "members/"), **headers(company_b)).status_code
        == 403
    )


def test_partner_can_add_existing_user_as_member(tenant_user, make_user):
    _user, company, _membership, client = tenant_user()
    target = make_user("auditora@despacho.mx", first_name="Elena", last_name="Soto")

    response = client.post(
        company_url(company, "members/"),
        {"email": target.email, "role": "AUDITOR"},
        format="json",
        **headers(company),
    )

    assert response.status_code == 201
    data = response.json()["data"]
    assert data["email"] == "auditora@despacho.mx"
    assert data["full_name"] == "Elena Soto"
    assert data["role"] == "AUDITOR"
    assert data["is_active"] is True
    assert CompanyMembership.objects.filter(user=target, company=company).exists()

    list_response = client.get(company_url(company, "members/"), **headers(company))
    assert list_response.status_code == 200
    assert list_response.json()["data"]["count"] == 2


def test_cannot_add_unknown_user_or_duplicate_membership(tenant_user, make_user):
    _user, company, _membership, client = tenant_user()
    existing_member = make_user()
    CompanyMembership.objects.create(
        user=existing_member,
        company=company,
        role=CompanyMembership.Role.ACCOUNTANT,
    )

    unknown = client.post(
        company_url(company, "members/"),
        {"email": "nadie@despacho.mx", "role": "AUDITOR"},
        format="json",
        **headers(company),
    )
    assert unknown.status_code == 400
    assert "No existe un usuario" in unknown.json()["errors"][0]["message"]

    duplicate = client.post(
        company_url(company, "members/"),
        {"email": existing_member.email, "role": "AUDITOR"},
        format="json",
        **headers(company),
    )
    assert duplicate.status_code == 400
    assert "ya pertenece" in duplicate.json()["errors"][0]["message"]


def test_delete_company_is_soft_delete(tenant_user):
    _user, company, _membership, client = tenant_user()

    response = client.delete(company_url(company), **headers(company))

    assert response.status_code == 204
    company.refresh_from_db()
    assert company.is_active is False

    list_response = client.get(COMPANIES_URL)
    assert list_response.json()["data"]["count"] == 0

    detail = client.get(company_url(company), **headers(company))
    assert detail.status_code == 403
    assert detail.json()["errors"][0]["code"] == "tenant_access_denied"


def test_client_role_can_only_read_its_company(tenant_user):
    _user, company, _membership, client = tenant_user(
        role=CompanyMembership.Role.CLIENT
    )

    assert client.get(company_url(company), **headers(company)).status_code == 200
    assert client.get(company_url(company, "members/"), **headers(company)).status_code == 403
    assert (
        client.patch(
            company_url(company),
            {"legal_name": "No permitido"},
            format="json",
            **headers(company),
        ).status_code
        == 403
    )

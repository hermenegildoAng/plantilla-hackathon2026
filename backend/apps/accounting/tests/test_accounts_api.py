import pytest

from apps.accounting.models import AccountCatalog
from apps.accounting.services import clone_master_sat_catalog
from apps.authentication.models import CompanyMembership
from apps.tenants.models import Company


pytestmark = pytest.mark.django_db

ACCOUNTS_URL = "/api/v1/accounts/"
COMPANIES_URL = "/api/v1/companies/"


def headers(company):
    return {"HTTP_X_COMPANY_ID": str(company.id)}


def account_url(account):
    return f"{ACCOUNTS_URL}{account.id}/"


def payload(**overrides):
    data = {
        "code": "102.01.004",
        "sat_group_code": "102.01",
        "name": "HSBC cuenta 5555555555",
        "account_type": "ASSET",
        "nature": "DEBIT",
        "is_selectable": True,
    }
    data.update(overrides)
    return data


@pytest.mark.parametrize(
    "role,expected_status",
    [
        (CompanyMembership.Role.PARTNER, 200),
        (CompanyMembership.Role.ACCOUNTANT, 200),
        (CompanyMembership.Role.AUDITOR, 200),
        (CompanyMembership.Role.CLIENT, 403),
    ],
)
def test_accounts_list_permission_matrix(
    role, expected_status, tenant_user
):
    _user, company, _membership, client = tenant_user(role=role)
    clone_master_sat_catalog(company)

    response = client.get(ACCOUNTS_URL, **headers(company))

    assert response.status_code == expected_status
    if expected_status == 200:
        body = response.json()["data"]
        assert body["count"] == 80


def test_accounts_tree_returns_nested_hierarchy(tenant_user):
    _user, company, _membership, client = tenant_user()
    clone_master_sat_catalog(company)

    response = client.get(
        ACCOUNTS_URL,
        {"tree": "true"},
        **headers(company),
    )

    assert response.status_code == 200
    roots = response.json()["data"]["results"]
    root_codes = {item["code"] for item in roots}
    assert root_codes == {"100", "200", "300", "400", "500", "600", "800"}

    assets = next(item for item in roots if item["code"] == "100")
    current_assets = next(
        child for child in assets["children"] if child["code"] == "100.01"
    )
    banks = next(
        child for child in current_assets["children"] if child["code"] == "102"
    )
    national_banks = next(
        child for child in banks["children"] if child["code"] == "102.01"
    )
    assert {child["code"] for child in national_banks["children"]} == {
        "102.01.001",
        "102.01.002",
        "102.01.003",
    }


def test_accounts_filters_by_search_and_type(tenant_user):
    _user, company, _membership, client = tenant_user()
    clone_master_sat_catalog(company)

    search_response = client.get(
        ACCOUNTS_URL,
        {"search": "Honorarios"},
        **headers(company),
    )
    assert search_response.status_code == 200
    results = search_response.json()["data"]["results"]
    assert results
    assert all("Honorarios" in item["name"] for item in results)

    type_response = client.get(
        ACCOUNTS_URL,
        {"account_type": "LIABILITY", "is_selectable": "true"},
        **headers(company),
    )
    assert type_response.status_code == 200
    type_results = type_response.json()["data"]["results"]
    assert type_results
    assert {item["account_type"] for item in type_results} == {"LIABILITY"}
    assert all(item["is_selectable"] is True for item in type_results)


def test_partner_can_create_account_in_own_company(tenant_user):
    _user, company, _membership, client = tenant_user()
    clone_master_sat_catalog(company)
    parent = AccountCatalog.objects.get(company=company, code="102.01")

    response = client.post(
        ACCOUNTS_URL,
        payload(parent=parent.id),
        format="json",
        **headers(company),
    )

    assert response.status_code == 201
    data = response.json()["data"]
    assert data["code"] == "102.01.004"
    created = AccountCatalog.objects.get(pk=data["id"])
    assert created.company == company
    assert created.parent == parent


def test_duplicate_code_is_rejected_in_same_company(tenant_user):
    _user, company, _membership, client = tenant_user()
    clone_master_sat_catalog(company)
    parent = AccountCatalog.objects.get(company=company, code="102.01")
    client.post(
        ACCOUNTS_URL,
        payload(parent=parent.id),
        format="json",
        **headers(company),
    )

    response = client.post(
        ACCOUNTS_URL,
        payload(parent=parent.id, name="Otra cuenta"),
        format="json",
        **headers(company),
    )

    assert response.status_code == 400
    assert response.json()["errors"][0]["field"] == "code"
    assert "código" in response.json()["errors"][0]["message"].lower()


def test_parent_must_belong_to_same_company(tenant_user, make_company):
    _user, company, _membership, client = tenant_user()
    clone_master_sat_catalog(company)
    foreign_company = make_company()
    foreign_parent = AccountCatalog.objects.create(
        company=foreign_company,
        code="900",
        sat_group_code="900",
        name="Cuenta de otra empresa",
        account_type=AccountCatalog.AccountType.ASSET,
        nature=AccountCatalog.Nature.DEBIT,
    )

    response = client.post(
        ACCOUNTS_URL,
        payload(parent=foreign_parent.id),
        format="json",
        **headers(company),
    )

    assert response.status_code == 400
    assert response.json()["errors"][0]["field"] == "parent"
    assert "misma empresa" in response.json()["errors"][0]["message"]


@pytest.mark.parametrize(
    "role,expected_status",
    [
        (CompanyMembership.Role.PARTNER, 201),
        (CompanyMembership.Role.ACCOUNTANT, 403),
        (CompanyMembership.Role.AUDITOR, 403),
        (CompanyMembership.Role.CLIENT, 403),
    ],
)
def test_account_create_permission_matrix(role, expected_status, tenant_user):
    _user, company, _membership, client = tenant_user(role=role)
    clone_master_sat_catalog(company)
    parent = AccountCatalog.objects.get(company=company, code="102.01")

    response = client.post(
        ACCOUNTS_URL,
        payload(parent=parent.id),
        format="json",
        **headers(company),
    )

    assert response.status_code == expected_status


def test_accountant_can_only_patch_name(tenant_user):
    _user, company, _membership, client = tenant_user(
        role=CompanyMembership.Role.ACCOUNTANT
    )
    clone_master_sat_catalog(company)
    account = AccountCatalog.objects.get(company=company, code="102.01.001")

    name_response = client.patch(
        account_url(account),
        {"name": "BBVA Bancomer cuenta principal"},
        format="json",
        **headers(company),
    )
    assert name_response.status_code == 200
    account.refresh_from_db()
    assert account.name == "BBVA Bancomer cuenta principal"

    deactivate_response = client.patch(
        account_url(account),
        {"is_active": False},
        format="json",
        **headers(company),
    )
    assert deactivate_response.status_code == 403
    assert "solo puede modificar el nombre" in deactivate_response.json()[
        "errors"
    ][0]["message"]


def test_partner_can_deactivate_account(tenant_user):
    _user, company, _membership, client = tenant_user()
    clone_master_sat_catalog(company)
    account = AccountCatalog.objects.get(company=company, code="102.01.001")

    response = client.patch(
        account_url(account),
        {"is_active": False},
        format="json",
        **headers(company),
    )

    assert response.status_code == 200
    account.refresh_from_db()
    assert account.is_active is False


@pytest.mark.parametrize(
    "role",
    [CompanyMembership.Role.AUDITOR, CompanyMembership.Role.CLIENT],
)
def test_auditor_and_client_cannot_patch_accounts(role, tenant_user):
    _user, company, _membership, client = tenant_user(role=role)
    clone_master_sat_catalog(company)
    account = AccountCatalog.objects.get(company=company, code="102.01.001")

    response = client.patch(
        account_url(account),
        {"name": "Intento de cambio"},
        format="json",
        **headers(company),
    )

    assert response.status_code == 403


def test_company_creation_clones_the_sat_catalog(tenant_user):
    _user, _company, _membership, client = tenant_user()

    response = client.post(
        COMPANIES_URL,
        {
            "rfc": "ABC010101AB1",
            "legal_name": "Empresa Nueva del Catálogo",
            "tax_regime": "601",
            "currency": "MXN",
        },
        format="json",
    )

    assert response.status_code == 201
    created = Company.objects.get(rfc="ABC010101AB1")
    assert AccountCatalog.objects.filter(company=created).count() == 80

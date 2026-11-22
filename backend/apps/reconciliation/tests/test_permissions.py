import pytest

from apps.authentication.models import CompanyMembership
from apps.reconciliation.tests.helpers import (
    csv_upload,
    headers,
    make_entry,
    make_movement,
    period_for,
    prepare_company,
)


pytestmark = pytest.mark.django_db

MOVEMENTS_URL = "/api/v1/reconciliation/movements/"
IMPORT_URL = "/api/v1/reconciliation/movements/import/"
TRIAL_BALANCE_URL = "/api/v1/reports/trial-balance/"


def _member(company, make_user, make_membership, authenticate, api_client, role):
    user = make_user()
    make_membership(user, company, role=role)
    authenticate(api_client, user)
    return user


def test_client_cannot_read_reconciliation(
    tenant_user,
    make_user,
    make_membership,
    authenticate,
    api_client,
):
    _user, company, _membership, _client = tenant_user()
    prepare_company(company)
    movement = make_movement(company)
    _member(
        company,
        make_user,
        make_membership,
        authenticate,
        api_client,
        CompanyMembership.Role.CLIENT,
    )

    listed = api_client.get(MOVEMENTS_URL, **headers(company))
    suggested = api_client.get(
        f"{MOVEMENTS_URL}{movement.pk}/suggestions/",
        **headers(company),
    )

    assert listed.status_code == 403
    assert suggested.status_code == 403


def test_auditor_reads_but_cannot_write(
    tenant_user,
    make_user,
    make_membership,
    authenticate,
    api_client,
):
    user, company, _membership, _client = tenant_user()
    prepare_company(company)
    period = period_for(company)
    entry = make_entry(company, user, period)
    movement = make_movement(company)

    _member(
        company,
        make_user,
        make_membership,
        authenticate,
        api_client,
        CompanyMembership.Role.AUDITOR,
    )

    listed = api_client.get(MOVEMENTS_URL, **headers(company))
    suggested = api_client.get(
        f"{MOVEMENTS_URL}{movement.pk}/suggestions/",
        **headers(company),
    )
    trial_balance = api_client.get(
        f"{TRIAL_BALANCE_URL}?period={period.pk}",
        **headers(company),
    )
    imported = api_client.post(
        IMPORT_URL,
        {
            "file": csv_upload(
                [("2026-05-10", "REF", "Movimiento", "100.00", "")]
            )
        },
        format="multipart",
        **headers(company),
    )
    matched = api_client.post(
        f"{MOVEMENTS_URL}{movement.pk}/match/",
        {"entry_id": entry.pk},
        format="json",
        **headers(company),
    )
    unmatched = api_client.post(
        f"{MOVEMENTS_URL}{movement.pk}/unmatch/",
        {},
        format="json",
        **headers(company),
    )

    assert listed.status_code == 200
    assert suggested.status_code == 200
    assert trial_balance.status_code == 200
    assert imported.status_code == 403
    assert matched.status_code == 403
    assert unmatched.status_code == 403


def test_accountant_can_import_match_and_unmatch(
    tenant_user,
    make_user,
    make_membership,
    authenticate,
    api_client,
):
    user, company, _membership, _client = tenant_user()
    prepare_company(company)
    period = period_for(company)
    entry = make_entry(company, user, period)
    movement = make_movement(company)

    _member(
        company,
        make_user,
        make_membership,
        authenticate,
        api_client,
        CompanyMembership.Role.ACCOUNTANT,
    )

    imported = api_client.post(
        IMPORT_URL,
        {
            "file": csv_upload(
                [("2026-05-10", "REF", "Movimiento", "100.00", "")]
            )
        },
        format="multipart",
        **headers(company),
    )
    matched = api_client.post(
        f"{MOVEMENTS_URL}{movement.pk}/match/",
        {"entry_id": entry.pk},
        format="json",
        **headers(company),
    )
    unmatched = api_client.post(
        f"{MOVEMENTS_URL}{movement.pk}/unmatch/",
        {},
        format="json",
        **headers(company),
    )

    assert imported.status_code == 200
    assert matched.status_code == 200
    assert unmatched.status_code == 200


def test_client_cannot_match_or_import(
    tenant_user,
    make_user,
    make_membership,
    authenticate,
    api_client,
):
    user, company, _membership, _client = tenant_user()
    prepare_company(company)
    period = period_for(company)
    entry = make_entry(company, user, period)
    movement = make_movement(company)

    _member(
        company,
        make_user,
        make_membership,
        authenticate,
        api_client,
        CompanyMembership.Role.CLIENT,
    )

    matched = api_client.post(
        f"{MOVEMENTS_URL}{movement.pk}/match/",
        {"entry_id": entry.pk},
        format="json",
        **headers(company),
    )
    imported = api_client.post(
        IMPORT_URL,
        {
            "file": csv_upload(
                [("2026-05-10", "REF", "Movimiento", "100.00", "")]
            )
        },
        format="multipart",
        **headers(company),
    )

    assert matched.status_code == 403
    assert imported.status_code == 403

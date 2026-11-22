from datetime import date

import pytest

from apps.accounting.services import close_period
from apps.reconciliation.models import BankMovement
from apps.reconciliation.tests.helpers import (
    headers,
    make_document,
    make_entry,
    make_movement,
    period_for,
    prepare_company,
)


pytestmark = pytest.mark.django_db

MOVEMENTS_URL = "/api/v1/reconciliation/movements/"


def test_suggestions_rank_exact_amount_and_near_date_first(tenant_user):
    user, company, _membership, client = tenant_user()
    prepare_company(company)
    period = period_for(company)
    entry = make_entry(
        company,
        user,
        period,
        amount="1000.00",
        entry_date=date(2026, 5, 15),
        concept="Cobro cliente",
    )
    movement = make_movement(
        company,
        movement_date=date(2026, 5, 17),
        amount="1000.00",
        reference="REF-001",
    )

    response = client.get(
        f"{MOVEMENTS_URL}{movement.pk}/suggestions/",
        **headers(company),
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["count"] >= 1
    first = data["candidates"][0]
    assert first["kind"] == "entry"
    assert first["id"] == entry.pk
    assert first["amount_exact"] is True
    assert first["date_days"] == 2
    assert first["score"] == 59


def test_suggestions_ignore_entries_outside_date_window(tenant_user):
    user, company, _membership, client = tenant_user()
    prepare_company(company)
    period = period_for(company)
    make_entry(
        company,
        user,
        period,
        amount="1000.00",
        entry_date=date(2026, 5, 10),
    )
    movement = make_movement(
        company,
        movement_date=date(2026, 5, 15),
        amount="1000.00",
    )

    response = client.get(
        f"{MOVEMENTS_URL}{movement.pk}/suggestions/",
        **headers(company),
    )

    assert response.status_code == 200
    assert response.json()["data"]["candidates"] == []


def test_suggestions_match_by_reference(tenant_user):
    user, company, _membership, client = tenant_user()
    prepare_company(company)
    period = period_for(company)
    entry = make_entry(
        company,
        user,
        period,
        amount="1000.00",
        entry_date=date(2026, 5, 15),
    )
    movement = make_movement(
        company,
        movement_date=date(2026, 5, 15),
        amount="999.00",
        reference=entry.folio,
    )

    response = client.get(
        f"{MOVEMENTS_URL}{movement.pk}/suggestions/",
        **headers(company),
    )

    candidate = response.json()["data"]["candidates"][0]
    assert candidate["kind"] == "entry"
    assert candidate["reference_match"] is True
    assert candidate["amount_exact"] is False


def test_suggestions_match_document_by_rfc(tenant_user):
    user, company, _membership, client = tenant_user()
    prepare_company(company)
    period = period_for(company)
    document = make_document(
        company,
        period,
        user,
        issuer_rfc="CNO200101AB9",
        total="1160.00",
        issue_date=date(2026, 5, 15),
    )
    movement = make_movement(
        company,
        movement_date=date(2026, 5, 15),
        amount="500.00",
        reference="SPEI",
        description="Pago RFC CNO200101AB9",
    )

    response = client.get(
        f"{MOVEMENTS_URL}{movement.pk}/suggestions/",
        **headers(company),
    )

    candidates = response.json()["data"]["candidates"]
    assert candidates
    document_candidate = next(
        candidate
        for candidate in candidates
        if candidate["kind"] == "document"
    )
    assert document_candidate["id"] == document.pk
    assert document_candidate["rfc_match"] is True


def test_match_entry_then_unmatch(tenant_user):
    user, company, _membership, client = tenant_user()
    prepare_company(company)
    period = period_for(company)
    entry = make_entry(company, user, period, amount="1000.00")
    movement = make_movement(company, amount="1000.00")

    matched = client.post(
        f"{MOVEMENTS_URL}{movement.pk}/match/",
        {"entry_id": entry.pk},
        format="json",
        **headers(company),
    )

    assert matched.status_code == 200
    data = matched.json()["data"]
    assert data["status"] == BankMovement.Status.RECONCILED
    assert data["entry"] == entry.pk
    assert data["entry_folio"] == entry.folio
    assert data["document"] is None

    unmatched = client.post(
        f"{MOVEMENTS_URL}{movement.pk}/unmatch/",
        {},
        format="json",
        **headers(company),
    )

    assert unmatched.status_code == 200
    data = unmatched.json()["data"]
    assert data["status"] == BankMovement.Status.PENDING
    assert data["entry"] is None
    assert data["document"] is None


def test_match_document_keeps_entry_link(tenant_user):
    user, company, _membership, client = tenant_user()
    prepare_company(company)
    period = period_for(company)
    entry = make_entry(company, user, period, amount="1000.00")
    document = make_document(company, period, user)
    movement = make_movement(company, amount="1000.00")

    client.post(
        f"{MOVEMENTS_URL}{movement.pk}/match/",
        {"entry_id": entry.pk},
        format="json",
        **headers(company),
    )
    response = client.post(
        f"{MOVEMENTS_URL}{movement.pk}/match/",
        {"document_id": document.pk},
        format="json",
        **headers(company),
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["status"] == BankMovement.Status.RECONCILED
    assert data["entry"] == entry.pk
    assert data["document"] == document.pk


@pytest.mark.parametrize("payload", [{}, {"entry_id": 1, "document_id": 1}])
def test_match_requires_exactly_one_target(tenant_user, payload):
    _user, company, _membership, client = tenant_user()
    prepare_company(company)
    movement = make_movement(company)

    response = client.post(
        f"{MOVEMENTS_URL}{movement.pk}/match/",
        payload,
        format="json",
        **headers(company),
    )

    assert response.status_code == 400
    assert response.json()["errors"][0]["code"] == "invalid_match_target"


def test_match_rejects_foreign_entry(tenant_user, make_company):
    user, company, _membership, client = tenant_user()
    prepare_company(company)
    period = period_for(company)
    other_company = make_company()
    prepare_company(other_company)
    other_period = period_for(other_company)
    foreign_entry = make_entry(other_company, user, other_period)
    movement = make_movement(company)

    response = client.post(
        f"{MOVEMENTS_URL}{movement.pk}/match/",
        {"entry_id": foreign_entry.pk},
        format="json",
        **headers(company),
    )

    assert response.status_code == 400
    assert response.json()["errors"][0]["code"] == "invalid_entry"


def test_closed_period_blocks_match_and_unmatch(tenant_user):
    user, company, _membership, client = tenant_user()
    prepare_company(company)
    period = period_for(company)
    entry = make_entry(company, user, period, amount="1000.00")
    movement = make_movement(company, amount="1000.00")

    client.post(
        f"{MOVEMENTS_URL}{movement.pk}/match/",
        {"entry_id": entry.pk},
        format="json",
        **headers(company),
    )
    close_period(period, user=user)

    blocked_match = client.post(
        f"{MOVEMENTS_URL}{movement.pk}/match/",
        {"entry_id": entry.pk},
        format="json",
        **headers(company),
    )
    blocked_unmatch = client.post(
        f"{MOVEMENTS_URL}{movement.pk}/unmatch/",
        {},
        format="json",
        **headers(company),
    )

    for response in (blocked_match, blocked_unmatch):
        assert response.status_code == 400
        assert response.json()["errors"][0]["code"] == "period_closed"


def test_list_filters_by_status(tenant_user):
    _user, company, _membership, client = tenant_user()
    prepare_company(company)
    pending = make_movement(company, reference="PEND")
    reconciled = make_movement(company, reference="CONC")
    reconciled.status = BankMovement.Status.RECONCILED
    reconciled.save(update_fields=["status"])

    response = client.get(
        f"{MOVEMENTS_URL}?status=RECONCILED",
        **headers(company),
    )

    assert response.status_code == 200
    results = response.json()["data"]["results"]
    assert [row["id"] for row in results] == [reconciled.pk]
    assert pending.pk not in [row["id"] for row in results]

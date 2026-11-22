import pytest

from apps.accounting.services import close_period
from apps.reconciliation.models import BankMovement
from apps.reconciliation.tests.helpers import (
    CSV_HEADER,
    csv_upload,
    headers,
    period_for,
)


pytestmark = pytest.mark.django_db

IMPORT_URL = "/api/v1/reconciliation/movements/import/"
LIST_URL = "/api/v1/reconciliation/movements/"


def test_import_valid_csv_returns_summary_and_strings(tenant_user):
    _user, company, _membership, client = tenant_user()
    upload = csv_upload(
        [
            ("2026-05-10", "REF-1", "Depósito nómina", "1500.00", ""),
            ("2026-05-11", "REF-2", "Pago proveedor", "", "250.50"),
        ]
    )

    response = client.post(
        IMPORT_URL,
        {"file": upload},
        format="multipart",
        **headers(company),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["summary"] == {
        "imported": 2,
        "skipped_duplicates": 0,
        "invalid": 0,
    }
    assert body["data"]["invalid_rows"] == []
    assert BankMovement.objects.filter(company=company).count() == 2

    listed = client.get(LIST_URL, **headers(company))
    assert listed.status_code == 200
    results = listed.json()["data"]["results"]
    assert results[0]["deposit"] in {"1500.00", "0.00"}
    for row in results:
        assert isinstance(row["deposit"], str)
        assert isinstance(row["withdrawal"], str)


def test_import_is_idempotent_by_row_hash(tenant_user):
    _user, company, _membership, client = tenant_user()
    rows = [
        ("2026-05-10", "REF-1", "Depósito nómina", "1500.00", ""),
        ("2026-05-11", "REF-2", "Pago proveedor", "", "250.50"),
    ]

    first = client.post(
        IMPORT_URL,
        {"file": csv_upload(rows)},
        format="multipart",
        **headers(company),
    )
    second = client.post(
        IMPORT_URL,
        {"file": csv_upload(rows)},
        format="multipart",
        **headers(company),
    )

    assert first.json()["data"]["summary"]["imported"] == 2
    assert second.json()["data"]["summary"] == {
        "imported": 0,
        "skipped_duplicates": 2,
        "invalid": 0,
    }
    assert BankMovement.objects.filter(company=company).count() == 2


def test_duplicate_rows_inside_same_file_are_skipped(tenant_user):
    _user, company, _membership, client = tenant_user()
    row = ("2026-05-10", "REF-1", "Depósito nómina", "1500.00", "")

    response = client.post(
        IMPORT_URL,
        {"file": csv_upload([row, row])},
        format="multipart",
        **headers(company),
    )

    assert response.status_code == 200
    assert response.json()["data"]["summary"] == {
        "imported": 1,
        "skipped_duplicates": 1,
        "invalid": 0,
    }


def test_invalid_rows_are_reported_with_file_row_number(tenant_user):
    _user, company, _membership, client = tenant_user()
    upload = csv_upload(
        [
            ("2026-05-10", "REF-1", "Válido", "1000.00", ""),
            ("2026-05-11", "REF-2", "Ambos montos", "100.00", "50.00"),
            ("fecha-mala", "REF-3", "Fecha inválida", "10.00", ""),
            ("2026-05-12", "REF-4", "Cero", "0.00", "0.00"),
        ]
    )

    response = client.post(
        IMPORT_URL,
        {"file": upload},
        format="multipart",
        **headers(company),
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["summary"] == {
        "imported": 1,
        "skipped_duplicates": 0,
        "invalid": 3,
    }
    invalid = {row["row"]: row for row in data["invalid_rows"]}
    assert invalid[3]["code"] == "deposit_and_withdrawal"
    assert invalid[4]["code"] == "invalid_date"
    assert invalid[5]["code"] == "zero_amount"
    assert BankMovement.objects.filter(company=company).count() == 1


def test_import_rejects_wrong_header(tenant_user):
    _user, company, _membership, client = tenant_user()
    upload = csv_upload(
        [("2026-05-10", "REF-1", "Depósito", "1000.00", "")],
        header="fecha,referencia,concepto,deposito,retiro\n",
    )

    response = client.post(
        IMPORT_URL,
        {"file": upload},
        format="multipart",
        **headers(company),
    )

    assert response.status_code == 400
    assert response.json()["errors"][0]["code"] == "invalid_csv_header"
    assert BankMovement.objects.filter(company=company).count() == 0


def test_import_rejects_rows_in_closed_period(tenant_user):
    user, company, _membership, client = tenant_user()
    period = period_for(company)
    close_period(period, user=user)

    upload = csv_upload(
        [("2026-05-10", "REF-1", "Periodo cerrado", "1000.00", "")]
    )
    response = client.post(
        IMPORT_URL,
        {"file": upload},
        format="multipart",
        **headers(company),
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["summary"] == {
        "imported": 0,
        "skipped_duplicates": 0,
        "invalid": 1,
    }
    assert data["invalid_rows"][0]["row"] == 2
    assert data["invalid_rows"][0]["code"] == "period_closed"
    assert BankMovement.objects.filter(company=company).count() == 0


def test_import_requires_a_csv_file(tenant_user):
    _user, company, _membership, client = tenant_user()
    upload = csv_upload([], header=CSV_HEADER)
    upload.name = "movimientos.txt"

    response = client.post(
        IMPORT_URL,
        {"file": upload},
        format="multipart",
        **headers(company),
    )

    assert response.status_code == 400
    assert "extensión .csv" in response.json()["errors"][0]["message"]

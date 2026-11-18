import pytest


@pytest.mark.django_db
def test_health_endpoint_requires_no_authentication(client):
    response = client.get("/api/v1/health/")

    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "message": "Consulta exitosa.",
        "data": {"status": "ok"},
        "errors": None,
    }


def test_health_endpoint_allows_any_method_only_get(client):
    response = client.post("/api/v1/health/", {}, format="json")

    assert response.status_code == 405
    assert response.json()["success"] is False

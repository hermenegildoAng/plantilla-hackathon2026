import logging
import uuid

import pytest


pytestmark = pytest.mark.urls("apps.core.tests.urls")


def test_validation_error_has_standard_shape(client):
    response = client.get("/__tests__/validation-error/")

    assert response.status_code == 400
    body = response.json()

    assert body["success"] is False
    assert body["message"] == "Error de validación en los datos enviados."
    assert body["error_id"] is None
    assert body["data"] is None
    assert isinstance(body["errors"], list)
    assert body["errors"] == [
        {
            "field": "rfc",
            "code": "invalid",
            "message": "Formato de RFC inválido.",
        }
    ]


def test_not_found_uses_standard_code(client):
    response = client.get("/__tests__/not-found/")

    assert response.status_code == 404
    body = response.json()

    assert body["success"] is False
    assert body["message"] == "Recurso no encontrado."
    assert body["error_id"] is None
    assert body["errors"][0]["code"] == "not_found"
    assert body["errors"][0]["field"] is None


def test_unhandled_exception_hides_traceback_and_returns_error_id(client, caplog):
    caplog.set_level(logging.ERROR, logger="apps.core.exceptions")

    response = client.get("/__tests__/server-error/")

    assert response.status_code == 500
    raw_body = response.content.decode()
    body = response.json()

    assert "super-secret-token" not in raw_body
    assert "Traceback" not in raw_body
    assert "RuntimeError" not in raw_body

    assert body["success"] is False
    assert body["message"] == "Error interno del servidor."
    assert body["data"] is None
    assert isinstance(body["errors"], list)
    assert body["errors"] == [
        {
            "field": None,
            "code": "internal_server_error",
            "message": "Ocurrió un error inesperado. Contacte a soporte técnico.",
        }
    ]

    error_id = body["error_id"]
    assert error_id is not None
    assert str(uuid.UUID(error_id)) == error_id

    assert error_id in caplog.text
    assert "super-secret-token" in caplog.text
    assert "RuntimeError" in caplog.text

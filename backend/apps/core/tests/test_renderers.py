import json
from decimal import Decimal

import pytest
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory

from apps.core.renderers import StandardJSONRenderer


pytestmark = pytest.mark.urls("apps.core.tests.urls")


def test_success_response_is_wrapped(client):
    response = client.get("/__tests__/success/")

    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "message": "Consulta exitosa.",
        "data": {"answer": "42"},
        "errors": None,
    }


def test_created_response_uses_creation_message(client):
    response = client.post("/__tests__/created/", {}, format="json")

    assert response.status_code == 201
    body = response.json()
    assert body["success"] is True
    assert body["message"] == "Registro creado correctamente."
    assert body["data"] == {"id": 1}
    assert body["errors"] is None


def test_view_can_override_response_message(client):
    response = client.get("/__tests__/custom-message/")

    assert response.status_code == 200
    assert response.json()["message"] == "Póliza contable registrada correctamente."


def test_paginated_payload_stays_inside_data():
    paginated = {
        "count": 0,
        "next": None,
        "previous": None,
        "results": [],
    }
    request = APIRequestFactory().get("/")
    response = Response(paginated)
    renderer = StandardJSONRenderer()
    context = {"response": response, "request": request, "view": None}

    rendered = renderer.render(paginated, renderer_context=context)
    body = json.loads(rendered)

    assert body["success"] is True
    assert body["data"] == paginated
    assert body["errors"] is None


def test_decimal_values_are_serialized_as_strings():
    data = {"total_debit": Decimal("11600.00"), "total_credit": Decimal("90.10")}
    request = APIRequestFactory().get("/")
    response = Response(data)
    renderer = StandardJSONRenderer()

    rendered = renderer.render(
        data,
        renderer_context={"response": response, "request": request, "view": None},
    )
    body = json.loads(rendered)

    assert body["data"]["total_debit"] == "11600.00"
    assert body["data"]["total_credit"] == "90.10"


def test_error_response_is_not_double_wrapped(client):
    response = client.get("/__tests__/validation-error/")

    assert response.status_code == 400
    body = response.json()
    assert body["success"] is False
    assert "data" in body
    assert body["data"] is None

import yaml
import pytest
from django.core.management import call_command
from drf_spectacular.generators import SchemaGenerator


pytestmark = pytest.mark.django_db

HTTP_METHODS = {
    "get",
    "post",
    "put",
    "patch",
    "delete",
    "options",
    "head",
}


def _schema():
    return SchemaGenerator().get_schema(request=None, public=True)


def test_schema_describes_standard_envelope_and_error_codes():
    schema = _schema()
    components = schema["components"]["schemas"]

    assert "StandardEnvelope" in components
    assert "StandardError" in components
    assert "StandardErrorItem" in components
    assert "ErrorCode" in components
    assert "period_closed" in components["ErrorCode"]["enum"]
    assert "role_permission_denied" in components["ErrorCode"]["enum"]

    operations = 0
    for path_item in schema["paths"].values():
        for method, operation in path_item.items():
            if method not in HTTP_METHODS:
                continue
            operations += 1
            responses = operation["responses"]

            for error_status in ("400", "401", "403", "404", "429", "500"):
                assert error_status in responses
                error_schema = responses[error_status]["content"][
                    "application/json"
                ]["schema"]
                assert (
                    error_schema["$ref"]
                    == "#/components/schemas/StandardError"
                )

            for status_code, response in responses.items():
                if not status_code.startswith("2") or status_code == "204":
                    continue
                success_schema = response["content"]["application/json"][
                    "schema"
                ]
                assert success_schema["x-standard-envelope"] is True
                assert any(
                    item.get("$ref")
                    == "#/components/schemas/StandardEnvelope"
                    for item in success_schema["allOf"]
                )

    assert operations > 0


def test_spectacular_command_writes_openapi_yaml(tmp_path):
    output = tmp_path / "openapi.yaml"
    call_command("spectacular", "--file", str(output), verbosity=0)

    document = yaml.safe_load(output.read_text(encoding="utf-8"))

    assert document["openapi"].startswith("3.")
    assert "StandardEnvelope" in document["components"]["schemas"]
    assert "period_closed" in document["components"]["schemas"]["ErrorCode"][
        "enum"
    ]

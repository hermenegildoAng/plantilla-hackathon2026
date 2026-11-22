"""drf-spectacular post-processing for the official response contract [E-02]."""

from copy import deepcopy


ERROR_CODES = [
    "validation_error",
    "missing_or_invalid_tenant_header",
    "period_closed",
    "authentication_failed",
    "token_not_valid",
    "tenant_access_denied",
    "role_permission_denied",
    "not_found",
    "method_not_allowed",
    "throttled",
    "internal_server_error",
]

ERROR_ITEM_SCHEMA = {
    "type": "object",
    "required": ["field", "code", "message"],
    "properties": {
        "field": {
            "type": "string",
            "nullable": True,
            "description": "Campo o encabezado relacionado con el error.",
        },
        "code": {"$ref": "#/components/schemas/ErrorCode"},
        "message": {
            "type": "string",
            "description": "Mensaje en español para el usuario final.",
        },
    },
}

ERROR_CODE_SCHEMA = {
    "type": "string",
    "enum": ERROR_CODES,
    "description": "Catálogo de códigos de error estandarizados.",
}

STANDARD_ENVELOPE_SCHEMA = {
    "type": "object",
    "description": "Envoltorio estándar de toda respuesta exitosa.",
    "required": ["success", "message", "data", "errors"],
    "properties": {
        "success": {
            "type": "boolean",
            "enum": [True],
            "example": True,
        },
        "message": {
            "type": "string",
            "example": "Consulta exitosa.",
        },
        "data": {
            "nullable": True,
            "description": "Carga útil del endpoint (objeto, arreglo o paginación).",
        },
        "errors": {
            "type": "array",
            "nullable": True,
            "items": {"$ref": "#/components/schemas/StandardErrorItem"},
            "example": None,
        },
    },
}

STANDARD_ERROR_SCHEMA = {
    "type": "object",
    "description": "Envoltorio estándar de toda respuesta de error.",
    "required": ["success", "message", "error_id", "data", "errors"],
    "properties": {
        "success": {
            "type": "boolean",
            "enum": [False],
            "example": False,
        },
        "message": {
            "type": "string",
            "example": "Error de validación en los datos enviados.",
        },
        "error_id": {
            "type": "string",
            "format": "uuid",
            "nullable": True,
            "description": "UUID solo para errores 500; null en el resto.",
        },
        "data": {"nullable": True, "example": None},
        "errors": {
            "type": "array",
            "items": {"$ref": "#/components/schemas/StandardErrorItem"},
        },
    },
}

ERROR_RESPONSES = {
    "400": (
        "Solicitud inválida o error de validación de negocio.",
        [
            "validation_error",
            "missing_or_invalid_tenant_header",
            "period_closed",
        ],
    ),
    "401": (
        "Token JWT ausente, malformado o expirado.",
        ["authentication_failed", "token_not_valid"],
    ),
    "403": (
        "Acceso denegado por tenant o por rol.",
        ["tenant_access_denied", "role_permission_denied"],
    ),
    "404": ("Recurso no encontrado en la empresa activa.", ["not_found"]),
    "405": ("Método HTTP no permitido.", ["method_not_allowed"]),
    "429": ("Límite de intentos excedido.", ["throttled"]),
    "500": (
        "Error interno no controlado (incluye error_id).",
        ["internal_server_error"],
    ),
}

HTTP_METHODS = {
    "get",
    "put",
    "post",
    "delete",
    "options",
    "head",
    "patch",
    "trace",
}


def _error_response(description, codes):
    return {
        "description": description,
        "x-error-codes": codes,
        "content": {
            "application/json": {
                "schema": {"$ref": "#/components/schemas/StandardError"},
                "example": {
                    "success": False,
                    "message": "Permisos insuficientes.",
                    "error_id": None,
                    "data": None,
                    "errors": [
                        {
                            "field": None,
                            "code": codes[0],
                            "message": "No tiene permisos para realizar esta acción.",
                        }
                    ],
                },
            }
        },
    }


def _wrap_success_schema(schema):
    if not isinstance(schema, dict):
        return schema
    if schema.get("x-standard-envelope"):
        return schema
    return {
        "allOf": [
            {"$ref": "#/components/schemas/StandardEnvelope"},
            {
                "type": "object",
                "properties": {"data": schema},
            },
        ],
        "x-standard-envelope": True,
    }


def standard_contract_postprocessor(result, generator, request, public):
    """Add the standard envelope and error catalog to every operation."""
    schema = result
    components = schema.setdefault("components", {}).setdefault("schemas", {})
    components.setdefault("ErrorCode", deepcopy(ERROR_CODE_SCHEMA))
    components.setdefault("StandardErrorItem", deepcopy(ERROR_ITEM_SCHEMA))
    components.setdefault("StandardEnvelope", deepcopy(STANDARD_ENVELOPE_SCHEMA))
    components.setdefault("StandardError", deepcopy(STANDARD_ERROR_SCHEMA))

    for path_item in schema.get("paths", {}).values():
        for method, operation in path_item.items():
            if method.lower() not in HTTP_METHODS or not isinstance(operation, dict):
                continue

            responses = operation.setdefault("responses", {})

            for status_code, (description, codes) in ERROR_RESPONSES.items():
                responses.setdefault(
                    status_code,
                    _error_response(description, codes),
                )

            for status_code, response in responses.items():
                if not str(status_code).startswith("2"):
                    continue
                if str(status_code) == "204":
                    continue
                content = response.setdefault("content", {}).setdefault(
                    "application/json",
                    {"schema": {"type": "object"}},
                )
                if "schema" not in content:
                    content["schema"] = {"type": "object"}
                content["schema"] = _wrap_success_schema(content["schema"])

    return schema

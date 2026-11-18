"""Global DRF exception handler with the official error contract."""

import logging
import uuid

from django.core.exceptions import (
    ObjectDoesNotExist,
    ValidationError as DjangoValidationError,
)
from rest_framework import exceptions
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler


logger = logging.getLogger(__name__)


STATUS_MESSAGES = {
    400: "Error de validación en los datos enviados.",
    401: "Sesión no válida o expirada.",
    403: "Permisos insuficientes.",
    404: "Recurso no encontrado.",
    405: "Método no permitido.",
    429: "Demasiados intentos.",
    500: "Error interno del servidor.",
}

CODE_MESSAGES = {
    "missing_or_invalid_tenant_header": "Contexto de empresa inválido.",
    "period_closed": "Periodo contable cerrado.",
    "tenant_access_denied": "Acceso denegado a la empresa.",
    "role_permission_denied": "Permisos insuficientes.",
    "not_found": "Recurso no encontrado.",
    "throttled": "Demasiados intentos.",
    "internal_server_error": "Error interno del servidor.",
    "authentication_failed": "Sesión no válida o expirada.",
    "token_not_valid": "Sesión no válida o expirada.",
}

CODE_FIELDS = {
    "authentication_failed": "authorization",
    "token_not_valid": "authorization",
    "missing_or_invalid_tenant_header": "X-Company-ID",
    "tenant_access_denied": "X-Company-ID",
    "period_closed": "fiscal_period",
}

CODE_ERROR_MESSAGES = {
    "missing_or_invalid_tenant_header": "Debe proporcionar un encabezado X-Company-ID válido.",
    "tenant_access_denied": "No tiene permisos para operar sobre esta empresa.",
    "role_permission_denied": "No tiene permisos para realizar esta acción.",
    "not_found": "El registro solicitado no existe en la empresa activa.",
    "throttled": "Intente de nuevo en un minuto.",
    "method_not_allowed": "El método HTTP utilizado no está permitido.",
}

GENERIC_CODE_BY_STATUS = {
    400: "validation_error",
    401: "authentication_failed",
    403: "role_permission_denied",
    404: "not_found",
    405: "method_not_allowed",
    429: "throttled",
    500: "internal_server_error",
}


def custom_exception_handler(exc, context):
    """Return every API error with ``errors`` as a list of normalized objects."""
    if isinstance(exc, DjangoValidationError):
        exc = _translate_django_validation_error(exc)
    elif isinstance(exc, ObjectDoesNotExist):
        exc = exceptions.NotFound()

    response = drf_exception_handler(exc, context)

    if response is None:
        return _internal_server_error_response(exc)

    if response.status_code == 500:
        return _internal_server_error_response(exc)

    return _standard_error_response(response)


def _translate_django_validation_error(exc: DjangoValidationError):
    if hasattr(exc, "message_dict"):
        detail = {
            field: [str(message) for message in messages]
            for field, messages in exc.message_dict.items()
        }
    else:
        detail = [str(message) for message in exc.messages]
    return exceptions.ValidationError(detail=detail)


def _standard_error_response(response: Response) -> Response:
    status_code = response.status_code
    errors = _flatten_errors(response.data, fallback_code=_generic_code(status_code))

    if not errors:
        errors = [
            {
                "field": None,
                "code": _generic_code(status_code),
                "message": STATUS_MESSAGES.get(
                    status_code,
                    "Ocurrió un error al procesar la solicitud.",
                ),
            }
        ]

    for error in errors:
        error["message"] = CODE_ERROR_MESSAGES.get(error["code"], error["message"])

    primary_code = errors[0]["code"]
    message = CODE_MESSAGES.get(primary_code) or STATUS_MESSAGES.get(
        status_code,
        "Ocurrió un error al procesar la solicitud.",
    )

    response.data = {
        "success": False,
        "message": message,
        "error_id": None,
        "data": None,
        "errors": errors,
    }
    return response


def _internal_server_error_response(exc) -> Response:
    error_id = uuid.uuid4()
    logger.exception(
        "Unhandled exception error_id=%s",
        error_id,
        exc_info=(type(exc), exc, exc.__traceback__),
    )

    return Response(
        {
            "success": False,
            "message": "Error interno del servidor.",
            "error_id": str(error_id),
            "data": None,
            "errors": [
                {
                    "field": None,
                    "code": "internal_server_error",
                    "message": (
                        "Ocurrió un error inesperado. "
                        "Contacte a soporte técnico."
                    ),
                }
            ],
        },
        status=500,
    )


def _flatten_errors(detail, field=None, fallback_code="error") -> list[dict]:
    if isinstance(detail, dict):
        errors = []
        for key, value in detail.items():
            if key == "detail":
                child_field = field
            elif key in {"non_field_errors", "__all__"}:
                child_field = None
            else:
                child_field = str(key)
            errors.extend(
                _flatten_errors(value, field=child_field, fallback_code=fallback_code)
            )
        return errors

    if isinstance(detail, (list, tuple)):
        errors = []
        for item in detail:
            errors.extend(
                _flatten_errors(item, field=field, fallback_code=fallback_code)
            )
        return errors

    code = getattr(detail, "code", None) or fallback_code
    code = _normalize_code(str(code), field)
    field = CODE_FIELDS.get(code, field)

    return [
        {
            "field": field,
            "code": code,
            "message": str(detail),
        }
    ]


def _normalize_code(code: str, field) -> str:
    if code == "not_authenticated":
        return "authentication_failed"
    if code == "permission_denied":
        return "role_permission_denied"
    return code


def _generic_code(status_code: int) -> str:
    return GENERIC_CODE_BY_STATUS.get(status_code, "error")

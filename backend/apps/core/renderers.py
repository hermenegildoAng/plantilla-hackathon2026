"""Standard response envelope for every DRF endpoint."""

from decimal import Decimal

from rest_framework.renderers import JSONRenderer
from rest_framework.utils.encoders import JSONEncoder


class StandardJSONEncoder(JSONEncoder):
    """Serialize Decimal as a string so money never becomes a float."""

    def default(self, obj):
        if isinstance(obj, Decimal):
            return format(obj, "f")
        return super().default(obj)


class StandardJSONRenderer(JSONRenderer):
    """Wrap successful responses in the official response contract.

    ``{"success": true, "message": "...", "data": ..., "errors": null}``

    Paginated payloads remain ``{"count", "next", "previous", "results"}``
    inside ``data`` as required by E-19.
    """

    encoder_class = StandardJSONEncoder

    DEFAULT_MESSAGES = {
        "GET": "Consulta exitosa.",
        "POST": "Registro creado correctamente.",
        "PUT": "Registro actualizado correctamente.",
        "PATCH": "Registro actualizado correctamente.",
        "DELETE": "Registro eliminado correctamente.",
    }

    def render(self, data, accepted_media_type=None, renderer_context=None):
        renderer_context = renderer_context or {}
        response = renderer_context.get("response")
        status_code = getattr(response, "status_code", 200)

        if 200 <= status_code < 300 and status_code != 204 and data is not None:
            if not self._is_envelope(data):
                message = self._get_message(renderer_context)
                if isinstance(data, dict):
                    data = dict(data)
                    message = data.pop("response_message", None) or message
                data = {
                    "success": True,
                    "message": message,
                    "data": data,
                    "errors": None,
                }

        return super().render(data, accepted_media_type, renderer_context)

    @staticmethod
    def _is_envelope(data) -> bool:
        return isinstance(data, dict) and {
            "success",
            "message",
            "data",
            "errors",
        }.issubset(data.keys())

    def _get_message(self, renderer_context) -> str:
        response = renderer_context.get("response")
        view = renderer_context.get("view")
        request = renderer_context.get("request")

        for source in (response, view):
            message = getattr(source, "response_message", None)
            if message:
                return str(message)

        method = getattr(request, "method", "").upper()
        return self.DEFAULT_MESSAGES.get(
            method,
            "Operación realizada correctamente.",
        )

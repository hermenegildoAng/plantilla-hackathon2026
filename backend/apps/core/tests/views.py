from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView


class SuccessView(APIView):
    def get(self, request):
        return Response({"answer": "42"})


class CustomMessageView(APIView):
    def get(self, request):
        response = Response({"ok": True})
        response.response_message = "Póliza contable registrada correctamente."
        return response


class ValidationErrorView(APIView):
    def get(self, request):
        from rest_framework.exceptions import ValidationError

        raise ValidationError({"rfc": ["Formato de RFC inválido."]})


class NotFoundView(APIView):
    def get(self, request):
        from rest_framework.exceptions import NotFound

        raise NotFound()


class ServerErrorView(APIView):
    def get(self, request):
        raise RuntimeError("super-secret-token and internal implementation detail")


class CreatedView(APIView):
    def post(self, request):
        return Response({"id": 1}, status=status.HTTP_201_CREATED)

"""Document endpoints: list, bulk upload, manual, PDF, download and delete."""

import os
from uuid import UUID

from django.core.exceptions import TooManyFilesSent
from django.db.models import CharField, Q
from django.db.models.functions import Cast
from django.http import FileResponse
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ErrorDetail, NotFound, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.authentication.permissions import IsPartnerRole, IsTenantMember
from apps.documents.models import Document
from apps.documents.permissions import CanUploadDocuments
from apps.documents.serializers import (
    BulkDocumentUploadSerializer,
    DocumentListSerializer,
    DocumentPdfSerializer,
    ManualDocumentSerializer,
)
from apps.documents.services import (
    DocumentUploadError,
    attach_pdf,
    create_manual_document,
    process_bulk_upload,
)
from apps.tenants.mixins import TenantContextMixin


def _raise_upload_error(exc: DocumentUploadError):
    raise ValidationError(
        {"detail": ErrorDetail(exc.message, code=exc.code)}
    )


def _parse_bool(raw_value, field):
    normalized = str(raw_value).strip().lower()
    if normalized in {"true", "1", "yes"}:
        return True
    if normalized in {"false", "0", "no"}:
        return False
    raise ValidationError(
        {
            field: ErrorDetail(
                "El valor debe ser true o false.",
                code="invalid",
            )
        }
    )


class DocumentViewSet(
    TenantContextMixin,
    mixins.ListModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """GET/POST/DELETE /api/v1/documents/ (03 §3.4)."""

    serializer_class = DocumentListSerializer
    http_method_names = ["get", "post", "delete", "head", "options"]

    def get_permissions(self):
        if self.action in {"list", "download"}:
            return [IsAuthenticated(), IsTenantMember()]
        if self.action in {"bulk_upload", "manual", "pdf"}:
            return [IsAuthenticated(), CanUploadDocuments()]
        if self.action == "destroy":
            return [IsAuthenticated(), IsPartnerRole()]
        return [IsAuthenticated(), IsTenantMember()]

    def get_queryset(self):
        queryset = Document.objects.filter(
            company=self.request.company
        ).select_related("fiscal_period")

        fiscal_period = self.request.query_params.get("fiscal_period")
        if fiscal_period:
            try:
                fiscal_period_id = int(fiscal_period)
            except (TypeError, ValueError):
                raise ValidationError(
                    {
                        "fiscal_period": ErrorDetail(
                            "El periodo fiscal debe ser un número entero.",
                            code="invalid",
                        )
                    }
                ) from None
            queryset = queryset.filter(fiscal_period_id=fiscal_period_id)

        direction = self.request.query_params.get("direction")
        if direction:
            queryset = queryset.filter(direction=direction.upper())

        cfdi_type = self.request.query_params.get("cfdi_type")
        if cfdi_type:
            queryset = queryset.filter(cfdi_type=cfdi_type.upper())

        is_accounted = self.request.query_params.get("is_accounted")
        if is_accounted is not None and is_accounted != "":
            queryset = queryset.filter(
                is_accounted=_parse_bool(is_accounted, "is_accounted")
            )

        search = self.request.query_params.get("search")
        if search:
            term = search.strip()
            filters = (
                Q(issuer_rfc__icontains=term)
                | Q(receiver_rfc__icontains=term)
                | Q(issuer_name__icontains=term)
                | Q(receiver_name__icontains=term)
                | Q(series__icontains=term)
                | Q(folio__icontains=term)
            )
            try:
                filters |= Q(uuid=UUID(term.lower()))
            except (ValueError, TypeError, AttributeError):
                pass
            queryset = queryset.annotate(
                uuid_text=Cast("uuid", output_field=CharField())
            ).filter(filters)

        return queryset

    @action(detail=False, methods=["post"], url_path="bulk-upload")
    def bulk_upload(self, request):
        try:
            request_data = request.data
        except TooManyFilesSent:
            raise ValidationError(
                {
                    "files": ErrorDetail(
                        "Se permiten como máximo 50 archivos por petición.",
                        code="max_length",
                    )
                }
            ) from None

        payload = BulkDocumentUploadSerializer(data=request_data)
        payload.is_valid(raise_exception=True)

        result = process_bulk_upload(
            payload.validated_data["files"],
            company=request.company,
            user=request.user,
            direction=payload.validated_data.get("direction"),
        )
        summary = result["summary"]
        response = Response(result, status=status.HTTP_200_OK)
        response.response_message = (
            "Procesamiento masivo finalizado: "
            f"{summary['processed_count']} comprobantes importados, "
            f"{summary['failed_count']} omitidos con errores."
        )
        return response

    @action(detail=False, methods=["post"])
    def manual(self, request):
        payload = ManualDocumentSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = dict(payload.validated_data)
        pdf_file = data.pop("pdf_file")

        try:
            document = create_manual_document(
                request.company,
                request.user,
                pdf_file=pdf_file,
                **data,
            )
        except DocumentUploadError as exc:
            _raise_upload_error(exc)

        response = Response(
            DocumentListSerializer(
                document,
                context=self.get_serializer_context(),
            ).data,
            status=status.HTTP_201_CREATED,
        )
        response.response_message = (
            "Comprobante manual registrado correctamente."
        )
        return response

    @action(detail=True, methods=["post"])
    def pdf(self, request, pk=None):
        document = self.get_object()
        payload = DocumentPdfSerializer(data=request.data)
        payload.is_valid(raise_exception=True)

        try:
            document = attach_pdf(
                document,
                payload.validated_data["pdf_file"],
            )
        except DocumentUploadError as exc:
            _raise_upload_error(exc)

        response = Response(
            DocumentListSerializer(
                document,
                context=self.get_serializer_context(),
            ).data,
            status=status.HTTP_200_OK,
        )
        response.response_message = "PDF adjuntado correctamente."
        return response

    @action(detail=True, methods=["get"])
    def download(self, request, pk=None):
        document = self.get_object()
        file_kind = request.query_params.get("file")
        if file_kind not in {"xml", "pdf"}:
            raise ValidationError(
                {
                    "file": ErrorDetail(
                        "Indique file=xml o file=pdf.",
                        code="invalid",
                    )
                }
            )

        field = (
            document.xml_file
            if file_kind == "xml"
            else document.pdf_file
        )
        if not field:
            raise NotFound(
                ErrorDetail(
                    "El archivo solicitado no está disponible.",
                    code="not_found",
                )
            )

        original = document.original_filename or os.path.basename(field.name)
        expected_extension = f".{file_kind}"
        if not original.lower().endswith(expected_extension):
            stem = os.path.splitext(original)[0] or "comprobante"
            original = f"{stem}{expected_extension}"

        try:
            handle = field.open("rb")
        except OSError:
            raise NotFound(
                ErrorDetail(
                    "El archivo solicitado no está disponible.",
                    code="not_found",
                )
            ) from None

        content_type = (
            "application/xml" if file_kind == "xml" else "application/pdf"
        )
        response = FileResponse(
            handle,
            as_attachment=True,
            filename=original,
            content_type=content_type,
        )
        response["X-Content-Type-Options"] = "nosniff"
        return response

    def destroy(self, request, *args, **kwargs):
        document = self.get_object()
        if document.is_accounted:
            raise ValidationError(
                {
                    "detail": ErrorDetail(
                        "No se puede eliminar un documento contabilizado.",
                        code="document_accounted",
                    )
                }
            )
        if document.fiscal_period.is_closed:
            raise ValidationError(
                {
                    "detail": ErrorDetail(
                        f"El periodo fiscal "
                        f"{document.fiscal_period.year}-"
                        f"{document.fiscal_period.month:02d} "
                        "se encuentra cerrado.",
                        code="period_closed",
                    )
                }
            )

        files = [
            (field.storage, field.name)
            for field in (document.xml_file, document.pdf_file)
            if field
        ]
        document.delete()
        for storage, name in files:
            try:
                storage.delete(name)
            except OSError:
                pass
        return Response(status=status.HTTP_204_NO_CONTENT)

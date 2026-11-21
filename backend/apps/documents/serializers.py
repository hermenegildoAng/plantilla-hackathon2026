"""Serializers for CFDI document endpoints (03 §3.4)."""

from zoneinfo import ZoneInfo

from django.conf import settings
from rest_framework import serializers

from apps.documents.models import Document
from apps.documents.validators import (
    DocumentFileValidationError,
    validate_pdf_upload,
)


MEXICO_CITY = ZoneInfo("America/Mexico_City")


class DocumentListSerializer(serializers.ModelSerializer):
    """Payload for GET /documents/ with authenticated download URLs [E-07]."""

    xml_url = serializers.SerializerMethodField()
    pdf_url = serializers.SerializerMethodField()

    class Meta:
        model = Document
        fields = [
            "id",
            "uuid",
            "direction",
            "cfdi_type",
            "series",
            "folio",
            "issue_date",
            "issuer_rfc",
            "issuer_name",
            "receiver_rfc",
            "receiver_name",
            "payment_method",
            "subtotal",
            "iva_transferred",
            "iva_retained",
            "isr_retained",
            "total",
            "is_accounted",
            "sat_status",
            "original_filename",
            "xml_url",
            "pdf_url",
        ]
        read_only_fields = fields

    def _download_url(self, obj, file_kind: str):
        has_file = bool(
            obj.xml_file if file_kind == "xml" else obj.pdf_file
        )
        if not has_file:
            return None
        return f"/api/v1/documents/{obj.pk}/download/?file={file_kind}"

    def get_xml_url(self, obj):
        return self._download_url(obj, "xml")

    def get_pdf_url(self, obj):
        return self._download_url(obj, "pdf")


class BulkDocumentUploadSerializer(serializers.Serializer):
    """Multipart payload for POST /documents/bulk-upload/ [E-04] [E-06]."""

    files = serializers.ListField(
        child=serializers.FileField(),
        allow_empty=False,
        error_messages={
            "required": "Debe adjuntar al menos un archivo.",
            "empty": "Debe adjuntar al menos un archivo.",
        },
    )
    direction = serializers.ChoiceField(
        choices=Document.Direction.choices,
        required=False,
    )

    def validate_files(self, files):
        max_files = int(
            getattr(settings, "DOCUMENT_MAX_FILES_PER_REQUEST", 50)
        )
        if len(files) > max_files:
            raise serializers.ValidationError(
                f"Se permiten como máximo {max_files} archivos por petición."
            )
        return files


class ManualDocumentSerializer(serializers.Serializer):
    """Create a manual supporting document with a mandatory PDF."""

    pdf_file = serializers.FileField(
        error_messages={
            "required": "El comprobante manual requiere un archivo PDF.",
            "empty": "El comprobante manual requiere un archivo PDF.",
        }
    )
    issue_date = serializers.DateTimeField()
    direction = serializers.ChoiceField(choices=Document.Direction.choices)
    issuer_rfc = serializers.CharField(max_length=13)
    issuer_name = serializers.CharField(max_length=255)
    subtotal = serializers.DecimalField(max_digits=12, decimal_places=2)
    iva_transferred = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
    )
    total = serializers.DecimalField(max_digits=12, decimal_places=2)

    # Optional SAT fields kept available for realistic manual captures.
    discount = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        required=False,
        default="0.00",
    )
    ieps_transferred = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        required=False,
        default="0.00",
    )
    iva_retained = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        required=False,
        default="0.00",
    )
    isr_retained = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        required=False,
        default="0.00",
    )
    series = serializers.CharField(
        max_length=25,
        required=False,
        allow_blank=True,
        default="",
    )
    folio = serializers.CharField(
        max_length=40,
        required=False,
        allow_blank=True,
        default="",
    )
    payment_method = serializers.CharField(
        max_length=5,
        required=False,
        allow_blank=True,
        default="",
    )
    payment_form = serializers.CharField(
        max_length=5,
        required=False,
        allow_blank=True,
        default="",
    )
    currency = serializers.CharField(
        max_length=3,
        required=False,
        default="MXN",
    )
    exchange_rate = serializers.DecimalField(
        max_digits=10,
        decimal_places=4,
        required=False,
        default="1.0000",
    )

    def validate_pdf_file(self, value):
        try:
            validate_pdf_upload(value)
        except DocumentFileValidationError as exc:
            raise serializers.ValidationError(
                exc.message,
                code=exc.code,
            ) from None
        return value

    def validate_issue_date(self, value):
        if value.tzinfo is None:
            return value.replace(tzinfo=MEXICO_CITY)
        return value.astimezone(MEXICO_CITY)

    def validate_issuer_rfc(self, value):
        value = (value or "").upper().strip()
        if not value:
            raise serializers.ValidationError("El RFC del emisor es obligatorio.")
        return value

    def validate_currency(self, value):
        return (value or "MXN").upper().strip() or "MXN"


class DocumentPdfSerializer(serializers.Serializer):
    """Payload for POST /documents/{id}/pdf/."""

    pdf_file = serializers.FileField()

    def validate_pdf_file(self, value):
        try:
            validate_pdf_upload(value)
        except DocumentFileValidationError as exc:
            raise serializers.ValidationError(
                exc.message,
                code=exc.code,
            ) from None
        return value

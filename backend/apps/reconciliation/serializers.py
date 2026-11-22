"""Serializers for bank reconciliation endpoints [E-21]."""

from django.conf import settings
from rest_framework import serializers

from apps.reconciliation.models import BankMovement


class BankMovementSerializer(serializers.ModelSerializer):
    """Read-only bank movement representation; money stays as strings."""

    entry_folio = serializers.CharField(
        source="entry.folio",
        read_only=True,
        allow_null=True,
        default=None,
    )
    document_uuid = serializers.UUIDField(
        source="document.uuid",
        read_only=True,
        allow_null=True,
        default=None,
    )

    class Meta:
        model = BankMovement
        fields = [
            "id",
            "date",
            "reference",
            "description",
            "deposit",
            "withdrawal",
            "status",
            "entry",
            "entry_folio",
            "document",
            "document_uuid",
            "import_batch",
            "row_hash",
        ]
        read_only_fields = fields


class BankMovementImportSerializer(serializers.Serializer):
    """Multipart payload for POST /reconciliation/movements/import/."""

    file = serializers.FileField(
        error_messages={
            "required": "Debe adjuntar un archivo CSV.",
            "empty": "Debe adjuntar un archivo CSV.",
        }
    )

    def validate_file(self, value):
        filename = (value.name or "").lower()
        if not filename.endswith(".csv"):
            raise serializers.ValidationError(
                "El archivo debe tener extensión .csv."
            )
        max_size = getattr(
            settings,
            "BANK_MOVEMENT_CSV_MAX_SIZE",
            5 * 1024 * 1024,
        )
        if value.size > max_size:
            raise serializers.ValidationError(
                "El archivo CSV excede el tamaño máximo permitido (5 MB)."
            )
        return value


class BankMovementMatchSerializer(serializers.Serializer):
    """Payload for POST /reconciliation/movements/{id}/match/."""

    entry_id = serializers.IntegerField(required=False, allow_null=True)
    document_id = serializers.IntegerField(required=False, allow_null=True)

    def validate(self, attrs):
        entry_id = attrs.get("entry_id")
        document_id = attrs.get("document_id")

        if entry_id is None and document_id is None:
            raise serializers.ValidationError(
                {
                    "match": serializers.ErrorDetail(
                        "Debe indicar entry_id o document_id para conciliar "
                        "el movimiento.",
                        code="invalid_match_target",
                    )
                }
            )
        if entry_id is not None and document_id is not None:
            raise serializers.ValidationError(
                {
                    "match": serializers.ErrorDetail(
                        "Solo puede indicar entry_id o document_id, no ambos.",
                        code="invalid_match_target",
                    )
                }
            )
        return attrs

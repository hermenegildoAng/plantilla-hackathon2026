"""Serializers for the immutable audit log."""

from rest_framework import serializers

from apps.core.models import AuditLog


class AuditLogSerializer(serializers.ModelSerializer):
    """Read-only audit trail row [E-21]."""

    user_name = serializers.CharField(source="user.full_name", read_only=True)
    user_email = serializers.EmailField(source="user.email", read_only=True)
    action_display = serializers.CharField(
        source="get_action_display",
        read_only=True,
    )

    class Meta:
        model = AuditLog
        fields = [
            "id",
            "user",
            "user_name",
            "user_email",
            "action",
            "action_display",
            "target_model",
            "target_id",
            "justification",
            "previous_state",
            "new_state",
            "ip_address",
            "created_at",
        ]
        read_only_fields = fields

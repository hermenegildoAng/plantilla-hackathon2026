from django.contrib import admin

from apps.documents.models import Document


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = (
        "uuid",
        "company",
        "direction",
        "cfdi_type",
        "issue_date",
        "total",
        "is_accounted",
        "sat_status",
    )
    list_filter = ("direction", "cfdi_type", "is_accounted", "sat_status")
    search_fields = (
        "uuid",
        "issuer_rfc",
        "issuer_name",
        "receiver_rfc",
        "receiver_name",
        "original_filename",
    )
    readonly_fields = ("created_at", "updated_at")

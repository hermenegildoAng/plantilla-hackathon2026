from django.contrib import admin

from apps.tenants.models import Company


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = (
        "rfc",
        "legal_name",
        "tax_regime",
        "currency",
        "fiscal_year_start",
        "is_active",
    )
    list_filter = ("tax_regime", "currency", "fiscal_year_start", "is_active")
    search_fields = ("rfc", "legal_name")
    ordering = ("legal_name",)
    readonly_fields = ("created_at", "updated_at")

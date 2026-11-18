import uuid

from django.conf import settings
from django.db import models


class TimeStampedModel(models.Model):
    """Abstract base model with automatic creation and update timestamps."""

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class TenantAwareModel(TimeStampedModel):
    """Abstract base model for every company-scoped entity."""

    company = models.ForeignKey(
        "tenants.Company",
        on_delete=models.CASCADE,
        related_name="%(app_label)s_%(class)s_set",
        db_index=True,
        verbose_name="Empresa / Contribuyente",
    )

    class Meta:
        abstract = True


# TODO(bloque 2): add TenantManager with objects.for_company(company_id) once
# tenant-scoped models are introduced.

import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
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


class ImmutableQuerySet(models.QuerySet):
    """[E-18] Prevent bulk deletion and bulk updates of audit records."""

    def delete(self):
        raise ValidationError(
            "Los registros de AuditLog son inmutables y no pueden ser eliminados."
        )

    def update(self, **kwargs):
        raise ValidationError(
            "Los registros de AuditLog son inmutables y no pueden ser modificados."
        )


class AuditLog(TimeStampedModel):
    """Immutable audit trail for critical security and accounting events."""

    class ActionType(models.TextChoices):
        PERIOD_CLOSED = "PERIOD_CLOSED", "Cierre de Periodo Fiscal"
        PERIOD_REOPENED = "PERIOD_REOPENED", "Reapertura Extraordinaria de Periodo"
        ENTRY_DELETED = "ENTRY_DELETED", "Eliminación de Póliza"
        ROLE_CHANGED = "ROLE_CHANGED", "Cambio de Rol de Usuario"
        CATALOG_MODIFIED = "CATALOG_MODIFIED", "Modificación de Catálogo Contable"

    company = models.ForeignKey(
        "tenants.Company",
        on_delete=models.CASCADE,
        related_name="audit_logs",
        db_index=True,
        verbose_name="Empresa",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="audit_logs",
        verbose_name="Usuario",
    )
    action = models.CharField(
        max_length=30,
        choices=ActionType.choices,
        db_index=True,
        verbose_name="Acción",
    )
    target_model = models.CharField(max_length=100, verbose_name="Modelo afectado")
    target_id = models.CharField(max_length=64, verbose_name="ID afectado")
    justification = models.TextField(
        blank=True,
        default="",
        help_text=(
            "Motivo de la acción. El mínimo de 15 caracteres en la reapertura "
            "de periodos se valida en PeriodReopenSerializer, no en el modelo."
        ),
        verbose_name="Justificación",
    )
    previous_state = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Estado anterior",
    )
    new_state = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Estado nuevo",
    )
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        verbose_name="Dirección IP",
    )

    objects = ImmutableQuerySet.as_manager()

    class Meta:
        db_table = "core_audit_log"
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["company", "action", "-created_at"],
                name="idx_audit_company_action_date",
            ),
        ]
        verbose_name = "Registro de auditoría"
        verbose_name_plural = "Bitácora de auditoría"

    def save(self, *args, **kwargs):
        # [E-18] Only the initial insert is allowed; existing rows are immutable.
        if not self._state.adding:
            raise ValidationError(
                "Los registros de AuditLog son inmutables y no pueden ser modificados."
            )
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError(
            "Los registros de AuditLog son inmutables y no pueden ser eliminados."
        )

    def __str__(self):
        return f"{self.action} · {self.target_model}#{self.target_id}"

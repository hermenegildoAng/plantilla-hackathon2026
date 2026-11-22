"""Bank reconciliation model [E-21]."""

import uuid
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q

from apps.core.models import TenantAwareModel


class BankMovement(TenantAwareModel):
    """Bank statement row that can be matched against entries or CFDI documents."""

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pendiente"
        RECONCILED = "RECONCILED", "Conciliado"

    date = models.DateField(
        db_index=True,
        verbose_name="Fecha del movimiento",
    )
    reference = models.CharField(
        max_length=100,
        blank=True,
        default="",
        verbose_name="Referencia bancaria",
    )
    description = models.CharField(
        max_length=255,
        verbose_name="Concepto",
    )
    deposit = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
        verbose_name="Depósito",
    )
    withdrawal = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
        verbose_name="Retiro",
    )
    status = models.CharField(
        max_length=12,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
        verbose_name="Estado",
    )
    entry = models.ForeignKey(
        "accounting.AccountingEntry",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="bank_movements",
        verbose_name="Póliza vinculada",
    )
    document = models.ForeignKey(
        "documents.Document",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="bank_movements",
        verbose_name="Documento vinculado",
    )
    import_batch = models.UUIDField(
        default=uuid.uuid4,
        db_index=True,
        verbose_name="Lote de importación",
    )
    row_hash = models.CharField(
        max_length=64,
        verbose_name="Huella de la fila",
        help_text="SHA-256 de la fila normalizada; evita duplicados al reimportar.",
    )

    class Meta:
        db_table = "reconciliation_bank_movement"
        ordering = ["-date", "-pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "row_hash"],
                name="uq_bank_movement_company_row_hash",
            ),
            models.CheckConstraint(
                condition=(
                    Q(deposit__gte=Decimal("0.00"))
                    & Q(withdrawal__gte=Decimal("0.00"))
                    & ~(
                        Q(deposit__gt=Decimal("0.00"))
                        & Q(withdrawal__gt=Decimal("0.00"))
                    )
                    & (
                        Q(deposit__gt=Decimal("0.00"))
                        | Q(withdrawal__gt=Decimal("0.00"))
                    )
                ),
                name="ck_bank_movement_single_amount",
            ),
        ]
        indexes = [
            models.Index(
                fields=["company", "status", "date"],
                name="idx_bank_mv_company_status",
            ),
        ]
        verbose_name = "Movimiento bancario"
        verbose_name_plural = "Movimientos bancarios"

    def clean(self):
        super().clean()

        if self.deposit is None or self.withdrawal is None:
            return

        if self.deposit < Decimal("0.00") or self.withdrawal < Decimal("0.00"):
            raise ValidationError(
                "Los montos de depósito y retiro no pueden ser negativos."
            )

        if self.deposit > Decimal("0.00") and self.withdrawal > Decimal("0.00"):
            raise ValidationError(
                "Un movimiento bancario no puede tener depósito y retiro "
                "simultáneamente."
            )

        if self.deposit == Decimal("0.00") and self.withdrawal == Decimal("0.00"):
            raise ValidationError(
                "El movimiento bancario debe tener un depósito o un retiro "
                "mayor a cero."
            )

        if self.entry_id and self.company_id:
            if self.entry.company_id != self.company_id:
                raise ValidationError(
                    "La póliza vinculada no pertenece a la empresa del movimiento."
                )

        if self.document_id and self.company_id:
            if self.document.company_id != self.company_id:
                raise ValidationError(
                    "El documento vinculado no pertenece a la empresa del "
                    "movimiento."
                )

    @property
    def amount(self) -> Decimal:
        """Signed bank amount: deposits are positive, withdrawals negative."""
        if self.deposit > Decimal("0.00"):
            return self.deposit
        return -self.withdrawal

    def __str__(self):
        return f"{self.date} · {self.description} · {self.amount}"

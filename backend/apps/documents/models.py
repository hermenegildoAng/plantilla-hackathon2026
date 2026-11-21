"""CFDI document model [E-07] [E-16]."""

import os
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from apps.core.models import TenantAwareModel
from apps.documents.validators import validate_pdf_upload, validate_xml_upload


def document_upload_path(instance, filename):
    """Private, UUID-based storage path; the original name is never used.

    [E-07] ``companies/{company_id}/documents/{yyyy}/{mm}/{uuid4}.{ext}``
    """
    ext = os.path.basename(filename).rsplit(".", 1)[-1].lower()
    issue_date = instance.issue_date
    if issue_date is None:
        local_date = timezone.localdate()
    elif isinstance(issue_date, datetime):
        local_date = (
            timezone.localtime(issue_date)
            if timezone.is_aware(issue_date)
            else issue_date
        )
    elif isinstance(issue_date, date):
        local_date = issue_date
    else:
        local_date = timezone.localdate()
    return (
        f"companies/{instance.company_id}/documents/"
        f"{local_date:%Y}/{local_date:%m}/{uuid4()}.{ext}"
    )


class Document(TenantAwareModel):
    """CFDI 4.0/3.3 comprobante or a manual supporting document."""

    class Direction(models.TextChoices):
        ISSUED = "ISSUED", "Emitido (Ingreso/Venta)"
        RECEIVED = "RECEIVED", "Recibido (Gasto/Compra)"

    class CfdiType(models.TextChoices):
        INGRESO = "I", "I - Ingreso"
        EGRESO = "E", "E - Egreso"
        TRASLADO = "T", "T - Traslado"
        NOMINA = "N", "N - Nómina"
        PAGO = "P", "P - Pago"
        MANUAL = "M", "M - Comprobante Manual sin XML"

    class SatStatus(models.TextChoices):
        VALID = "VALID", "Vigente"
        CANCELLED = "CANCELLED", "Cancelado"
        UNVERIFIED = "UNVERIFIED", "Sin verificar"

    fiscal_period = models.ForeignKey(
        "accounting.FiscalPeriod",
        on_delete=models.PROTECT,
        related_name="documents",
        verbose_name="Periodo fiscal",
    )
    uuid = models.UUIDField(
        null=True,
        blank=True,
        help_text=(
            "Folio Fiscal (Timbre Fiscal Digital), normalizado a minúsculas. "
            "Null únicamente para comprobantes manuales sin XML."
        ),
    )  # [E-16] Sin db_index: el UniqueConstraint (company, uuid) ya crea el índice.
    direction = models.CharField(
        max_length=10,
        choices=Direction.choices,
        db_index=True,
        verbose_name="Dirección",
    )
    cfdi_type = models.CharField(
        max_length=2,
        choices=CfdiType.choices,
        default=CfdiType.INGRESO,
        db_index=True,
        verbose_name="Tipo de comprobante",
    )
    cfdi_version = models.CharField(
        max_length=5,
        default="4.0",
        verbose_name="Versión CFDI",
    )
    original_filename = models.CharField(
        max_length=255,
        blank=True,
        default="",
        verbose_name="Nombre original",
    )
    sat_status = models.CharField(
        max_length=12,
        choices=SatStatus.choices,
        default=SatStatus.UNVERIFIED,
        db_index=True,
        verbose_name="Estatus SAT",
    )
    series = models.CharField(
        max_length=25,
        blank=True,
        default="",
        verbose_name="Serie",
    )
    folio = models.CharField(
        max_length=40,
        blank=True,
        default="",
        verbose_name="Folio",
    )
    issue_date = models.DateTimeField(db_index=True, verbose_name="Fecha de emisión")

    issuer_rfc = models.CharField(
        max_length=13,
        db_index=True,
        verbose_name="RFC emisor",
    )
    issuer_name = models.CharField(max_length=255, verbose_name="Nombre emisor")
    receiver_rfc = models.CharField(
        max_length=13,
        db_index=True,
        verbose_name="RFC receptor",
    )
    receiver_name = models.CharField(max_length=255, verbose_name="Nombre receptor")

    payment_method = models.CharField(
        max_length=5,
        blank=True,
        default="",
        help_text="PUE o PPD",
        verbose_name="Método de pago",
    )
    payment_form = models.CharField(
        max_length=5,
        blank=True,
        default="",
        help_text="01 Efectivo, 03 Transferencia, etc.",
        verbose_name="Forma de pago",
    )
    currency = models.CharField(max_length=3, default="MXN", verbose_name="Moneda")
    exchange_rate = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        default=Decimal("1.0000"),
        verbose_name="Tipo de cambio",
    )

    subtotal = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name="Subtotal",
    )
    discount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name="Descuento",
    )
    iva_transferred = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="IVA Trasladado",
        verbose_name="IVA trasladado",
    )
    ieps_transferred = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="IEPS Trasladado",
        verbose_name="IEPS trasladado",
    )
    iva_retained = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="IVA Retenido",
        verbose_name="IVA retenido",
    )
    isr_retained = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="ISR Retenido",
        verbose_name="ISR retenido",
    )
    total = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name="Total",
    )

    raw_metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Metadatos CFDI",
    )

    xml_file = models.FileField(
        upload_to=document_upload_path,
        null=True,
        blank=True,
        validators=[validate_xml_upload],
        verbose_name="XML",
    )
    pdf_file = models.FileField(
        upload_to=document_upload_path,
        null=True,
        blank=True,
        validators=[validate_pdf_upload],
        verbose_name="PDF",
    )

    is_accounted = models.BooleanField(
        default=False,
        db_index=True,
        help_text="True si ya tiene póliza vinculada",
        verbose_name="Contabilizado",
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="uploaded_documents",
        verbose_name="Cargado por",
    )

    class Meta:
        db_table = "documents_document"
        ordering = ["-issue_date"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "uuid"],
                condition=models.Q(uuid__isnull=False),
                name="uq_company_cfdi_uuid",
            )
        ]
        indexes = [
            # [E-16] idx_doc_company_uuid is intentionally absent: it would
            # duplicate the unique constraint index.
            models.Index(
                fields=["company", "fiscal_period", "direction"],
                name="idx_doc_period_direction",
            ),
            models.Index(
                fields=["company", "issue_date"],
                name="idx_doc_company_date",
            ),
            models.Index(
                fields=["company", "is_accounted"],
                name="idx_doc_company_accounted",
            ),
        ]
        verbose_name = "Documento fiscal"
        verbose_name_plural = "Documentos fiscales"

    def clean(self):
        super().clean()
        if self.fiscal_period_id and self.fiscal_period.is_closed:
            raise ValidationError(
                "No se pueden cargar o modificar documentos en un periodo "
                "fiscal cerrado."
            )
        if self.cfdi_type != self.CfdiType.MANUAL and not self.uuid:
            raise ValidationError(
                "Todo comprobante CFDI debe contar con un UUID válido."
            )
        if self.cfdi_type == self.CfdiType.MANUAL and not self.pdf_file:
            raise ValidationError(
                "Los comprobantes manuales sin XML requieren adjuntar un "
                "archivo PDF o imagen de respaldo."
            )

    def save(self, *args, **kwargs):
        # [E-16] Normalize UUID and RFC values before persisting.
        if self.uuid is not None and not isinstance(self.uuid, UUID):
            self.uuid = UUID(str(self.uuid).lower())
        if self.uuid is not None:
            self.uuid = UUID(str(self.uuid).lower())
        if self.issuer_rfc:
            self.issuer_rfc = self.issuer_rfc.upper().strip()
        if self.receiver_rfc:
            self.receiver_rfc = self.receiver_rfc.upper().strip()
        if self.original_filename:
            self.original_filename = (
                os.path.basename(self.original_filename)[:255]
            )
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.get_cfdi_type_display()} · {self.uuid or 'manual'}"

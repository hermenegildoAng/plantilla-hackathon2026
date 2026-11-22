"""Accounting models: fiscal periods, chart of accounts and journal entries."""

from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.core.models import TenantAwareModel


class FiscalPeriod(TenantAwareModel):
    """Monthly accounting period that can be closed and reopened."""

    year = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(2000)],
        verbose_name="Ejercicio",
    )
    month = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(12)],
        verbose_name="Mes",
    )
    is_closed = models.BooleanField(
        default=False,
        db_index=True,
        verbose_name="Cerrado",
    )
    closed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Fecha de cierre",
    )
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="closed_fiscal_periods",
        verbose_name="Cerrado por",
    )

    class Meta:
        db_table = "accounting_fiscal_period"
        ordering = ["-year", "-month"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "year", "month"],
                name="uq_company_fiscal_period",
            ),
        ]
        verbose_name = "Periodo fiscal"
        verbose_name_plural = "Periodos fiscales"

    def __str__(self):
        return f"{self.company.legal_name} · {self.year}-{self.month:02d}"


class AccountCatalog(TenantAwareModel):
    """Company chart of accounts tied to the SAT grouping codes (Anexo 24)."""

    class AccountType(models.TextChoices):
        ASSET = "ASSET", "Activo"
        LIABILITY = "LIABILITY", "Pasivo"
        EQUITY = "EQUITY", "Capital"
        REVENUE = "REVENUE", "Ingresos"
        EXPENSE = "EXPENSE", "Costos y gastos"
        ORDER = "ORDER", "Cuentas de orden"

    class Nature(models.TextChoices):
        DEBIT = "DEBIT", "Deudora"
        CREDIT = "CREDIT", "Acreedora"

    parent = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="children",
        verbose_name="Cuenta padre",
    )
    code = models.CharField(
        max_length=30,
        db_index=True,
        verbose_name="Código de cuenta",
    )
    sat_group_code = models.CharField(
        max_length=15,
        db_index=True,
        verbose_name="Código agrupador SAT",
    )
    name = models.CharField(max_length=255, verbose_name="Nombre de la cuenta")
    account_type = models.CharField(
        max_length=20,
        choices=AccountType.choices,
        verbose_name="Tipo de cuenta",
    )
    nature = models.CharField(
        max_length=10,
        choices=Nature.choices,
        verbose_name="Naturaleza",
    )
    is_selectable = models.BooleanField(
        default=True,
        verbose_name="Afectable",
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="Activa",
    )

    class Meta:
        db_table = "accounting_account_catalog"
        ordering = ["code"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "code"],
                name="uq_company_account_code",
            ),
        ]
        verbose_name = "Cuenta contable"
        verbose_name_plural = "Catálogo de cuentas"

    def __str__(self):
        return f"{self.code} · {self.name}"


class AccountingEntry(TenantAwareModel):
    """Journal entry header (póliza) validated with double-entry accounting."""

    class EntryType(models.TextChoices):
        INCOME = "INCOME", "Póliza de Ingresos"
        EXPENSE = "EXPENSE", "Póliza de Egresos"
        JOURNAL = "JOURNAL", "Póliza de Diario"

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Borrador"
        POSTED = "POSTED", "Contabilizada"

    fiscal_period = models.ForeignKey(
        FiscalPeriod,
        on_delete=models.PROTECT,
        related_name="entries",
        verbose_name="Periodo fiscal",
    )
    entry_type = models.CharField(
        max_length=15,
        choices=EntryType.choices,
        verbose_name="Tipo de póliza",
    )
    folio = models.CharField(
        max_length=30,
        db_index=True,
        verbose_name="Folio",
    )
    entry_date = models.DateField(
        db_index=True,
        verbose_name="Fecha de la póliza",
    )
    concept = models.CharField(
        max_length=500,
        verbose_name="Concepto",
    )
    status = models.CharField(
        max_length=15,
        choices=Status.choices,
        default=Status.POSTED,
        db_index=True,
        verbose_name="Estado",
    )
    total_debit = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name="Total de cargos",
    )
    total_credit = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name="Total de abonos",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_entries",
        verbose_name="Creado por",
    )

    class Meta:
        db_table = "accounting_entry"
        ordering = ["-entry_date", "-folio"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "fiscal_period", "entry_type", "folio"],
                name="uq_entry_folio_period",
            ),
        ]
        indexes = [
            models.Index(
                fields=["company", "fiscal_period", "entry_date"],
                name="idx_entry_company_period_date",
            ),
        ]
        verbose_name = "Póliza contable"
        verbose_name_plural = "Pólizas contables"

    def clean(self):
        super().clean()
        if self.fiscal_period_id and self.company_id:
            if self.fiscal_period.company_id != self.company_id:
                raise ValidationError(
                    "El periodo fiscal no pertenece a la empresa seleccionada."
                )
        if self.fiscal_period_id and self.fiscal_period.is_closed:
            raise ValidationError(
                f"El periodo fiscal {self.fiscal_period.year}-"
                f"{self.fiscal_period.month:02d} se encuentra cerrado. "
                "No se permiten modificaciones."
            )
        if self.entry_date and self.fiscal_period_id:
            if (
                self.entry_date.year != self.fiscal_period.year
                or self.entry_date.month != self.fiscal_period.month
            ):
                raise ValidationError(
                    "La fecha de la póliza debe corresponder al mes y año "
                    "del periodo fiscal asignado."
                )

    def validate_double_entry(self):
        """Ensure persisted items are balanced and strictly greater than zero."""
        items = list(self.items.all())
        if len(items) < 2:
            raise ValidationError(
                "Una póliza contable debe contener al menos dos movimientos."
            )

        sum_debit = sum((item.debit for item in items), Decimal("0.00"))
        sum_credit = sum((item.credit for item in items), Decimal("0.00"))

        if sum_debit <= Decimal("0.00") or sum_credit <= Decimal("0.00"):
            raise ValidationError(
                "La suma de cargos y abonos debe ser estrictamente mayor a cero."
            )

        if sum_debit != sum_credit:
            raise ValidationError(
                "Póliza descuadrada: "
                f"Suma de Cargos (${sum_debit}) != "
                f"Suma de Abonos (${sum_credit})."
            )

        self.total_debit = sum_debit
        self.total_credit = sum_credit

    def __str__(self):
        return f"{self.folio} · {self.concept}"


class AccountingEntryItem(TenantAwareModel):
    """Journal entry line (movimiento) linked to an account and optional CFDI."""

    entry = models.ForeignKey(
        AccountingEntry,
        on_delete=models.CASCADE,
        related_name="items",
        verbose_name="Póliza",
    )
    account = models.ForeignKey(
        AccountCatalog,
        on_delete=models.PROTECT,
        related_name="entry_items",
        verbose_name="Cuenta contable",
    )
    document = models.ForeignKey(
        "documents.Document",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="accounting_items",
        help_text="CFDI / Documento soporte vinculado a este movimiento",
        verbose_name="Documento soporte",
    )
    line_number = models.PositiveSmallIntegerField(
        default=1,
        verbose_name="Número de renglón",
    )
    description = models.CharField(
        max_length=255,
        blank=True,
        default="",
        verbose_name="Descripción",
    )
    debit = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
        verbose_name="Cargo",
    )
    credit = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
        verbose_name="Abono",
    )

    class Meta:
        db_table = "accounting_entry_item"
        ordering = ["line_number"]
        indexes = [
            models.Index(
                fields=["company", "account"],
                name="idx_item_company_account",
            ),
            models.Index(
                fields=["company", "document"],
                name="idx_item_company_document",
            ),
        ]
        verbose_name = "Renglón de póliza"
        verbose_name_plural = "Renglones de póliza"

    def clean(self):
        super().clean()
        if self.entry_id and self.company_id:
            if self.entry.company_id != self.company_id:
                raise ValidationError(
                    "El renglón no pertenece a la empresa de la póliza."
                )
        if self.account_id and self.company_id:
            if self.account.company_id != self.company_id:
                raise ValidationError(
                    "La cuenta contable no pertenece a la empresa de la póliza."
                )
        if self.account_id and not self.account.is_selectable:
            raise ValidationError(
                f"La cuenta {self.account.code} es acumulativa y no acepta "
                "movimientos directos."
            )
        if self.debit > Decimal("0.00") and self.credit > Decimal("0.00"):
            raise ValidationError(
                "Un mismo renglón no puede tener cargo y abono simultáneamente."
            )
        if self.debit == Decimal("0.00") and self.credit == Decimal("0.00"):
            raise ValidationError(
                "El renglón debe tener un monto mayor a cero en Cargo o Abono."
            )

    def __str__(self):
        return f"{self.entry.folio} · {self.line_number} · {self.account.code}"

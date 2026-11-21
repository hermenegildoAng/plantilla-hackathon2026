"""Accounting models: fiscal periods and the SAT chart of accounts."""

from django.conf import settings
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

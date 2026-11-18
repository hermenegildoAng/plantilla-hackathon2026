from django.core.validators import (
    MaxValueValidator,
    MinValueValidator,
    RegexValidator,
)
from django.db import models

from apps.core.models import TimeStampedModel


# RFC oficial del SAT (12 caracteres para personas morales, 13 para físicas).
# Nota [E-17]: los RFC de demostración deben pasar este regex.
RFC_REGEX = (
    r"^([A-ZÑ&]{3,4}) ?(?:- ?)?"
    r"(\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])) ?(?:- ?)?"
    r"([A-Z\d]{2})([A\d])$"
)


class Company(TimeStampedModel):
    class TaxRegime(models.TextChoices):
        PFAEP = "612", "612 - Personas Físicas con Actividades Empresariales y Profesionales"
        RESICO = "626", "626 - Régimen Simplificado de Confianza"
        GENERAL_PM = "601", "601 - General de Ley Personas Morales"

    rfc = models.CharField(
        max_length=13,
        unique=True,
        db_index=True,
        validators=[
            RegexValidator(
                regex=RFC_REGEX,
                message="Formato de RFC inválido según reglas del SAT.",
            )
        ],
    )
    legal_name = models.CharField(max_length=255, db_index=True)
    tax_regime = models.CharField(max_length=10, choices=TaxRegime.choices)
    currency = models.CharField(max_length=3, default="MXN")
    fiscal_year_start = models.PositiveSmallIntegerField(
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(12)],
        help_text="Mes de inicio del ejercicio fiscal (Enero = 1).",
    )
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = "tenants_company"
        ordering = ["legal_name"]
        indexes = [
            models.Index(
                fields=["rfc", "is_active"],
                name="idx_company_rfc_active",
            ),
        ]
        verbose_name = "Empresa"
        verbose_name_plural = "Empresas"

    def save(self, *args, **kwargs):
        self.rfc = self.rfc.upper().strip()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.legal_name

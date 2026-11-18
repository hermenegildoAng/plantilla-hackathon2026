from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models

from apps.authentication.managers import UserManager
from apps.core.models import TimeStampedModel


class User(AbstractUser):
    """Custom user identified by email instead of username [E-10]."""

    username = None
    email = models.EmailField("Correo electrónico", unique=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

    class Meta:
        verbose_name = "Usuario"
        verbose_name_plural = "Usuarios"

    def __str__(self):
        return self.email

    @property
    def full_name(self):
        """Name shown by the API, falling back to the email address."""
        return self.get_full_name() or self.email


class Profile(TimeStampedModel):
    """Global data of a firm user, independent from any tenant."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
        verbose_name="Usuario",
    )
    phone = models.CharField(max_length=20, blank=True, default="")
    professional_license = models.CharField(
        max_length=50,
        blank=True,
        default="",
        help_text="Cédula profesional opcional",
    )
    default_company = models.ForeignKey(
        "tenants.Company",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="default_for_profiles",
        verbose_name="Empresa predeterminada",
    )

    class Meta:
        db_table = "auth_profile"
        verbose_name = "Perfil"
        verbose_name_plural = "Perfiles"

    def __str__(self):
        return f"Perfil de {self.user.email}"


class CompanyMembership(TimeStampedModel):
    """Roles a user has inside each company (N:M with role per tenant)."""

    class Role(models.TextChoices):
        PARTNER = "PARTNER", "Socio / Administrador"
        ACCOUNTANT = "ACCOUNTANT", "Auxiliar Contable"
        AUDITOR = "AUDITOR", "Auditor"
        CLIENT = "CLIENT", "Cliente (Portal Externo)"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="company_memberships",
        verbose_name="Usuario",
    )
    company = models.ForeignKey(
        "tenants.Company",
        on_delete=models.CASCADE,
        related_name="user_memberships",
        verbose_name="Empresa",
    )
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.ACCOUNTANT,
        verbose_name="Rol",
    )
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = "auth_company_membership"
        verbose_name = "Membresía"
        verbose_name_plural = "Membresías"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "company"],
                name="uq_user_company_membership",
            )
        ]
        indexes = [
            models.Index(
                fields=["user", "company", "is_active"],
                name="idx_membership_lookup",
            ),
        ]
        ordering = ["company__legal_name", "user__email"]

    def __str__(self):
        return f"{self.user.email} · {self.company.legal_name} · {self.role}"

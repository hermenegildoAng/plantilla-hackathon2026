# Especificación Técnica de Base de Datos y Modelos ORM (`02_DATABASE_SPEC.md`)

Este documento define la arquitectura relacional en PostgreSQL y la implementación exacta de la capa de modelos en **Django ORM** para el sistema contable multi-tenant. Sirve como guía obligatoria para la generación de migraciones, managers personalizados y reglas de integridad de datos.

> **Precedencia:** `docs/00_ERRATA.md` prevalece sobre este documento. Los puntos ajustados por la errata se marcan con `[E-xx]`.

---

## 1. Principios Globales de Diseño y Clases Base (`apps/core`)

### 1.1 Estrategia de Aislamiento Multi-Tenant (`TenantAwareModel`)
Para evitar repetición de código y garantizar el cumplimiento estricto de la regla de aislamiento lógico por empresa (`company_id`), todos los modelos transaccionales y de catálogo operativo heredarán de una clase abstracta base `TenantAwareModel` ubicada en `apps/core/models.py`.

* **Llave primaria estándar:** `UUIDField` (v4) o `BigAutoField` (usaremos `BigAutoField` como PK interna por rendimiento en índices B-tree y `UUIDField` público cuando aplique).
* **Auditoría temporal:** Campos automáticos `created_at` y `updated_at`.
* **Manager Multi-Tenant:** Un `TenantManager` que facilita el filtrado explícito por empresa (`Model.objects.for_company(company_id)`).

```python
# apps/core/models.py
import uuid
from django.db import models
from django.conf import settings


class TimeStampedModel(models.Model):
    """Clase abstracta base para trazabilidad temporal en todas las tablas."""
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class TenantAwareModel(TimeStampedModel):
    """
    Clase abstracta obligatoria para cualquier entidad aislada por cliente/empresa.
    Garantiza la existencia de `company` y optimiza las consultas multi-tenant.
    """
    company = models.ForeignKey(
        'tenants.Company',
        on_delete=models.CASCADE,
        related_name='%(app_label)s_%(class)s_set',
        db_index=True,
        verbose_name="Empresa / Contribuyente"
    )

    class Meta:
        abstract = True
```

---

## 2. Diagrama Entidad-Relación (ERD Conceptual)

```text
+-------------------+       1:N       +-----------------------+
|      Company      |---------------->|   CompanyMembership   |<--- N:1 --- [User / Profile]
+-------------------+                 +-----------------------+
  |   |   |   |   |
  |   |   |   |   +--- 1:N ---> [AuditLog]
  |   |   |   +------- 1:N ---> [FiscalPeriod] <--- 1:N ---+
  |   |   +----------- 1:N ---> [AccountCatalog]           |
  |   +--------------- 1:N ---> [Document] (CFDI XML/PDF)  |
  |                                  ^                     |
  |                                  | (N:M / FK opcional) |
  +------------------- 1:N ---> [AccountingEntry] ---------+
  |                                  |
  |                                  | 1:N (Partida Doble: Sum Debit == Sum Credit)
  |                                  v
  |                           [AccountingEntryItem] ---> N:1 ---> [AccountCatalog]
  |
  +------------------- 1:N ---> [BankMovement] --(FK nula)--> [AccountingEntry] / [Document]   [E-21]
```

---

## 3. Definición Detallada de Modelos por Aplicación

### 3.1 App `tenants`: Empresas y Regímenes Fiscales

#### Modelo: `Company`
Representa a cada cliente/contribuyente administrado por el despacho contable.

| Campo | Tipo Django ORM | Restricciones / Índices | Descripción / Regla de Negocio |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | `primary_key=True` | Identificador interno único. |
| `rfc` | `CharField(max_length=13)` | `unique=True`, `db_index=True`, `RegexValidator` | RFC oficial del SAT (12 caracteres Moral, 13 Física). |
| `legal_name` | `CharField(max_length=255)` | `db_index=True` | Razón social o nombre completo sin régimen societario. |
| `tax_regime` | `CharField(max_length=10)` | `choices=TaxRegimeChoices` | Clave oficial SAT: `612` (PFAEP), `626` (RESICO), `601` (General PM). |
| `currency` | `CharField(max_length=3)` | `default='MXN'` | Moneda base contable. |
| `fiscal_year_start` | `PositiveSmallIntegerField` | `default=1` | Mes de inicio del ejercicio fiscal (Enero = 1). |
| `is_active` | `BooleanField` | `default=True`, `db_index=True` | Soft-delete / suspensión operativa del cliente. |

```python
# apps/tenants/models.py
from django.db import models
from django.core.validators import RegexValidator, MinValueValidator, MaxValueValidator
from apps.core.models import TimeStampedModel

# Nota [E-17]: los RFC de demostración deben pasar este regex (ej. CNO200101AB9, SDA210515XY1).
RFC_REGEX = r'^([A-ZÑ&]{3,4}) ?(?:- ?)?(\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])) ?(?:- ?)?([A-Z\d]{2})([A\d])$'


class Company(TimeStampedModel):
    class TaxRegime(models.TextChoices):
        PFAEP = '612', '612 - Personas Físicas con Actividades Empresariales y Profesionales'
        RESICO = '626', '626 - Régimen Simplificado de Confianza'
        GENERAL_PM = '601', '601 - General de Ley Personas Morales'

    rfc = models.CharField(
        max_length=13,
        unique=True,
        db_index=True,
        validators=[RegexValidator(regex=RFC_REGEX, message="Formato de RFC inválido según reglas del SAT.")]
    )
    legal_name = models.CharField(max_length=255, db_index=True)
    tax_regime = models.CharField(max_length=10, choices=TaxRegime.choices)
    currency = models.CharField(max_length=3, default='MXN')
    fiscal_year_start = models.PositiveSmallIntegerField(
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(12)],
        help_text="Mes de inicio del ejercicio fiscal (Enero = 1)."
    )  # [E-17] Declarado en la tabla pero omitido en el código original
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = 'tenants_company'
        ordering = ['legal_name']
        indexes = [
            models.Index(fields=['rfc', 'is_active'], name='idx_company_rfc_active'),
        ]

    def save(self, *args, **kwargs):
        self.rfc = self.rfc.upper().strip()
        super().save(*args, **kwargs)
```

---

### 3.2 App `authentication`: Usuario, Perfiles y Membresías RBAC por Empresa

#### Modelo: `User` (personalizado) `[E-10]`
El login de la API usa `email`, por lo que el proyecto define un modelo de usuario propio **antes de ejecutar la primera migración** (cambiar `AUTH_USER_MODEL` después es muy costoso). En `settings/base.py`: `AUTH_USER_MODEL = 'authentication.User'`.

```python
# apps/authentication/models.py
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra):
        if not email:
            raise ValueError("El correo electrónico es obligatorio.")
        user = self.model(email=self.normalize_email(email).lower(), **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra):
        extra.setdefault('is_staff', False)
        extra.setdefault('is_superuser', False)
        return self._create_user(email, password, **extra)

    def create_superuser(self, email, password=None, **extra):
        extra.setdefault('is_staff', True)
        extra.setdefault('is_superuser', True)
        return self._create_user(email, password, **extra)


class User(AbstractUser):
    username = None
    email = models.EmailField(unique=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name']

    objects = UserManager()

    class Meta:
        db_table = 'auth_user_custom'

    @property
    def full_name(self):
        return self.get_full_name() or self.email
```

#### Modelos: `Profile` y `CompanyMembership`
Un usuario del despacho (ej. un Auxiliar Contable) puede atender a múltiples empresas con distintos roles. Por ello, desacoplamos el `Profile` (datos globales del usuario) de `CompanyMembership` (relación N:M con rol específico por tenant).

```python
# apps/authentication/models.py
from django.db import models
from django.conf import settings
from apps.core.models import TimeStampedModel


class Profile(TimeStampedModel):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='profile'
    )
    phone = models.CharField(max_length=20, blank=True, default='')
    professional_license = models.CharField(max_length=50, blank=True, default='', help_text="Cédula profesional opcional")
    default_company = models.ForeignKey(
        'tenants.Company',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='default_for_profiles'
    )

    class Meta:
        db_table = 'auth_profile'


class CompanyMembership(TimeStampedModel):
    class Role(models.TextChoices):
        PARTNER = 'PARTNER', 'Socio / Administrador'
        ACCOUNTANT = 'ACCOUNTANT', 'Auxiliar Contable'
        AUDITOR = 'AUDITOR', 'Auditor'
        CLIENT = 'CLIENT', 'Cliente (Portal Externo)'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='company_memberships'
    )
    company = models.ForeignKey(
        'tenants.Company',
        on_delete=models.CASCADE,
        related_name='user_memberships'
    )
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.ACCOUNTANT)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = 'auth_company_membership'
        constraints = [
            models.UniqueConstraint(fields=['user', 'company'], name='uq_user_company_membership')
        ]
        indexes = [
            models.Index(fields=['user', 'company', 'is_active'], name='idx_membership_lookup'),
        ]
```

---

### 3.3 App `accounting`: Periodos Fiscales, Catálogo SAT y Pólizas

#### Modelo: `FiscalPeriod`
Controla la apertura y cierre contable mensual de cada empresa.

| Campo | Tipo Django ORM | Restricciones / Índices | Descripción / Regla de Negocio |
| :--- | :--- | :--- | :--- |
| `company` | `ForeignKey(Company)` | `db_index=True` (Heredado) | Empresa propietaria del periodo. |
| `year` | `PositiveSmallIntegerField` | `MinValueValidator(2000)` | Ejercicio fiscal (ej. `2026`). |
| `month` | `PositiveSmallIntegerField` | `MinValueValidator(1)`, `MaxValueValidator(12)` | Mes natural (`1` a `12`). |
| `is_closed` | `BooleanField` | `default=False`, `db_index=True` | Si es `True`, bloquea modificaciones en pólizas y documentos. |
| `closed_at` | `DateTimeField` | `null=True, blank=True` | Fecha/hora exacta del cierre contable. |
| `closed_by` | `ForeignKey(User)` | `null=True, blank=True, SET_NULL` | Socio que ejecutó el cierre. |

* **Restricción Única:** `UniqueConstraint(fields=['company', 'year', 'month'], name='uq_company_fiscal_period')`.

#### Modelo: `AccountCatalog`
Catálogo de cuentas contables homolgado con el Anexo 24 del SAT (Código Agrupador) y estructura jerárquica (Cuenta de Mayor / Subcuenta).

| Campo | Tipo Django ORM | Restricciones / Índices | Descripción / Regla de Negocio |
| :--- | :--- | :--- | :--- |
| `company` | `ForeignKey(Company)` | `db_index=True` (Heredado) | Empresa propietaria del catálogo clonado. |
| `parent` | `ForeignKey('self')` | `null=True, blank=True, PROTECT` | Cuenta padre para estructura jerárquica (Mayor -> Subcuenta). |
| `code` | `CharField(max_length=30)` | `db_index=True` | Código interno de cuenta (ej. `102.01.001`). |
| `sat_group_code` | `CharField(max_length=15)` | `db_index=True` | Código agrupador oficial SAT (ej. `102.01` Bancos nacionales). |
| `name` | `CharField(max_length=255)` | - | Nombre descriptivo de la cuenta contable. |
| `account_type` | `CharField(max_length=20)` | `choices` | `ASSET`, `LIABILITY`, `EQUITY`, `REVENUE`, `EXPENSE`, `ORDER`. |
| `nature` | `CharField(max_length=10)` | `choices` | Naturaleza contable: `DEBIT` (Deudora) o `CREDIT` (Acreedora). |
| `is_selectable` | `BooleanField` | `default=True` | `False` para cuentas acumulativas (Mayor); `True` para afectables. |
| `is_active` | `BooleanField` | `default=True` | Permite desactivar cuentas sin perder historial contable. |

* **Restricción Única:** `UniqueConstraint(fields=['company', 'code'], name='uq_company_account_code')`.

#### Modelos: `AccountingEntry` y `AccountingEntryItem` (Partida Doble)
Garantizan la integridad contable mediante atomicidad transaccional y validación estricta de partida doble en la capa de modelo (`clean()`).

```python
# apps/accounting/models.py
from decimal import Decimal
from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from apps.core.models import TenantAwareModel


class FiscalPeriod(TenantAwareModel):
    year = models.PositiveSmallIntegerField(validators=[MinValueValidator(2000), MaxValueValidator(2100)])
    month = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(12)])
    is_closed = models.BooleanField(default=False, db_index=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='closed_fiscal_periods'
    )

    class Meta:
        db_table = 'accounting_fiscal_period'
        ordering = ['-year', '-month']
        constraints = [
            models.UniqueConstraint(fields=['company', 'year', 'month'], name='uq_company_fiscal_period')
        ]
        indexes = [
            models.Index(fields=['company', 'year', 'month', 'is_closed'], name='idx_period_company_status'),
        ]

    def __str__(self):
        return f"{self.company.rfc} | {self.year}-{self.month:02d}"


class AccountCatalog(TenantAwareModel):
    class AccountType(models.TextChoices):
        ASSET = 'ASSET', 'Activo'
        LIABILITY = 'LIABILITY', 'Pasivo'
        EQUITY = 'EQUITY', 'Capital Contable'
        REVENUE = 'REVENUE', 'Ingresos'
        EXPENSE = 'EXPENSE', 'Costos y Gastos'
        ORDER = 'ORDER', 'Cuentas de Orden'

    class Nature(models.TextChoices):
        DEBIT = 'DEBIT', 'Deudora'
        CREDIT = 'CREDIT', 'Acreedora'

    parent = models.ForeignKey(
        'self',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='children'
    )
    code = models.CharField(max_length=30, db_index=True)
    sat_group_code = models.CharField(max_length=15, db_index=True)
    name = models.CharField(max_length=255)
    account_type = models.CharField(max_length=20, choices=AccountType.choices)
    nature = models.CharField(max_length=10, choices=Nature.choices)
    is_selectable = models.BooleanField(
        default=True,
        help_text="True si recibe movimientos directos (subcuenta); False si es cuenta de mayor acumulativa."
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'accounting_account_catalog'
        ordering = ['code']
        constraints = [
            models.UniqueConstraint(fields=['company', 'code'], name='uq_company_account_code')
        ]
        indexes = [
            models.Index(fields=['company', 'sat_group_code'], name='idx_account_company_sat'),
            models.Index(fields=['company', 'is_selectable', 'is_active'], name='idx_account_selectable'),
        ]


class AccountingEntry(TenantAwareModel):
    class EntryType(models.TextChoices):
        INCOME = 'INCOME', 'Póliza de Ingresos'
        EXPENSE = 'EXPENSE', 'Póliza de Egresos'
        JOURNAL = 'JOURNAL', 'Póliza de Diario'

    class Status(models.TextChoices):
        DRAFT = 'DRAFT', 'Borrador'
        POSTED = 'POSTED', 'Contabilizada'

    fiscal_period = models.ForeignKey(
        FiscalPeriod,
        on_delete=models.PROTECT,
        related_name='entries'
    )
    entry_type = models.CharField(max_length=15, choices=EntryType.choices)
    # [E-15] Generado por services.next_folio(company, entry_type, year) con select_for_update.
    # Prefijos ING / EGR / DIA; formato ING-2026-0014.
    folio = models.CharField(max_length=30, db_index=True)
    entry_date = models.DateField(db_index=True)
    concept = models.CharField(max_length=500)
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.POSTED, db_index=True)
    total_debit = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    total_credit = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='created_entries'
    )

    class Meta:
        db_table = 'accounting_entry'
        ordering = ['-entry_date', '-folio']
        constraints = [
            models.UniqueConstraint(fields=['company', 'fiscal_period', 'entry_type', 'folio'], name='uq_entry_folio_period')
        ]
        indexes = [
            models.Index(fields=['company', 'fiscal_period', 'entry_date'], name='idx_entry_company_period_date'),
        ]

    def clean(self):
        super().clean()
        # 1. Validación estricta de aislamiento entre modelos relacionados
        if self.fiscal_period_id and self.fiscal_period.company_id != self.company_id:
            raise ValidationError("El periodo fiscal no pertenece a la empresa seleccionada.")

        # 2. Bloqueo de periodo cerrado
        if self.fiscal_period_id and self.fiscal_period.is_closed:
            raise ValidationError(
                f"El periodo fiscal {self.fiscal_period.year}-{self.fiscal_period.month:02d} se encuentra cerrado. No se permiten modificaciones."
            )

        # 3. Validación de coincidencia de fecha con el periodo fiscal
        if self.entry_date and self.fiscal_period_id:
            if self.entry_date.year != self.fiscal_period.year or self.entry_date.month != self.fiscal_period.month:
                raise ValidationError("La fecha de la póliza debe corresponder al mes y año del periodo fiscal asignado.")

    def validate_double_entry(self):
        """
        Valida matemáticamente la partida doble sobre los renglones persistidos o en memoria
        dentro de un bloque transaction.atomic().
        """
        # [E-15] Aplica por igual a pólizas POSTED y DRAFT: un borrador también debe estar cuadrado.
        items = list(self.items.all())
        if len(items) < 2:
            raise ValidationError("Una póliza contable debe contener al menos dos movimientos.")

        sum_debit = sum((item.debit for item in items), Decimal('0.00'))
        sum_credit = sum((item.credit for item in items), Decimal('0.00'))

        if sum_debit <= Decimal('0.00') or sum_credit <= Decimal('0.00'):
            raise ValidationError("La suma de cargos y abonos debe ser estrictamente mayor a cero.")

        if sum_debit != sum_credit:
            raise ValidationError(
                f"Póliza descuadrada: Suma de Cargos (${sum_debit}) != Suma de Abonos (${sum_credit})."
            )

        self.total_debit = sum_debit
        self.total_credit = sum_credit


class AccountingEntryItem(TenantAwareModel):
    entry = models.ForeignKey(
        AccountingEntry,
        on_delete=models.CASCADE,
        related_name='items'
    )
    account = models.ForeignKey(
        AccountCatalog,
        on_delete=models.PROTECT,
        related_name='entry_items'
    )
    document = models.ForeignKey(
        'documents.Document',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='accounting_items',
        help_text="CFDI / Documento soporte vinculado a este movimiento"
    )
    line_number = models.PositiveSmallIntegerField(default=1)
    description = models.CharField(max_length=255, blank=True, default='')
    debit = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    credit = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))]
    )

    class Meta:
        db_table = 'accounting_entry_item'
        ordering = ['line_number']
        indexes = [
            models.Index(fields=['company', 'account'], name='idx_item_company_account'),
            models.Index(fields=['company', 'document'], name='idx_item_company_document'),
        ]

    def clean(self):
        super().clean()
        # El renglón debe pertenecer a la misma empresa que su póliza.
        if self.entry_id and self.entry.company_id != self.company_id:
            raise ValidationError("El renglón no pertenece a la empresa de la póliza.")
        if self.account_id and self.account.company_id != self.company_id:
            raise ValidationError("La cuenta contable no pertenece a la empresa de la póliza.")
        if self.account_id and not self.account.is_selectable:
            raise ValidationError(f"La cuenta {self.account.code} es acumulativa y no acepta movimientos directos.")
        if self.debit > Decimal('0.00') and self.credit > Decimal('0.00'):
            raise ValidationError("Un mismo renglón no puede tener cargo y abono simultáneamente.")
        if self.debit == Decimal('0.00') and self.credit == Decimal('0.00'):
            raise ValidationError("El renglón debe tener un monto mayor a cero en Cargo o Abono.")
```

---

### 3.4 App `documents`: Gestión de CFDI 4.0 (XML) y Respaldos PDF

#### Modelo: `Document`
Implementa el **enfoque híbrido** acordado: columnas `DecimalField(max_digits=12, decimal_places=2)` dedicadas para importes fiscales críticos e índice único compuesto `UniqueConstraint(fields=['company', 'uuid'])` (condicional a `uuid IS NOT NULL`) con índices B-tree estándar, complementado con `JSONField` para nodos flexibles. Almacenamiento y descargas: ver `[E-07]`.

```python
# apps/documents/models.py
from decimal import Decimal
from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from apps.core.models import TenantAwareModel


import os
from uuid import uuid4
from django.utils import timezone


def document_upload_path(instance, filename):
    """
    [E-07] El nombre original NUNCA se usa en el sistema de archivos (previene path traversal).
    Ruta: companies/{company_id}/documents/{yyyy}/{mm}/{uuid4}.{ext}
    El nombre original se conserva en Document.original_filename.
    """
    ext = os.path.basename(filename).rsplit('.', 1)[-1].lower()
    local_date = timezone.localtime(instance.issue_date)  # [E-11] fecha local de México
    return f"companies/{instance.company_id}/documents/{local_date:%Y}/{local_date:%m}/{uuid4()}.{ext}"


class Document(TenantAwareModel):
    class Direction(models.TextChoices):
        ISSUED = 'ISSUED', 'Emitido (Ingreso/Venta)'
        RECEIVED = 'RECEIVED', 'Recibido (Gasto/Compra)'

    class CfdiType(models.TextChoices):
        INGRESO = 'I', 'I - Ingreso'
        EGRESO = 'E', 'E - Egreso'
        TRASLADO = 'T', 'T - Traslado'
        NOMINA = 'N', 'N - Nómina'
        PAGO = 'P', 'P - Pago'
        MANUAL = 'M', 'M - Comprobante Manual sin XML'

    fiscal_period = models.ForeignKey(
        'accounting.FiscalPeriod',
        on_delete=models.PROTECT,
        related_name='documents'
    )
    uuid = models.UUIDField(
        null=True,
        blank=True,
        help_text="Folio Fiscal (Timbre Fiscal Digital), normalizado a minúsculas. Null únicamente para comprobantes manuales sin XML."
    )  # [E-16] Sin db_index: el UniqueConstraint (company, uuid) ya crea el índice.
    direction = models.CharField(max_length=10, choices=Direction.choices, db_index=True)
    cfdi_type = models.CharField(max_length=2, choices=CfdiType.choices, default=CfdiType.INGRESO, db_index=True)
    cfdi_version = models.CharField(max_length=5, default='4.0')  # '4.0' o '3.3'
    original_filename = models.CharField(max_length=255, blank=True, default='')  # [E-16] solo informativo

    class SatStatus(models.TextChoices):  # [E-16]
        VALID = 'VALID', 'Vigente'
        CANCELLED = 'CANCELLED', 'Cancelado'
        UNVERIFIED = 'UNVERIFIED', 'Sin verificar'

    # El MVP solo valida la estructura; no consulta el webservice del SAT.
    sat_status = models.CharField(max_length=12, choices=SatStatus.choices, default=SatStatus.UNVERIFIED, db_index=True)
    series = models.CharField(max_length=25, blank=True, default='')
    folio = models.CharField(max_length=40, blank=True, default='')
    issue_date = models.DateTimeField(db_index=True)

    # Datos de Emisor y Receptor
    issuer_rfc = models.CharField(max_length=13, db_index=True)
    issuer_name = models.CharField(max_length=255)
    receiver_rfc = models.CharField(max_length=13, db_index=True)
    receiver_name = models.CharField(max_length=255)

    # Claves de Pago SAT
    payment_method = models.CharField(max_length=5, blank=True, default='', help_text="PUE o PPD")
    payment_form = models.CharField(max_length=5, blank=True, default='', help_text="01 Efectivo, 03 Transferencia, etc.")
    currency = models.CharField(max_length=3, default='MXN')
    exchange_rate = models.DecimalField(max_digits=10, decimal_places=4, default=Decimal('1.0000'))

    # Columnas Fiscales Duras (Optimizadas para SUM/AGGREGATE en PostgreSQL)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    discount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    iva_transferred = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), help_text="IVA Trasladado")
    ieps_transferred = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), help_text="IEPS Trasladado")
    iva_retained = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), help_text="IVA Retenido")
    isr_retained = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), help_text="ISR Retenido")
    total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))

    # Almacenamiento Híbrido para Metadatos Flexibles (Conceptos, Complementos, Impuestos Locales)
    raw_metadata = models.JSONField(default=dict, blank=True)

    # Archivos Físicos
    xml_file = models.FileField(upload_to=document_upload_path, null=True, blank=True)
    pdf_file = models.FileField(upload_to=document_upload_path, null=True, blank=True)

    is_accounted = models.BooleanField(default=False, db_index=True, help_text="True si ya tiene póliza vinculada")
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='uploaded_documents'
    )

    class Meta:
        db_table = 'documents_document'
        ordering = ['-issue_date']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'uuid'],
                condition=models.Q(uuid__isnull=False),
                name='uq_company_cfdi_uuid'
            )
        ]
        indexes = [
            # [E-16] Se eliminó idx_doc_company_uuid: es redundante con uq_company_cfdi_uuid.
            models.Index(fields=['company', 'fiscal_period', 'direction'], name='idx_doc_period_direction'),
            models.Index(fields=['company', 'issue_date'], name='idx_doc_company_date'),
            models.Index(fields=['company', 'is_accounted'], name='idx_doc_company_accounted'),
        ]

    def clean(self):
        super().clean()
        if self.fiscal_period_id and self.fiscal_period.is_closed:
            raise ValidationError("No se pueden cargar o modificar documentos en un periodo fiscal cerrado.")
        if self.cfdi_type != self.CfdiType.MANUAL and not self.uuid:
            raise ValidationError("Todo comprobante CFDI debe contar con un UUID válido.")
        if self.cfdi_type == self.CfdiType.MANUAL and not self.pdf_file:
            raise ValidationError("Los comprobantes manuales sin XML requieren adjuntar un archivo PDF o imagen de respaldo.")
```

---

### 3.5 App `core`: Bitácora Inmutable de Auditoría (`AuditLog`)

#### Modelo: `AuditLog`
Registra eventos críticos de seguridad y gobierno contable (ej. reapertura extraordinaria de un `FiscalPeriod` cerrado, eliminación de pólizas, cambios de roles RBAC).

```python
# apps/core/models.py (Continuación)
from django.core.exceptions import ValidationError


class ImmutableQuerySet(models.QuerySet):
    """[E-18] Impide borrado y actualización masiva de registros de auditoría."""
    def delete(self):
        raise ValidationError("Los registros de AuditLog son inmutables y no pueden ser eliminados.")

    def update(self, **kwargs):
        raise ValidationError("Los registros de AuditLog son inmutables y no pueden ser modificados.")


class AuditLog(TimeStampedModel):
    class ActionType(models.TextChoices):
        PERIOD_CLOSED = 'PERIOD_CLOSED', 'Cierre de Periodo Fiscal'
        PERIOD_REOPENED = 'PERIOD_REOPENED', 'Reapertura Extraordinaria de Periodo'
        ENTRY_DELETED = 'ENTRY_DELETED', 'Eliminación de Póliza'
        ROLE_CHANGED = 'ROLE_CHANGED', 'Cambio de Rol de Usuario'
        CATALOG_MODIFIED = 'CATALOG_MODIFIED', 'Modificación de Catálogo Contable'

    company = models.ForeignKey(
        'tenants.Company',
        on_delete=models.CASCADE,
        related_name='audit_logs',
        db_index=True
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='audit_logs'
    )
    action = models.CharField(max_length=30, choices=ActionType.choices, db_index=True)
    target_model = models.CharField(max_length=100)
    target_id = models.CharField(max_length=64)
    justification = models.TextField(
        blank=True,
        default='',
        help_text="Motivo de la acción. El mínimo de 15 caracteres en la reapertura de periodos "
                  "se valida en PeriodReopenSerializer, no en el modelo."
    )  # [E-18]
    previous_state = models.JSONField(default=dict, blank=True)
    new_state = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    objects = ImmutableQuerySet.as_manager()

    class Meta:
        db_table = 'core_audit_log'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['company', 'action', '-created_at'], name='idx_audit_company_action_date'),
        ]

    def save(self, *args, **kwargs):
        # [E-18] Solo se permite la inserción inicial; un registro existente no se modifica.
        if not self._state.adding:
            raise ValidationError("Los registros de AuditLog son inmutables y no pueden ser modificados.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Los registros de AuditLog son inmutables y no pueden ser eliminados.")
```

---

### 3.6 App `reconciliation`: Movimientos Bancarios `[E-21]`

El modelo `BankMovement` (`TenantAwareModel`) y sus restricciones (`row_hash` único por empresa, `deposit`/`withdrawal` mutuamente excluyentes, FK nulas a `AccountingEntry` y `Document`) se definen en `00_ERRATA.md` §2.1. Estado: `PENDING` / `RECONCILED`.

---

## 4. Patrón Estándar de Persistencia Atómica (Partida Doble)

Para cumplir con la decisión arquitectónica #3, toda creación o actualización de pólizas contables desde la capa de servicios (`apps/accounting/services.py`) deberá ejecutarse estrictamente bajo el siguiente patrón transaccional:

```python
from django.db import transaction

def create_accounting_entry(*, company, fiscal_period, user, header_data, items_data):
    with transaction.atomic():
        entry = AccountingEntry(
            company=company,
            fiscal_period=fiscal_period,
            created_by=user,
            **header_data
        )
        entry.full_clean()  # Valida tenant isolation y que fiscal_period.is_closed == False
        entry.save()

        for idx, item_dict in enumerate(items_data, start=1):
            item = AccountingEntryItem(
                company=company,
                entry=entry,
                line_number=idx,
                **item_dict
            )
            item.full_clean()  # Valida cuenta afectable y cargo/abono excluyente
            item.save()

        # Valida sum(debit) == sum(credit) > 0; lanza ValidationError y dispara rollback automático si falla
        entry.validate_double_entry()
        entry.save(update_fields=['total_debit', 'total_credit'])

        return entry
```

**Reglas complementarias:**
* **Periodo `[E-14]`:** `fiscal_period` se resuelve con `get_or_create_period(company, date)` a partir de la fecha local. Si el payload lo trae, debe coincidir con la fecha.
* **Folio `[E-15]`:** `header_data['folio']` se asigna con `next_folio(company, entry_type, year)` dentro de la misma transacción.
* **Cargas parciales `[E-24]`:** no se usa `ATOMIC_REQUESTS`; la carga masiva de documentos abre un `transaction.atomic()` por archivo.
# Especificación Técnica de API Backend y Capa RESTful (`03_BACKEND_API_SPEC.md`)

Este documento define el contrato técnico de la API RESTful construida sobre **Django 5.x + Django REST Framework (DRF)** para ser consumida por el cliente SPA en **Vue 3**. Establece las reglas de autenticación JWT, inyección de contexto multi-tenant mediante `X-Company-ID`, matriz de permisos RBAC, contratos de endpoints/serializers y el estándar global de respuestas JSON.

> **Precedencia:** `docs/00_ERRATA.md` prevalece sobre este documento. Los puntos ajustados por la errata se marcan con `[E-xx]`.

---

## 1. Arquitectura Transversal: Autenticación JWT y Contexto Multi-Tenant

### 1.1 Flujo de Autenticación (`djangorestframework-simplejwt`)
La autenticación es *stateless* basada en tokens Bearer JWT (`Authorization: Bearer <access_token>`).

* **Configuración de Tokens:**
  * `ACCESS_TOKEN_LIFETIME`: `30 minutos`.
  * `REFRESH_TOKEN_LIFETIME`: `12 horas` (con `ROTATE_REFRESH_TOKENS = True` y `BLACKLIST_AFTER_ROTATION = True`).
  * **Modelo de usuario `[E-10]`:** `authentication.User` personalizado (`email` único como `USERNAME_FIELD`).
  * **Throttling `[E-09]`:** `POST /auth/login/` limitado a **5 intentos por minuto por IP** (`429 Too Many Requests`, código `throttled`).
* **Claims Personalizados (`CustomTokenObtainPairSerializer`):**
  El payload del `access_token` incluirá metadatos globales del usuario (sin fijar una empresa rígida para permitir el cambio dinámico de cliente en el frontend sin re-autenticar):
  ```json
  {
    "user_id": 12,
    "email": "contador@despacho.mx",
    "full_name": "Laura Méndez",
    "is_superuser": false
  }
  ```
* **Respuesta de Login (`POST /api/v1/auth/login/`):**
  Además de `access` y `refresh`, devuelve el perfil y el arreglo inicial de empresas asignadas (`memberships`) con su rol correspondiente para hidratar `useAuthStore` y `useTenantStore` en Vue 3 `[E-01]`.

### 1.2 Inyección y Validación de Contexto Multi-Tenant (`TenantContextMixin`) `[E-03]`
La validación **no** es un middleware de Django: la autenticación JWT ocurre dentro de DRF (después de los middlewares), por lo que `request.user` aún no existe en esa capa. `TenantContextMixin` se ejecuta en `initial()` de la vista DRF, una vez autenticado el usuario.

Todas las peticiones a rutas operativas deben incluir el encabezado HTTP:
```http
X-Company-ID: <company_id_entero>
```

#### Clasificación de Rutas y Reglas de Validación:
1. **Rutas Exentas de `X-Company-ID` (Globales / Arranque de Sesión):**
   * `POST /api/v1/auth/login/`, `POST /api/v1/auth/refresh/`, `POST /api/v1/auth/logout/`
   * `GET /api/v1/auth/me/`
   * `GET /api/v1/companies/` (Lista todas las empresas donde el usuario tiene `CompanyMembership.is_active=True`).
   * `POST /api/v1/companies/` (Alta de nueva empresa; asigna automáticamente al creador como `PARTNER`).
   * `GET /api/v1/health/` (sin autenticación).

2. **Rutas Operativas (Exigen `X-Company-ID` Obligatorio):**
   * Incluye `/api/v1/companies/{id}/` (detalle/edición), `/api/v1/accounts/`, `/api/v1/documents/`, `/api/v1/entries/`, `/api/v1/periods/`, `/api/v1/reconciliation/`, `/api/v1/reports/`, `/api/v1/audit-logs/`.
   * `/api/v1/documents/{id}/download/` es operativa: exige `X-Company-ID` (el frontend la descarga como *blob* con el Bearer) `[E-07]`.
   * **Algoritmo de Interceptación en el Request:**
     1. Extraer `raw_company_id = request.headers.get("X-Company-ID")`.
     2. **Validación de Formato (`400 Bad Request`):** Si `raw_company_id` es nulo, vacío o no es un entero positivo válido, abortar inmediatamente con código de error `missing_or_invalid_tenant_header`.
     3. **Validación de Membresía (`403 Forbidden`):** Consultar `CompanyMembership` activo para `(user=request.user, company_id=int(raw_company_id), company__is_active=True)`. Si no existe, abortar con código `tenant_access_denied`.
     4. **Inyección en `request`:** Adjuntar `request.company` (instancia de `Company`) y `request.membership` (instancia de `CompanyMembership` con su `role`).

3. **Aislamiento Automático en `QuerySet` (`TenantQuerySetMixin`):**
   Todos los `ViewSets` operativos heredarán de `TenantQuerySetMixin`, el cual sobrescribe `get_queryset()` para ejecutar obligatoriamente `super().get_queryset().filter(company=self.request.company)` y `perform_create()` para inyectar `company=self.request.company`.

---

## 2. Matriz de Permisos por Rol (RBAC en DRF)

Las clases de permisos residen en `apps/authentication/permissions.py` y evalúan `request.membership.role` (garantizando previamente que `request.company` fue resuelto).

### 2.1 Catálogo de Clases de Permisos (`BasePermission`)

| Clase DRF | Roles Permitidos | Regla de Evaluación |
| :--- | :--- | :--- |
| `IsTenantMember` | `PARTNER`, `ACCOUNTANT`, `AUDITOR`, `CLIENT` | Verifica que exista `request.membership` activo para el `X-Company-ID` enviado. |
| `IsPartnerRole` | `PARTNER` | Permite acceso total (lectura/escritura/borrado/acciones administrativas). |
| `CanManageAccounting` | `PARTNER`, `ACCOUNTANT` | Permite `GET`, `POST`, `PUT`, `PATCH`. Deniega `DELETE` a `ACCOUNTANT` en registros históricos/contabilizados. |
| `IsReadOnlyAuditor` | `AUDITOR` | Permite únicamente métodos seguros (`SAFE_METHODS`: `GET`, `HEAD`, `OPTIONS`). |
| `IsClientPortalAllowed` | `CLIENT` | Restringe el acceso exclusivamente a endpoints habilitados para el portal externo (Documentos propios de la empresa y Reportes básicos). |
| `IsFiscalPeriodOpen` | *(Validación de Estado)* | Permiso de nivel de objeto/payload: bloquea `POST`, `PUT`, `PATCH`, `DELETE` si `fiscal_period.is_closed == True`. |

### 2.2 Aplicación de Permisos por Recurso y Método HTTP

| Recurso / Endpoint | `PARTNER` (Socio/Admin) | `ACCOUNTANT` (Auxiliar) | `AUDITOR` | `CLIENT` (Portal Externo) |
| :--- | :---: | :---: | :---: | :---: |
| `GET /companies/` | Permitido (Sus empresas) | Permitido (Sus empresas) | Permitido (Sus empresas) | Permitido (Su empresa) |
| `POST /companies/` | Permitido | Denegado (`403`) | Denegado (`403`) | Denegado (`403`) |
| `PATCH/DELETE /companies/{id}/` | Permitido | Denegado (`403`) | Denegado (`403`) | Denegado (`403`) |
| `CRUD /companies/{id}/members/` | Permitido | Denegado (`403`) | Denegado (`403`) | Denegado (`403`) |
| `GET /accounts/` | Permitido | Permitido | Permitido | Denegado (`403`) |
| `POST/PATCH/DELETE /accounts/` | Permitido | Solo `PATCH` del campo `name` (No crear/borrar) `[E-12]` | Denegado (`403`) | Denegado (`403`) |
| `GET /documents/` | Permitido | Permitido | Permitido | Permitido (Toda su empresa) |
| `POST /documents/bulk-upload/` (XML y PDF) | Permitido (Periodo abierto) | Permitido (Periodo abierto) | Denegado (`403`) | Permitido (Periodo abierto) |
| `POST /documents/manual/` · `POST /documents/{id}/pdf/` | Permitido (Periodo abierto) | Permitido (Periodo abierto) | Denegado (`403`) | Permitido (Periodo abierto) |
| `GET /documents/{id}/download/` | Permitido | Permitido | Permitido | Permitido (Su empresa) |
| `DELETE /documents/{id}/` | Permitido (Si no contabilizado) | Denegado (`403`) | Denegado (`403`) | Denegado (`403`) |
| `GET /entries/` | Permitido | Permitido | Permitido | Denegado (`403`) |
| `POST/PATCH /entries/` | Permitido (Periodo abierto) | Permitido (Periodo abierto) | Denegado (`403`) | Denegado (`403`) |
| `DELETE /entries/{id}/` | Permitido (Con `AuditLog`) | Denegado (`403`) | Denegado (`403`) | Denegado (`403`) |
| `GET /periods/` | Permitido | Permitido | Permitido | Denegado (`403`) |
| `POST /periods/{id}/close/` | Permitido | Denegado (`403`) | Denegado (`403`) | Denegado (`403`) |
| `POST /periods/{id}/reopen/` | Permitido (Justificación obligatoria) | Denegado (`403`) | Denegado (`403`) | Denegado (`403`) |
| `GET /reports/executive-summary/` | Permitido | Permitido | Permitido | Permitido (Vista resumida) |
| `GET /reports/trial-balance/` | Permitido | Permitido | Permitido | Denegado (`403`) |
| `GET /reconciliation/movements/` (y `suggestions/`) | Permitido | Permitido | Permitido | Denegado (`403`) |
| `POST /reconciliation/movements/import/ · {id}/match/ · {id}/unmatch/` | Permitido (Periodo abierto) | Permitido (Periodo abierto) | Denegado (`403`) | Denegado (`403`) |
| `GET /audit-logs/` | Permitido | Denegado (`403`) | Permitido | Denegado (`403`) |

> `[E-12]` / `[E-13]`: el rol `CLIENT` ve **todos los documentos de su empresa** (no solo los que subió él) y nunca puede borrar. El `ACCOUNTANT` nunca puede borrar documentos, pólizas ni cuentas.

---

## 3. Especificación de Endpoints Core (`/api/v1/`)

Todos los endpoints utilizan `JSONParser` (excepto cargas de archivos que usan `MultiPartParser` / `FormParser`), paginación estándar `PageNumberPagination` (`page_size = 25`, `max_page_size = 100`) y filtros mediante `django-filter`.

### 3.1 Autenticación y Sesión (`apps/authentication`)

#### `POST /api/v1/auth/login/`
* **Headers requeridos:** Ninguno.
* **Request Payload (`LoginSerializer`):**
  ```json
  {
    "email": "laura.mendez@despacho.mx",
    "password": "••••••••••••"
  }
  ```
* **Response `200 OK` (`data`):**
  ```json
  {
    "tokens": {
      "access": "eyJhbGciOiJIUzI1NiIs...",
      "refresh": "eyJhbGciOiJIUzI1NiIs..."
    },
    "user": {
      "id": 12,
      "email": "laura.mendez@despacho.mx",
      "full_name": "Laura Méndez",
      "default_company_id": 4
    },
    "memberships": [
      {
        "company_id": 4,
        "rfc": "CME210514AB9",
        "legal_name": "Comercializadora Mexicana del Centro S.A. de C.V.",
        "tax_regime": "601",
        "role": "PARTNER"
      }
    ]
  }
  ```

---

### 3.2 Empresas y Membresías (`apps/tenants`)

#### `GET /api/v1/companies/`
* **Headers requeridos:** `Authorization` (No requiere `X-Company-ID`).
* **Comportamiento:** Retorna únicamente las empresas activas asociadas al usuario autenticado vía `CompanyMembership`.
* **Serializer (`CompanyListSerializer`):** `id`, `rfc`, `legal_name`, `tax_regime`, `tax_regime_display`, `currency`, `user_role` (anotado desde la membresía).

#### `POST /api/v1/companies/`
* **Headers requeridos:** `Authorization`.
* **Permisos `[E-22]`:** Usuarios con rol `PARTNER` en al menos un tenant o `is_superuser`. No existe auto-registro de usuarios.
* **Request Payload (`CompanyCreateSerializer`):**
  ```json
  {
    "rfc": "GARC850912H10",
    "legal_name": "Carlos García Rodríguez",
    "tax_regime": "626",
    "currency": "MXN"
  }
  ```
* **Efecto Secundario Transaccional:** Al crear la empresa, dentro de la misma transacción, dispara el servicio `clone_master_sat_catalog(company)` y crea la `CompanyMembership` con `role="PARTNER"` para el usuario creador.

#### `GET /api/v1/companies/{id}/members/` & `POST /api/v1/companies/{id}/members/`
* **Headers requeridos:** `Authorization`, `X-Company-ID` (debe coincidir con `{id}`).
* **Permisos:** `IsPartnerRole`.
* **Payload `POST` (`CompanyMembershipSerializer`):** `email` (**solo usuarios existentes** `[E-22]`; no hay invitaciones), `role` (`PARTNER`, `ACCOUNTANT`, `AUDITOR`, `CLIENT`).

---

### 3.3 Catálogo de Cuentas SAT (`apps/accounting`)

#### `GET /api/v1/accounts/`
* **Headers requeridos:** `Authorization`, `X-Company-ID`.
* **Permisos:** `IsTenantMember` (Excluye `CLIENT`).
* **Query Params:** `?search=` (código o nombre), `?account_type=ASSET`, `?is_selectable=true`, `?tree=true` (opcional para vista jerárquica).
* **Serializer (`AccountCatalogSerializer`):**
  ```json
  {
    "id": 204,
    "parent": 201,
    "code": "102.01.001",
    "sat_group_code": "102.01",
    "name": "BBVA Bancomer Cuenta 0192837465",
    "account_type": "ASSET",
    "nature": "DEBIT",
    "is_selectable": true,
    "is_active": true
  }
  ```

#### `POST /api/v1/accounts/` & `PATCH /api/v1/accounts/{id}/`
* **Permisos `[E-12]`:** `IsPartnerRole` para `POST`, desactivación (`is_active=false`) y cambios de `code`, `parent`, `account_type`, `nature`. El `ACCOUNTANT` solo puede hacer `PATCH` del campo `name`; el `AUDITOR` y el `CLIENT` reciben `403`.
* **Validaciones del Serializer:**
  * Unicidad de `code` dentro de `request.company`.
  * Si `parent` tiene movimientos contables previos, no puede usarse como cuenta padre.
  * Impide cambiar `account_type` o `nature` si la cuenta ya tiene `AccountingEntryItem` asociados.

---

### 3.4 Documentos y Carga Masiva CFDI 4.0 (`apps/documents`)

#### `GET /api/v1/documents/`
* **Headers requeridos:** `Authorization`, `X-Company-ID`.
* **Permisos:** `IsTenantMember` (Incluye `CLIENT`, viendo todos los documentos de su `company_id`).
* **Query Params:** `?fiscal_period=18`, `?direction=RECEIVED`, `?cfdi_type=I`, `?is_accounted=false`, `?search=` (UUID, RFC o Razón Social).
* **Serializer (`DocumentListSerializer`):**
  `id`, `uuid`, `direction`, `cfdi_type`, `series`, `folio`, `issue_date`, `issuer_rfc`, `issuer_name`, `receiver_rfc`, `receiver_name`, `payment_method`, `subtotal`, `iva_transferred`, `iva_retained`, `isr_retained`, `total`, `is_accounted`, `sat_status`, `original_filename`, `xml_url`, `pdf_url`.
* **`xml_url` / `pdf_url` `[E-07]`:** apuntan a `/api/v1/documents/{id}/download/?file=xml|pdf`, un endpoint autenticado que verifica la empresa. `MEDIA_ROOT` nunca se sirve directamente. Los montos se serializan como *string* `[E-23]`.
* **Respuesta paginada `[E-19]`:** `data = {count, next, previous, results}`.

#### `POST /api/v1/documents/bulk-upload/` (Procesamiento Parcial)
* **Headers requeridos:** `Authorization`, `X-Company-ID`, `Content-Type: multipart/form-data`.
* **Permisos:** `PARTNER`, `ACCOUNTANT`, `CLIENT`.
* **Request Payload (`BulkDocumentUploadSerializer`):**
  * `files`: Lista de archivos `.xml` y `.pdf` `[E-06]` (máximo **50 archivos por petición**; XML ≤ **2 MB**, PDF ≤ **5 MB** `[E-04]`). Cada PDF se empareja con el XML de mismo nombre base dentro del lote; un PDF sin pareja se reporta como `orphan_pdf`.
  * `direction` *(opcional)*: Si se omite, el parser infiere `ISSUED` si `issuer_rfc == company.rfc` o `RECEIVED` si `receiver_rfc == company.rfc`.
* **Flujo de Procesamiento Parcial:**
  1. Itera archivo por archivo sin envolver todo el lote en una única transacción abortable.
  2. Parsea el XML con `defusedxml.ElementTree` `[E-05]` (protección XXE / *billion laughs*), valida esquema CFDI 3.3/4.0 y verifica que `issuer_rfc` o `receiver_rfc` corresponda al RFC de `request.company`.
  3. Resuelve o crea automáticamente el `FiscalPeriod` del mes de `issue_date`. Si `fiscal_period.is_closed == True`, rechaza ese archivo individual.
  4. Verifica duplicidad por `(company, uuid)` (UUID normalizado a minúsculas).
  5. Cada archivo se procesa dentro de su propio `transaction.atomic()` `[E-24]`; no se usa `ATOMIC_REQUESTS`.
* **Códigos de fallo por archivo:** `invalid_xml`, `not_cfdi`, `rfc_mismatch`, `duplicate_cfdi_uuid`, `period_closed`, `file_too_large`, `invalid_file_type`, `orphan_pdf`.
* **Response `200 OK` (Incluso si hubo fallos parciales, detallados en `data`):**
  ```json
  {
    "success": true,
    "message": "Procesamiento masivo finalizado: 8 comprobantes importados, 2 omitidos con errores.",
    "data": {
      "summary": {
        "total_received": 10,
        "processed_count": 8,
        "failed_count": 2
      },
      "processed": [
        {
          "filename": "FAC_A102.xml",
          "document_id": 541,
          "uuid": "550e8400-e29b-41d4-a716-446655440000",
          "direction": "RECEIVED",
          "total": "4640.00"
        }
      ],
      "failed": [
        {
          "filename": "FAC_A099.xml",
          "uuid": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
          "code": "duplicate_cfdi_uuid",
          "message": "El UUID ya se encuentra registrado en esta empresa."
        },
        {
          "filename": "FAC_OCT_01.xml",
          "uuid": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
          "code": "period_closed",
          "message": "El periodo fiscal 2026-10 se encuentra cerrado."
        }
      ]
    },
    "errors": null
  }
  ```

#### `POST /api/v1/documents/manual/`
* **Headers requeridos:** `Authorization`, `X-Company-ID`, `Content-Type: multipart/form-data`.
* **Serializer (`ManualDocumentSerializer`):** Para comprobantes sin XML (`cfdi_type = "M"`). Exige `pdf_file` obligatorio, `issue_date`, `direction`, `issuer_rfc`, `issuer_name`, `subtotal`, `iva_transferred` y `total`.

#### `POST /api/v1/documents/{id}/pdf/` `[E-06]`
* **Permisos:** `PARTNER`, `ACCOUNTANT`, `CLIENT` (periodo abierto). Adjunta o reemplaza el PDF de un documento existente (≤ 5 MB, firma `%PDF-`).

#### `GET /api/v1/documents/{id}/download/?file=xml|pdf` `[E-07]`
* **Headers requeridos:** `Authorization`, `X-Company-ID`. Devuelve el archivo como adjunto. Si el documento pertenece a otra empresa responde `404`.

#### `DELETE /api/v1/documents/{id}/`
* **Permisos:** únicamente `PARTNER`, solo si `is_accounted == False` y el periodo está abierto.

---

### 3.5 Pólizas Contables y Partida Doble (`apps/accounting`)

#### `GET /api/v1/entries/` & `GET /api/v1/entries/{id}/`
* **Headers requeridos:** `Authorization`, `X-Company-ID`.
* **Permisos:** `PARTNER`, `ACCOUNTANT`, `AUDITOR`.
* **Serializer (`AccountingEntryDetailSerializer`):**
  ```json
  {
    "id": 104,
    "fiscal_period": 18,
    "period_label": "2026-11",
    "entry_type": "EXPENSE",
    "folio": "EGR-2026-0042",
    "entry_date": "2026-11-15",
    "concept": "Pago de honorarios legales factura F-881",
    "status": "POSTED",
    "total_debit": "11600.00",
    "total_credit": "11600.00",
    "items": [
      {
        "id": 310,
        "line_number": 1,
        "account": 412,
        "account_code": "601.32.001",
        "account_name": "Honorarios a personas físicas",
        "document": 541,
        "document_uuid": "550e8400-e29b-41d4-a716-446655440000",
        "description": "Subtotal honorarios",
        "debit": "10000.00",
        "credit": "0.00"
      },
      {
        "id": 311,
        "line_number": 2,
        "account": 118,
        "account_code": "118.01.001",
        "account_name": "IVA acreditable pagado",
        "document": 541,
        "description": "IVA 16%",
        "debit": "1600.00",
        "credit": "0.00"
      },
      {
        "id": 312,
        "line_number": 3,
        "account": 102,
        "account_code": "102.01.001",
        "account_name": "BBVA Bancomer Cuenta 0192837465",
        "document": null,
        "description": "Transferencia SPEI",
        "debit": "0.00",
        "credit": "11600.00"
      }
    ]
  }
  ```

#### `POST /api/v1/entries/` & `PUT /api/v1/entries/{id}/`
* **Permisos:** `CanManageAccounting` + `IsFiscalPeriodOpen`.
* **Validaciones Estrictas en `AccountingEntryWriteSerializer`:**
  0. `fiscal_period` es **opcional** `[E-14]`: si se omite, se resuelve con `get_or_create_period(company, entry_date)`; si se envía, debe coincidir con `entry_date`. El `folio` lo genera el backend con `next_folio(company, entry_type, year)` `[E-15]`.
  1. `fiscal_period` debe pertenecer a `request.company` y tener `is_closed == False`.
  2. `entry_date` debe caer dentro del año y mes del `fiscal_period`.
  3. `items` debe contener al menos 2 renglones.
  4. Cada `account` debe pertenecer a `request.company` y tener `is_selectable == True`.
  5. Ningún renglón puede tener `debit > 0` y `credit > 0` al mismo tiempo, ni ambos en `0.00`.
  6. **Partida Doble:** `sum(item['debit']) == sum(item['credit'])` y mayor a `Decimal('0.00')`.
  7. Ejecuta `create_accounting_entry()` dentro de `transaction.atomic()` y actualiza `Document.is_accounted = True` en los documentos vinculados.
  8. `[E-15]` Las reglas 3 a 6 aplican también a pólizas en estado `DRAFT`: un borrador debe estar cuadrado.
* **Códigos de error:** `unbalanced_entry`, `period_closed`, `entry_date_out_of_period`, `non_selectable_account`, `invalid_line_amounts`.
* **Filtros `GET`:** `?fiscal_period=`, `?entry_type=`, `?status=`, `?date_from=`, `?date_to=`, `?search=` (folio o concepto).

#### `DELETE /api/v1/entries/{id}/`
* **Permisos:** Únicamente `IsPartnerRole` + `IsFiscalPeriodOpen`.
* **Efecto Secundario:** Crea obligatoriamente un registro en `AuditLog` (`action = ENTRY_DELETED`) guardando el snapshot JSON de la póliza eliminada en `previous_state` y libera `Document.is_accounted = False` si los documentos no están referenciados por otras pólizas.

---

### 3.6 Periodos Contables y Cierre (`apps/accounting`)

#### `GET /api/v1/periods/`
* **Headers requeridos:** `Authorization`, `X-Company-ID`.
* **Permisos:** `PARTNER`, `ACCOUNTANT`, `AUDITOR`.
* **Nota `[E-14]`:** no existe `POST /periods/`; los periodos se crean automáticamente con `get_or_create_period`.
* **Serializer (`FiscalPeriodSerializer`):** `id`, `year`, `month`, `is_closed`, `closed_at`, `closed_by_name`, `entries_count`, `unaccounted_documents_count`.

#### `POST /api/v1/periods/{id}/close/`
* **Permisos:** `IsPartnerRole`.
* **Validaciones Pre-Cierre:**
  * Verifica que `is_closed` sea actualmente `False`.
  * Verifica que no existan pólizas en estado `DRAFT` dentro del periodo (si existen, devuelve `400 Bad Request` con código `draft_entries_pending`).
* **Acción:** Establece `is_closed = True`, `closed_at = timezone.now()`, `closed_by = request.user` y registra evento `PERIOD_CLOSED` en `AuditLog`.

#### `POST /api/v1/periods/{id}/reopen/`
* **Permisos:** `IsPartnerRole`.
* **Request Payload (`PeriodReopenSerializer`):**
  ```json
  {
    "justification": "Reclasificación de factura complementaria de pago recibida fuera de fecha."
  }
  ```
* **Validaciones:** `justification` es obligatoria (mínimo 15 caracteres, validada en el serializer `[E-18]`).
* **Acción:** Establece `is_closed = False` y crea un registro inmutable en `AuditLog` (`action = PERIOD_REOPENED`) incluyendo la IP del cliente y la justificación.

---

### 3.7 Conciliación Bancaria (`apps/reconciliation`) `[E-21]`
Modelo `BankMovement` definido en `00_ERRATA.md` §2.1. Todos los endpoints exigen `Authorization` y `X-Company-ID`.

* `POST /api/v1/reconciliation/movements/import/` (`multipart/form-data`, CSV con columnas `date,reference,description,deposit,withdrawal`). Reporta filas inválidas por número de fila (incluida la fila con depósito y retiro simultáneos) y omite duplicados por `row_hash`. Respuesta con `summary` (`imported`, `skipped_duplicates`, `invalid`).
* `GET /api/v1/reconciliation/movements/?status=PENDING|RECONCILED`
* `GET /api/v1/reconciliation/movements/{id}/suggestions/` — candidatos de pólizas y documentos por monto exacto, fecha ±3 días y coincidencia de referencia o RFC, ordenados por puntaje.
* `POST /api/v1/reconciliation/movements/{id}/match/` — payload `{"entry_id": 104}` o `{"document_id": 541}`; deja el movimiento en `RECONCILED`.
* `POST /api/v1/reconciliation/movements/{id}/unmatch/` — regresa a `PENDING`.
* **Permisos:** `PARTNER` y `ACCOUNTANT` escriben; `AUDITOR` solo lectura; `CLIENT` recibe `403`. Las escrituras se rechazan con `period_closed` si el periodo del movimiento está cerrado.

### 3.8 Reportes Ejecutivos (`apps/reconciliation`) `[E-21]`
* `GET /api/v1/reports/trial-balance/?period=<id>` — por cuenta: `sat_group_code`, `code`, `name`, `opening_balance`, `total_debit`, `total_credit`, `closing_balance`, más fila `totals` con `difference`. Saldo inicial = acumulado de periodos previos del mismo ejercicio; cargos/abonos = pólizas `POSTED` del periodo; saldo final según `nature`. Permisos: `PARTNER`, `ACCOUNTANT`, `AUDITOR`.
* `GET /api/v1/reports/executive-summary/?period=<id>` — `iva_transferred`, `iva_creditable`, `iva_retained`, `isr_retained`, `income_total`, `expense_total`. `CLIENT` recibe solo `income_total`, `expense_total` y totales de IVA. Cálculo preliminar, sin distinguir PUE de PPD.
* Agregaciones con el ORM; prohibido `.raw()`.

### 3.9 Bitácora de Auditoría (`apps/core`) `[E-21]`
* `GET /api/v1/audit-logs/` — solo lectura; `PARTNER` y `AUDITOR`. Filtros `?action=`, `?date_from=`, `?date_to=`. Paginado `[E-19]`.

---

## 4. Estandarización Global de Respuestas y Manejo de Errores

### 4.1 Custom JSON Renderer (`apps/core/renderers.py`)
Configurado como `DEFAULT_RENDERER_CLASSES` en `settings/base.py`. Intercepta toda respuesta exitosa (`2xx`) antes de serializarla al cliente y la envuelve en el contrato oficial aprobado en `01_CORE_SPECS.md`:

```json
{
  "success": true,
  "message": "Operación realizada correctamente.",
  "data": { ... },
  "errors": null
}
```
* **Paginación `[E-19]`:** las respuestas paginadas se envuelven como `data = {"count": 0, "next": null, "previous": null, "results": []}`.
* **Nota de Implementación:** Las vistas pueden definir un atributo o clave temporal `response_message` para personalizar `"message"`, o el renderer asignará un mensaje descriptivo por defecto según el método HTTP (`GET`: `"Consulta exitosa."`, `POST`: `"Registro creado correctamente."`, `PATCH/PUT`: `"Registro actualizado correctamente."`, `DELETE`: `"Registro eliminado correctamente."`).

### 4.2 Custom Exception Handler (`apps/core/exceptions.py`)
Configurado como `EXCEPTION_HANDLER` global en DRF. Captura excepciones de DRF (`APIException`, `ValidationError`, `AuthenticationFailed`, `PermissionDenied`, `NotFound`), errores de Django ORM (`DjangoValidationError`, `ObjectDoesNotExist`) y errores no controlados (`500`), transformándolos al formato unificado con `success: false` `[E-02]`: `errors` es **siempre un arreglo** `[{field, code, message}]`; se añade `error_id` al nivel superior (UUID solo en errores `500`, el stack trace completo se registra en logs internos asociado a ese ID; `null` en los demás). No se utiliza `422`.

#### Catálogo de Códigos de Error Estandarizados:

| HTTP Status | Código Interno (`code`) | Causa / Escenario | Ejemplo de Respuesta JSON |
| :--- | :--- | :--- | :--- |
| **`400 Bad Request`** | `validation_error` | Error en campos de serializer o reglas de negocio (ej. partida doble descuadrada). | `{"success": false, "message": "Error de validación en los datos enviados.", "error_id": null, "data": null, "errors": [{"field": "items", "code": "unbalanced_entry", "message": "Póliza descuadrada: Cargos ($100.00) != Abonos ($90.00)."}]}` |
| **`400 Bad Request`** | `missing_or_invalid_tenant_header` | Falta header `X-Company-ID` o no es numérico en una ruta operativa. | `{"success": false, "message": "Contexto de empresa inválido.", "error_id": null, "data": null, "errors": [{"field": "X-Company-ID", "code": "missing_or_invalid_tenant_header", "message": "Debe proporcionar un encabezado X-Company-ID válido."}]}` |
| **`400 Bad Request`** | `period_closed` | Intento de crear/editar/borrar pólizas o documentos en un mes cerrado. | `{"success": false, "message": "Periodo contable cerrado.", "error_id": null, "data": null, "errors": [{"field": "fiscal_period", "code": "period_closed", "message": "El periodo 2026-10 está cerrado."}]}` |
| **`401 Unauthorized`** | `authentication_failed` / `token_not_valid` | Token JWT ausente, malformado o expirado. | `{"success": false, "message": "Sesión no válida o expirada.", "error_id": null, "data": null, "errors": [{"field": "authorization", "code": "token_not_valid", "message": "El token de acceso ha expirado."}]}` |
| **`403 Forbidden`** | `tenant_access_denied` | El usuario no tiene membresía activa en el `X-Company-ID` solicitado. | `{"success": false, "message": "Acceso denegado a la empresa.", "error_id": null, "data": null, "errors": [{"field": "X-Company-ID", "code": "tenant_access_denied", "message": "No tiene permisos para operar sobre esta empresa."}]}` |
| **`403 Forbidden`** | `role_permission_denied` | El rol del usuario (`ACCOUNTANT`, `AUDITOR`, `CLIENT`) no permite la acción. | `{"success": false, "message": "Permisos insuficientes.", "error_id": null, "data": null, "errors": [{"field": null, "code": "role_permission_denied", "message": "Su rol actual no permite cerrar periodos fiscales."}]}` |
| **`404 Not Found`** | `not_found` | El recurso no existe o pertenece a otra empresa (evita enumeración de IDs). | `{"success": false, "message": "Recurso no encontrado.", "error_id": null, "data": null, "errors": [{"field": null, "code": "not_found", "message": "El registro solicitado no existe en la empresa activa."}]}` |
| **`429 Too Many Requests`** | `throttled` | Se excedió el límite de intentos de login (5/min). | `{"success": false, "message": "Demasiados intentos.", "error_id": null, "data": null, "errors": [{"field": null, "code": "throttled", "message": "Intente de nuevo en un minuto."}]}` |
| **`500 Internal Server Error`** | `internal_server_error` | Excepción no controlada del servidor (oculta stacktrace en producción). | `{"success": false, "message": "Error interno del servidor.", "error_id": "a1b2c3d4-e5f6-7890-abcd-ef0123456789", "data": null, "errors": [{"field": null, "code": "internal_server_error", "message": "Ocurrió un error inesperado. Contacte a soporte técnico."}]}` |

---

## 5. Checklist de Implementación para el Backend

1. **`apps/core/renderers.py` & `exceptions.py`:** Registrar `StandardJSONRenderer` y `custom_exception_handler` en `REST_FRAMEWORK` dentro de `config/settings/base.py`.
2. **`apps/tenants/mixins.py`:** Implementar `TenantContextMixin` (validación de `X-Company-ID`, `400` vs `403`, en `initial()`) y `TenantQuerySetMixin` `[E-03]`.
3. **`apps/authentication/permissions.py`:** Implementar `IsTenantMember`, `IsPartnerRole`, `CanManageAccounting`, `IsReadOnlyAuditor`, `IsClientPortalAllowed` e `IsFiscalPeriodOpen`.
4. **`apps/documents/services.py`:** Implementar parser XML con `defusedxml.ElementTree` `[E-05]` (namespaces CFDI 4.0 y 3.3) soportando extracción de Timbre Fiscal Digital (TFD 1.1) e impuestos trasladados/retenidos para procesamiento parcial.
5. **`apps/accounting/services.py`:** Conectar los serializers de pólizas y cierre/reapertura de periodos con `transaction.atomic()` y `AuditLog`, e implementar `next_folio` `[E-15]` y `get_or_create_period` `[E-14]`.
6. **`apps/reconciliation/`:** `BankMovement`, importación CSV, sugerencias, `match`/`unmatch` y reportes `[E-21]`.
7. **Settings `[E-04]` `[E-09]` `[E-11]`:** `DATA_UPLOAD_MAX_NUMBER_FILES = 50`, `FILE_UPLOAD_MAX_MEMORY_SIZE`, `TIME_ZONE='America/Mexico_City'`, `USE_TZ=True`, throttling de login, `drf-spectacular`.
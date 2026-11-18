# `00_ERRATA.md` — Errata y Decisiones de Arquitectura

**Regla de precedencia:** este documento **prevalece** sobre `01`–`06` en caso de cualquier conflicto. Los documentos 01–06 ya fueron actualizados para reflejar estas decisiones; el ID de cada errata aparece entre corchetes (ej. `[E-02]`) en los puntos modificados.

---

## 1. Tabla de decisiones

| ID | Severidad | Hallazgo | Decisión |
|---|---|---|---|
| E-01 | Media | Nombres distintos para lo mismo: `PolicyEntry` (01) vs `AccountingEntryItem` (02); `Account` (01) vs `AccountCatalog` (02); `/accounting/journal-entries/` (01) vs `/entries/` (03); `useCompanyStore` (05) vs `tenantStore` (01/03). | Se usan `AccountingEntry`, `AccountingEntryItem`, `AccountCatalog`, `/api/v1/entries/`, `useAuthStore` y `useTenantStore` (con `companies`, `currentCompany`, `setCurrentCompany`). |
| E-02 | **Alta** | Formato de error: 01 y 03 usan `errors` como **arreglo** `[{field, code, message}]`; 06 lo mostraba como **objeto** y añadía `error_id`. | `errors` es siempre un arreglo. Se añade `error_id` al nivel superior (UUID en errores 500, `null` en el resto). No se usa 422; la validación es 400. |
| E-03 | **Alta** | 01 pedía un *middleware* de Django que lea el usuario del JWT, pero la autenticación JWT ocurre dentro de DRF, después de los middlewares. | La validación de tenant se implementa como `TenantContextMixin` (en `initial()` de la vista DRF) y `TenantQuerySetMixin`, no como middleware de Django. |
| E-04 | Media | Tamaño máximo: 5 MB por archivo (06) vs 2 MB (03). | XML ≤ 2 MB, PDF ≤ 5 MB, máximo 50 archivos por petición. Se configuran `DATA_UPLOAD_MAX_NUMBER_FILES`, `FILE_UPLOAD_MAX_MEMORY_SIZE` y `client_max_body_size` en Nginx. |
| E-05 | Media | 06 pedía `lxml` contra XXE; 01 y 03 piden `xml.etree.ElementTree`, vulnerable a expansión de entidades. | Se usa `defusedxml.ElementTree` (misma API). Se soportan los namespaces CFDI 4.0 y 3.3. |
| E-06 | Media | 04 y 06 aceptan XML y PDF en la carga masiva; el endpoint de 03 solo recibía `.xml`. | `bulk-upload` acepta `.xml` y `.pdf`. Un PDF se empareja con el XML de mismo nombre base dentro del lote; sin pareja se reporta `orphan_pdf`. Además `POST /documents/{id}/pdf/` lo adjunta después. |
| E-07 | Media | Rutas de almacenamiento: 02 usaba el nombre original (riesgo de *path traversal*); 06 usaba `companies/{id}/xmls/` también para PDF. | Ruta única: `companies/{company_id}/documents/{yyyy}/{mm}/{uuid4}.{ext}`. El nombre original se guarda en `original_filename`. `xml_url`/`pdf_url` apuntan a `/api/v1/documents/{id}/download/?file=xml\|pdf` (autenticado); el frontend descarga como *blob*. |
| E-08 | Media | 06 y 05 se contradecían en 401/403. | **401:** un intento de refresh y, si falla, logout. **403:** si `code = tenant_access_denied`, se limpia la empresa y se redirige a `/select-company`; si es `role_permission_denied`, solo Toast. **500:** mensaje + `error_id`. Rutas del frontend en inglés (`/select-company`). |
| E-09 | Media | `SECURE_BROWSER_XSS_FILTER` fue eliminado en Django 4.0; `CORS_ALLOW_CREDENTIALS=True` no es necesario con Bearer; `X-Company-ID` no está en los headers CORS permitidos por defecto; no hay *throttling* de login. | Se elimina el filtro XSS; se añaden `django-csp`, HSTS, `SECURE_REFERRER_POLICY` y cookies seguras en producción. `CORS_ALLOW_CREDENTIALS=False`. `x-company-id` se agrega a `CORS_ALLOW_HEADERS`. Login limitado a 5/min. JWT en `localStorage` aceptado como riesgo del MVP, mitigado con CSP. |
| E-10 | **Alta** | 03 hace login con `email` pero nadie define el modelo de usuario. | `authentication.User` (`AbstractUser`, `email` único, `USERNAME_FIELD='email'`) se crea antes de cualquier migración. |
| E-11 | Media | No se define zona horaria. | `TIME_ZONE='America/Mexico_City'`, `USE_TZ=True`. El periodo se deriva de la fecha local del CFDI. |
| E-12 | Media | 01 daba al Auxiliar CRUD completo; 03 le niega el `DELETE`. Catálogo: "Lectura/Asignación" vs "solo PATCH". | Prevalece 03. El Auxiliar solo puede hacer `PATCH` del campo `name` en cuentas. |
| E-13 | Media | "Cliente ve solo sus propios comprobantes" (01, 06) vs "toda su empresa" (03). | "Propios" = los de **su empresa** (tenant). |
| E-14 | Media | Falta endpoint para crear periodos. | Los periodos se resuelven con `get_or_create` a partir de la fecha local. `fiscal_period` es opcional en el payload de pólizas; si se envía, debe coincidir con la fecha. |
| E-15 | Media | Falta el folio de pólizas; 01 dice que no se guardan descuadradas, pero existe `DRAFT`. | Servicio `next_folio(company, entry_type, year)` con `select_for_update`; prefijos `ING/EGR/DIA`, formato `ING-2026-0014`. Un `DRAFT` **también** debe estar cuadrado; solo se distingue en que no está contabilizado y en que bloquea el cierre. |
| E-16 | Menor | `Document` no guardaba `original_filename` ni estatus; índice redundante. | Se añaden `original_filename` y `sat_status` (`VALID`, `CANCELLED`, `UNVERIFIED`; el MVP solo valida estructura). Se elimina `idx_doc_company_uuid`. UUID normalizado a minúsculas. |
| E-17 | **Alta (demo)** | Los RFC del *seed* no pasan el regex; `fiscal_year_start` faltaba en el código. | RFC demo: `CNO200101AB9` y `SDA210515XY1`. Se agrega `fiscal_year_start`. Razones sociales sin régimen societario. |
| E-18 | Menor | `AuditLog.delete()` solo bloqueaba el borrado por instancia. | Se bloquea `save()` si ya existe `pk` y se usa un `QuerySet` propio que prohíbe `delete()` y `update()`. `justification` pasa a `blank=True`; la exigencia de 15 caracteres vive en el serializer de reapertura. |
| E-19 | Menor | No se define la paginación en el envoltorio. | `data = {count, next, previous, results}`. |
| E-20 | Menor | `shadow-xs` no existe en Tailwind 3.4; `text-slate-500` sobre `bg-slate-100` < 4.5:1; "Timbrar" y "descarga masiva SAT" fuera de alcance. | `shadow-sm`; `<th>` usa `text-slate-600`; se elimina "Timbrar"; notificaciones SAT = placeholder sin lógica. |
| E-21 | **Alta** | Conciliación, Reportes y `/audit-logs/` no tenían modelo ni endpoints. | Definidos en la sección 2 de este documento y reflejados en 03. |
| E-22 | Media | `POST /companies/` exigía ser PARTNER, así que el primer usuario nunca podría crear empresas; "invitación" sin definir. | PARTNER o superusuario pueden crear empresas. `members` acepta solo usuarios existentes; los usuarios se crean con `createsuperuser`, el *seed* o el admin. Sin auto-registro. |
| E-23 | Media | Sin criterio para montos en el frontend. | La API envía montos como string. Frontend: `decimal.js` (`useCurrency`), nunca `parseFloat` para sumar. |
| E-24 | Menor | Carga masiva parcial sin aclarar transacciones. | Un `transaction.atomic()` por archivo (savepoint); sin `ATOMIC_REQUESTS`. |
| E-25 | Menor | El *seed* debe ser idempotente y respetar el bloqueo de periodos. | Orden: crear periodos → cargar documentos y pólizas con los **mismos servicios** que usa la API → cerrar al final el mes anterior. Se niega a correr con `DEBUG=False` sin `--force`; contraseñas desde `DEMO_PASSWORD`. |

---

## 2. E-21: Especificación añadida (Conciliación, Reportes y Bitácora)

### 2.1 Modelo `BankMovement` (`TenantAwareModel`, app `reconciliation`)
| Campo | Tipo | Notas |
|---|---|---|
| `date` | `DateField` | Fecha del movimiento. |
| `reference` | `CharField(100)` | Referencia bancaria. |
| `description` | `CharField(255)` | Concepto. |
| `deposit` | `DecimalField(14,2)` | ≥ 0. |
| `withdrawal` | `DecimalField(14,2)` | ≥ 0. Mutuamente excluyente con `deposit`; uno debe ser > 0. |
| `status` | `CharField` | `PENDING` (default) / `RECONCILED`. |
| `entry` | FK `AccountingEntry` nula | Póliza vinculada. |
| `document` | FK `Document` nula | CFDI vinculado. |
| `import_batch` | `UUIDField` | Lote de importación. |
| `row_hash` | `CharField(64)` | SHA-256 de la fila; **único por empresa** (evita duplicados al reimportar). |

### 2.2 Endpoints de conciliación (exigen `X-Company-ID`)
* `POST /api/v1/reconciliation/movements/import/` — CSV con columnas `date,reference,description,deposit,withdrawal`. Reporta filas inválidas por número de fila y omite duplicados.
* `GET /api/v1/reconciliation/movements/?status=`
* `GET /api/v1/reconciliation/movements/{id}/suggestions/` — sugiere por monto exacto, fecha ±3 días y referencia o RFC; ordenado por puntaje.
* `POST /api/v1/reconciliation/movements/{id}/match/` — `{entry_id | document_id}`.
* `POST /api/v1/reconciliation/movements/{id}/unmatch/`
* **Permisos:** PARTNER y ACCOUNTANT escriben; AUDITOR solo lee; CLIENT recibe 403. Escrituras bloqueadas si el periodo del movimiento está cerrado.

### 2.3 Reportes
* `GET /api/v1/reports/trial-balance/?period=<id>` — saldo inicial = acumulado de periodos previos del mismo ejercicio; cargos y abonos = pólizas `POSTED` del periodo; saldo final según `nature`; fila de totales con diferencia.
* `GET /api/v1/reports/executive-summary/?period=<id>` — IVA trasladado, IVA acreditable, retenciones de IVA/ISR, ingresos vs egresos. CLIENT recibe un subconjunto (ingresos, egresos y totales de IVA). Es un cálculo preliminar, sin distinguir PUE de PPD.
* Los cálculos usan agregaciones del ORM; nunca `.raw()`.

### 2.4 Bitácora
* `GET /api/v1/audit-logs/` — PARTNER y AUDITOR; paginado; filtros `action` y `date`.

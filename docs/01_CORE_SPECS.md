# Especificación Maestra de Negocio y Estructura (`01_CORE_SPECS.md`)

Este documento constituye la fuente de verdad definitiva e inamovible para el diseño, desarrollo e implementación del sistema plantilla multi-tenant para despachos contables en México. Está optimizado para ser interpretado y ejecutado por agentes autónomos de desarrollo (OpenCode) y sirve como contexto base para las capas de Base de Datos, Backend y Frontend.

> **Precedencia:** `docs/00_ERRATA.md` prevalece sobre este documento. Los puntos ajustados por la errata se marcan con `[E-xx]`.

---

## 1. Arquitectura Multi-Cliente (Multi-Tenant) y Regímenes Fiscales

### 1.1 Modelo de Aislamiento Lógico (Shared Database / Tenant ID)
* **Enfoque de Base de Datos:** PostgreSQL con base de datos compartida y aislamiento lógico estricto a nivel de fila.
* **Llave de Aislamiento:** Todas las tablas transaccionales y de catálogo operativo (documentos, pólizas, cuentas contables por empresa, periodos fiscales, movimientos bancarios) deben poseer una llave foránea obligatoria `company_id`.
* **Mecanismo de Interceptación (`TenantContextMixin` + `TenantQuerySetMixin`) `[E-03]`:** La autenticación JWT se resuelve dentro de DRF, después de los middlewares de Django, por lo que la validación de tenant **no** se implementa como middleware de Django. Un `TenantContextMixin` ejecutado en `initial()` de la vista DRF lee el header HTTP `X-Company-ID` (el token JWT no fija una empresa), valida que el usuario autenticado tenga una membresía activa sobre dicha empresa e inyecta `request.company` y `request.membership`. Un `TenantQuerySetMixin` filtra automáticamente todos los `QuerySets` por `company` para garantizar cero fugas de información entre clientes del despacho.
* **Modelo de Usuario `[E-10]`:** El proyecto define `authentication.User` (`AbstractUser`, `email` único como `USERNAME_FIELD`) y lo declara en `AUTH_USER_MODEL` antes de la primera migración.
* **Zona Horaria `[E-11]`:** `TIME_ZONE = 'America/Mexico_City'` y `USE_TZ = True`. El periodo fiscal de un comprobante se deriva de su fecha **local**.

### 1.2 Regímenes Fiscales Base Soportados
La plantilla inicial soportará las reglas de validación, clasificación y acumulación para los siguientes tres regímenes del SAT en México:
1. **Persona Física con Actividad Empresarial y Profesional (PFAEP):** Control de ingresos acumulables (flujo de efectivo), deducciones autorizadas por tipo de gasto y determinación mensual de ISR e IVA.
2. **Régimen Simplificado de Confianza (RESICO) - Personas Físicas:** Cálculo con tasas fijas reducidas de ISR sobre ingresos efectivamente cobrados (sin deducciones estructurales para ISR, manteniendo acreditamiento de IVA) y validación preventiva del límite anual de ingresos ($3,500,000.00 MXN).
3. **Persona Moral - Régimen General:** Acumulación de ingresos con base en facturación/devengado, control estricto de deducciones autorizadas, aplicación de coeficiente de utilidad para pagos provisionales de ISR y conciliación contable-fiscal.

---

## 2. Matriz de Roles y Permisos (RBAC)

El sistema define 4 roles jerárquicos con capacidades estrictamente delimitadas dentro del contexto de cada empresa asignada:

| Módulo / Acción | Socio / Admin | Auxiliar Contable | Auditor | Cliente (Portal Externo) |
| :--- | :---: | :---: | :---: | :---: |
| **Gestión de Empresas (Tenants)** | CRUD Completo | Solo Lectura | Solo Lectura | Sin Acceso |
| **Gestión de Usuarios y Roles** | CRUD Completo | Sin Acceso | Sin Acceso | Sin Acceso |
| **Catálogo de Cuentas (SAT)** | CRUD / Personalización | Lectura / Edición solo del nombre (`PATCH name`) `[E-12]` | Solo Lectura | Sin Acceso |
| **Carga de XMLs (CFDI 4.0) y PDFs** | CRUD Completo (borrado solo si no está contabilizado) | Carga y edición, **sin borrado** `[E-12]` | Solo Lectura | Solo Carga y Lectura (de su empresa; sin borrado) `[E-13]` |
| **Creación / Edición de Pólizas** | CRUD Completo (borrado con `AuditLog`) | Crear / Editar, **sin borrado** (Solo Periodos Abiertos) `[E-12]` | Solo Lectura | Sin Acceso |
| **Cierre de Mes Contable** | Permitido | Sin Acceso | Sin Acceso | Sin Acceso |
| **Reapertura Extraordinaria de Mes** | Permitido (Con Log Obligatorio) | Sin Acceso | Sin Acceso | Sin Acceso |
| **Conciliación Bancaria** | Ejecución y Aprobación | Ejecución Operativa | Solo Lectura | Sin Acceso |
| **Reportes Ejecutivos y Fiscales** | Acceso Total | Acceso Operativo | Acceso Total | Consulta Básica (Resumen) |
| **Bitácora de Auditoría (AuditLog)** | Solo Lectura | Sin Acceso | Solo Lectura | Sin Acceso |

---

## 3. Funciones Core del Sistema Plantilla (MVP Sólido sin IA)

### 3.1 Módulo de Gestión de Clientes, Catálogo SAT y Periodos Contables
* **Empresas (`Company`):** Registro de contribuyentes con RFC (validado contra formato oficial del SAT), razón social, régimen fiscal y moneda base (`MXN`).
* **Alta de Empresas `[E-22]`:** Pueden crear empresas un usuario con rol `PARTNER` en al menos un tenant o un superusuario. Al crearla, el creador queda como `PARTNER`. No existe auto-registro: los usuarios se crean con `createsuperuser`, el comando `seed_accounting_data` o el admin de Django, y la gestión de miembros solo agrega usuarios existentes.
* **Catálogo de Cuentas Homologado (`AccountCatalog`) `[E-01]`:** El sistema incluirá un Catálogo de Cuentas Maestro preconfigurado con los códigos agrupadores oficiales del SAT para contabilidad electrónica. Al dar de alta una nueva empresa, el sistema clonará automáticamente este catálogo maestro hacia la nueva empresa para permitir operación inmediata.
* **Periodos Contables (`FiscalPeriod`):** Gestión mensual (`year`, `month`) por empresa con bandera booleana `is_closed` (por defecto `False`).
  * **Regla de Bloqueo Estricto:** Cuando `is_closed == True`, el sistema bloqueará a nivel de lógica de negocio y API cualquier intento de crear, editar o eliminar pólizas, facturas o movimientos bancarios asociados a ese periodo.
  * **Reapertura Extraordinaria:** Únicamente el rol `Socio/Admin` puede cambiar `is_closed` de `True` a `False`. Esta acción exige ingresar una justificación textual (mínimo 15 caracteres, validada en el serializer) y crea un registro inmutable en la tabla `AuditLog`.
  * **Creación de Periodos `[E-14]`:** No existe endpoint para crear periodos. Se resuelven con `get_or_create` a partir de la fecha local del documento o de la póliza.

### 3.2 Módulo de Recepción y Clasificación de Documentos (XML / PDF)
* **Carga Masiva de XMLs (CFDI 4.0) y PDFs `[E-06]`:** Endpoint optimizado para recibir múltiples archivos `.xml` y `.pdf` simultáneamente (emitidos y recibidos). Cada PDF se empareja con el XML de mismo nombre base dentro del lote; sin pareja se reporta `orphan_pdf`. Límites `[E-04]`: XML ≤ 2 MB, PDF ≤ 5 MB, máximo 50 archivos por petición. El procesamiento es parcial, con una transacción por archivo `[E-24]`.
* **Extracción Segura `[E-05]`:** Parsing rápido en backend utilizando `defusedxml.ElementTree` (misma API que `xml.etree.ElementTree`, pero protegido contra XXE y expansión de entidades), con soporte de namespaces CFDI 4.0 y 3.3, para extraer automáticamente: UUID (Timbre Fiscal Digital), versión de CFDI, tipo de comprobante (Ingreso, Egreso, Pago, Nómina), fecha de emisión, RFC y nombre de emisor/receptor, método y forma de pago, subtotal, descuentos, impuestos trasladados (IVA, IEPS), impuestos retenidos y total.
* **Prevención de Duplicados:** Validación única por `uuid` dentro de la misma `company_id`.
* **Captura Manual de Respaldo:** Formulario para registrar comprobantes sin XML (ej. gastos menores, notas de remisión, comprobantes extranjeros), requiriendo adjuntar archivo PDF o imagen de respaldo.

### 3.3 Módulo de Pólizas Contables (Partida Doble)
* **Tipos de Póliza:** `INCOME` (Ingresos), `EXPENSE` (Egresos) y `JOURNAL` (Diario).
* **Regla Matemática Inquebrantable (Partida Doble):** Toda póliza consta de un encabezado y múltiples partidas/movimientos (`AccountingEntryItem`) `[E-01]`. El sistema validará a nivel de serializador y transacción de base de datos que:
  $$\sum \text{Cargos (Debit)} = \sum \text{Abonos (Credit)}$$
  *(Nota: No se permite guardar ni contabilizar pólizas descuadradas o con suma igual a cero. Esto aplica también al estado `DRAFT`: un borrador también debe estar cuadrado y solo se distingue por no estar contabilizado y por bloquear el cierre del periodo `[E-15]`).*
* **Folios `[E-15]`:** El folio se genera con `next_folio(company, entry_type, year)` usando `select_for_update`. Prefijos `ING` / `EGR` / `DIA`; formato `ING-2026-0014`.
* **Trazabilidad Documental:** Posibilidad de vincular cada póliza o partida contable con uno o varios UUIDs de documentos CFDI previamente cargados, prellenando cuentas e importes sugeridos según el catálogo de la empresa.

### 3.4 Módulo de Conciliación Básica
* **Importación de Movimientos Bancarios:** Carga estructurada (CSV/Excel estandarizado) o captura de movimientos del estado de cuenta bancario de la empresa (fecha, referencia, concepto, cargo/abono).
* **Cruce Operativo:** Interfaz y lógica de emparejamiento (matching) que permite vincular movimientos bancarios contra pólizas contables y/o facturas CFDI basándose en coincidencia de fecha, monto exacto y RFC/referencia, marcando los registros como `conciliado` (`RECONCILED`) o `pendiente` (`PENDING`). Modelo `BankMovement` y endpoints definidos en `00_ERRATA.md` §2 `[E-21]`.

### 3.5 Módulo de Reportes Ejecutivos
* **Balanza de Comprobación:** Cálculo dinámico por periodo fiscal mostrando código agrupador SAT, código de cuenta interna, nombre de cuenta, saldo inicial, total de cargos, total de abonos y saldo final.
* **Resumen Fiscal del Periodo:** Tablero ejecutivo con el cálculo preliminar de IVA trasladado (cobrado), IVA acreditable (pagado), retenciones de IVA/ISR y resumen de ingresos vs. egresos del mes. Endpoints y reglas de cálculo definidos en `00_ERRATA.md` §2 `[E-21]`.

---

## 4. Estructura Oficial de Carpetas y Convenciones (Monorepo)

### 4.1 Árbol de Directorios Exacto
```text
/
├── backend/                  # Django + Django REST Framework (Python 3.11+)
│   ├── config/               # Configuración central del proyecto Django
│   │   ├── settings/         # Configuraciones divididas (base.py, local.py, production.py)
│   │   ├── urls.py           # Enrutamiento raíz de la API (/api/v1/)
│   │   ├── wsgi.py
│   │   └── asgi.py
│   ├── apps/                 # Aplicaciones modulares de dominio
│   │   ├── core/             # Clases base, excepciones personalizadas, renderer JSON, AuditLog
│   │   ├── authentication/   # User personalizado, Profile, CompanyMembership, JWT, permisos RBAC
│   │   ├── tenants/          # Empresas (Company), regímenes y mixins multi-tenant (TenantContextMixin)
│   │   ├── accounting/       # Catálogo SAT, FiscalPeriod, Pólizas y Partida Doble
│   │   ├── documents/        # Parser XML CFDI 4.0, almacenamiento de archivos y validación
│   │   └── reconciliation/   # Movimientos bancarios, conciliación y reportes ejecutivos
│   ├── fixtures/             # Datos iniciales (Catálogo maestro de cuentas SAT, regímenes)
│   ├── requirements/         # Dependencias (base.txt, local.txt, production.txt)
│   ├── Dockerfile
│   └── manage.py
├── frontend/                 # Vue 3 + Composition API + Pinia + Tailwind CSS
│   ├── public/
│   ├── src/
│   │   ├── api/              # Clientes HTTP (Axios), interceptores de token y X-Company-ID
│   │   ├── assets/           # Estilos base de Tailwind e imágenes
│   │   ├── components/       # Componentes UI reutilizables (tablas, modales, badges)
│   │   ├── composables/      # Lógica reactiva compartida (useToast, useCurrency, useRBAC)
│   │   ├── layouts/          # Plantillas de estructura (DashboardLayout, AuthLayout)
│   │   ├── router/           # Definición de rutas y Navigation Guards por rol y empresa
│   │   ├── stores/           # Stores de Pinia (useAuthStore, useTenantStore, accountingStore)
│   │   ├── views/            # Vistas principales organizadas por módulo de negocio
│   │   ├── App.vue
│   │   └── main.js
│   ├── Dockerfile
│   ├── index.html
│   ├── package.json
│   ├── postcss.config.js
│   └── tailwind.config.js
├── docs/                     # Documentación de arquitectura y especificaciones
│   ├── 00_ERRATA.md          # Errata y decisiones (PREVALECE sobre 01–06)
│   ├── 01_CORE_SPECS.md      # Este documento
│   └── 02..06_*.md           # Base de datos, API, UI, frontend y seguridad
├── .env.example              # Plantilla de variables de entorno
├── docker-compose.yml        # Orquestación de servicios (db, backend, frontend)
└── README.md
```

### 4.2 Convenciones de Nomenclatura Globales
* **Código Fuente y Arquitectura (Inglés Estricto):** Todos los nombres de archivos, clases, modelos de Django, campos de base de datos, variables, funciones, componentes Vue, stores de Pinia y rutas de endpoints REST deben escribirse estrictamente en **Inglés** siguiendo `snake_case` en Python/SQL y `camelCase` / `PascalCase` en JavaScript/Vue (ej. `FiscalPeriod`, `company_id`, `parse_cfdi_xml`, `/api/v1/entries/`) `[E-01]`. Las rutas del frontend también van en inglés (ej. `/select-company`).
* **Interfaz de Usuario y Mensajes al Cliente (Español Estricto):** Todos los textos visibles en el frontend (menús, etiquetas de formularios, encabezados de tablas, tooltips, alertas) y todos los mensajes de respuesta o error devueltos por la API al usuario final deben redactarse en **Español** claro, profesional y adaptado a la terminología contable y fiscal de México.

### 4.3 Formato Estándar de Respuesta JSON (API REST)
Todo endpoint de Django REST Framework debe utilizar un `CustomRenderer` y manejador de excepciones global para garantizar que **100% de las respuestas** cumplan exactamente con la siguiente estructura:

* **Respuesta Exitosa (`200 OK`, `201 Created`):**
```json
{
  "success": true,
  "message": "Póliza contable registrada correctamente.",
  "data": {
    "id": 104,
    "folio": "ING-2026-0014",
    "total_debit": "11600.00",
    "total_credit": "11600.00"
  },
  "errors": null
}
```

* **Respuesta Paginada `[E-19]`:** `data = { "count": 0, "next": null, "previous": null, "results": [] }`.

* **Respuesta de Error (`400 Bad Request`, `401 Unauthorized`, `403 Forbidden`, `404 Not Found`, `429 Too Many Requests`, `500 Internal Server Error`) `[E-02]`:** `errors` es **siempre un arreglo**. `error_id` es un UUID en los errores `500` (correlacionado con el stack trace en logs internos) y `null` en los demás. No se utiliza `422`: los errores de validación son `400`.
```json
{
  "success": false,
  "message": "No se pudo procesar la operación debido a errores de validación.",
  "error_id": null,
  "data": null,
  "errors": [
    {
      "field": "fiscal_period",
      "code": "period_closed",
      "message": "El periodo fiscal 2026-10 se encuentra cerrado. Solicite autorización a un Socio para reabrirlo."
    }
  ]
}
```
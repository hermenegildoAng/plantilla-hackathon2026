# `05_FRONTEND_ARCH_SPEC.md` — Especificación de Arquitectura Frontend, Rutas, Stores y Cliente HTTP

Este documento define la arquitectura técnica y el diseño conceptual para la capa de cliente en **Vue 3 (Composition API), Pinia, Vue Router y Tailwind CSS**, integrándose con el backend Django REST Framework bajo los estándares del sistema de diseño ERP Compacto (`04_FRONTEND_UI_SYSTEM.md`) y las especificaciones multi-tenant (`01_CORE_SPECS.md`).

> **Precedencia:** `docs/00_ERRATA.md` prevalece sobre este documento. Los puntos ajustados por la errata se marcan con `[E-xx]`.

---

## 1. Configuración del Cliente HTTP (Axios / Interceptors)

El cliente HTTP centraliza la comunicación con la API REST (`/api/v1/`) mediante una instancia configurada para inyectar automáticamente los mecanismos de autenticación y aislamiento multi-tenant.

### 1.1 Reglas de Interceptación de Peticiones (Request Interceptor)
* **Inyección de Token JWT:** Cada petición adjunta automáticamente el token de acceso vigente en la cabecera de autorización (`Authorization: Bearer <access_token>`), obtenido desde el store global de autenticación.
* **Inyección de Contexto Tenant (`X-Company-ID`):** Para todas las rutas operativas, el interceptor extrae el identificador de la empresa activa del store de tenants e inyecta dinámicamente la cabecera obligatoria `X-Company-ID: <company_id>` requerida por el backend.

### 1.2 Reglas de Interceptación de Respuestas y Errores (Response Interceptor)
* **Normalización de Respuestas:** Desempaqueta automáticamente la estructura estándar de la API (`{ success, message, error_id, data, errors }`) para entregar los datos directamente a los composables o componentes. `errors` es siempre un arreglo `[{field, code, message}]` `[E-02]`. Las respuestas paginadas llegan como `{count, next, previous, results}` `[E-19]`. Los montos llegan como *string* y se operan con `decimal.js` `[E-23]`.
* **Manejo de Sesión Expirada (`401 Unauthorized`) `[E-08]`:** Si una petición falla por expiración del token de acceso, el interceptor ejecuta **un solo intento** de renovación transparente (*token refresh*), encolando las peticiones concurrentes mientras refresca. Si el refresco falla, invalida el token en el store, limpia el almacenamiento local y redirige a `/login`.
* **Manejo de `403 Forbidden` `[E-08]`:** Se decide por el `code` de error. Si es `tenant_access_denied` (pérdida de membresía o cambio de estatus del tenant), el interceptor limpia el contexto de la empresa activa y redirige a `/select-company`. Si es `role_permission_denied`, solo muestra un *Toast* de falta de permisos y conserva el contexto.
* **Manejo de `500 Internal Server Error`:** Muestra un mensaje limpio al usuario junto con el `error_id` devuelto por el servidor como folio de seguimiento. Nunca se muestra información técnica.
* **Descargas autenticadas `[E-07]`:** `xml_url` y `pdf_url` no se abren con `<a href>` (no enviarían el Bearer ni `X-Company-ID`); se solicitan con Axios como *blob* y se descargan desde el navegador.

---

## 2. Manejo de Estado Global (Pinia Stores)

### 2.1 `useAuthStore` (Autenticación y Seguridad)
* **Responsabilidades:** 
  * Administrar el ciclo de vida de las credenciales, el token de acceso y el token de actualización (*refresh token*).
  * Almacenar el perfil del usuario autenticado y su matriz global de membresías (`memberships`) por empresa.
  * Proveer métodos reactivos para inicio de sesión (`login`), cierre de sesión (`logout`) y verificación de roles a nivel de tenant (`Socio`, `Auxiliar`, `Auditor`, `Cliente`).
* **Persistencia:** Sincronización automática de tokens, datos de usuario y membresías con el almacenamiento local del navegador (`localStorage`) para mantener la sesión activa tras recargas del navegador.

### 2.2 `useTenantStore` (Gestión de Tenants y Empresa Activa) `[E-01]`
* **Responsabilidades:**
  * Mantener el listado actualizado de empresas asociadas al usuario autenticado (`companies`).
  * Administrar el objeto o identificador de la empresa activa seleccionada (`currentCompany`).
  * Proveer métodos para cambiar de empresa activa (`setCurrentCompany`), lo cual actualiza de forma inmediata el estado global y sincroniza el contexto con el cliente HTTP y `localStorage`.

---

## 3. Arquitectura de Vistas y Rutas (Vue Router)

### 3.1 Mapa de Rutas del Sistema
* **Rutas Públicas:**
  * `/login` — Vista de autenticación y credenciales de acceso.
* **Rutas Privadas (Estructura de Layout Principal / Dashboard):**
  * `/select-company` `[E-08]` — Vista general para la selección de la empresa o contribuyente activo del despacho (las rutas van en inglés).
  * `/companies/:id/dashboard` — Resumen ejecutivo del periodo (KPIs).
  * `/companies/:id/documents` — Módulo de bóveda fiscal, carga masiva de archivos XML (CFDI 4.0) y PDF, y listado de comprobantes.
  * `/companies/:id/entries` — Módulo de pólizas contables (ingresos, egresos y diario) con validación estricta de partida doble.
  * `/companies/:id/periods` — Módulo de gestión, control y cierre/reapertura de periodos fiscales mensuales.
  * `/companies/:id/accounts` — Catálogo de cuentas SAT.
  * `/companies/:id/reconciliation` — Conciliación bancaria.
  * `/companies/:id/reports` — Balanza de comprobación y resumen ejecutivo.
  * `/companies/:id/audit-log` — Bitácora de auditoría (`PARTNER` y `AUDITOR`).
  * `/companies/:id/members` — Gestión de miembros (`PARTNER`).
* **Rutas de Error / Comodín:**
  * Ruta de captura 404 para URLs no encontradas.

### 3.2 Guardias de Navegación (Navigation Guards)
* **Validación de Autenticación:** Intercepta la navegación a rutas privadas para verificar que el usuario posea una sesión válida; de lo contrario, redirige al formulario de acceso preservando la ruta de destino.
* **Validación de Contexto Tenant (Deep Linking):** 
  * Verifica que exista una `currentCompany` seleccionada en el estado global antes de permitir el acceso a cualquier ruta operativa (`/companies/:id/...`).
  * Si el usuario accede mediante una URL directa (*deep linking*) sin una empresa activa previa, el guard evalúa el ID en la URL y, si el usuario posee membresía válida, sincroniza automáticamente el store de empresa sin fricciones.
  * Si el identificador de la empresa en la URL no coincide con los permisos del usuario, la navegación se interrumpe y se redirige a `/select-company`.
* **Validación de Rol `[E-12]` `[E-13]`:** Las rutas declaran los roles permitidos (`meta.roles`). El menú lateral se filtra con `useRBAC`; el rol `CLIENT` solo ve Documentos y Resumen. La ocultación en UI es solo ergonomía: la autorización real es siempre la del backend.
# 06_SECURITY_AND_HARDENING_SPEC.md

Este documento establece las especificaciones técnicas de **seguridad, validación de entradas, manejo global de excepciones y hardening** para el sistema contable multi-empresa (Django + Vue 3). Su objetivo es garantizar la integridad transaccional, la protección contra vulnerabilidades comunes (OWASP Top 10) y el cumplimiento de los estándares requeridos para operar comprobantes fiscales en México.

> **Precedencia:** `docs/00_ERRATA.md` prevalece sobre este documento. Los puntos ajustados por la errata se marcan con `[E-xx]`.

---

## 1. Validación, Sanitización y Almacenamiento de Archivos (XML/PDF)

Para la carga masiva e individual de comprobantes fiscales (CFDI), se implementa una capa de validación estricta tanto en el cliente (Vue 3) como en el backend (Django REST Framework).

### A. Restricciones de Tipo y Tamaño
* **MIME Types Permitidos:**
  * **Archivos XML:** `application/xml`, `text/xml` (validando además la estructura sintáctica del nodo raíz `<cfdi:Comprobante>` mediante `defusedxml.ElementTree` `[E-05]`, que previene ataques XXE / *XML External Entity* y de expansión de entidades / *billion laughs*; se aceptan los namespaces CFDI 4.0 y 3.3).
  * **Archivos PDF:** `application/pdf` (verificando la firma de cabecera `%PDF-`).
* **Límite de Tamaño `[E-04]`:**
  * Máximo **2 MB por XML** y **5 MB por PDF**, y máximo **50 archivos por petición**, para prevenir ataques de denegación de servicio (DoS) por agotamiento de memoria o espacio en disco.
  * Se aplican `DATA_UPLOAD_MAX_NUMBER_FILES = 50`, `FILE_UPLOAD_MAX_MEMORY_SIZE` y `client_max_body_size` en Nginx.
  * Los PDF se emparejan con el XML de mismo nombre base; un PDF sin pareja se reporta como `orphan_pdf` `[E-06]`.

### B. Sanitización de Nombres y Prevención de *Directory Traversal*
* Los nombres originales de los archivos subidos **nunca** se utilizan directamente en el sistema de archivos.
* El backend procesa el nombre mediante utilidades seguras (`os.path.basename` y `uuid4`) para evitar rutas maliciosas (`../../`):
  ```python
  import os
  from uuid import uuid4
  from django.utils import timezone

  def document_upload_path(instance, filename):  # [E-07] ruta única, igual que en 02_DATABASE_SPEC
      ext = os.path.basename(filename).rsplit('.', 1)[-1].lower()
      local_date = timezone.localtime(instance.issue_date)
      return f"companies/{instance.company_id}/documents/{local_date:%Y}/{local_date:%m}/{uuid4()}.{ext}"
  ```
* El nombre original solo se guarda como dato informativo en `Document.original_filename`.
* Se rechazan explícitamente caracteres nulos (`\x00`), barras invertidas o secuencias de escape en los metadatos de la petición.

### C. Estructura de Almacenamiento Local (Aislada por Empresa)
* Los archivos se almacenan dentro del contenedor Docker en un volumen persistente estructurado estrictamente por *tenant*:
  ```text
  MEDIA_ROOT/
  └── companies/
      ├── {company_id_1}/
      │   └── documents/
      │       └── {yyyy}/{mm}/
      │           ├── uuid-v4-file-1.xml
      │           └── uuid-v4-file-2.pdf
      └── {company_id_2}/
          └── documents/
  ```
* El acceso directo a los archivos estáticos en `MEDIA_ROOT` estará bloqueado por el servidor web (Nginx/Gunicorn); las descargas se servirán únicamente a través de `GET /api/v1/documents/{id}/download/?file=xml|pdf` `[E-07]`, un endpoint autenticado que verifica que el usuario pertenece a `company_id` (un documento de otra empresa devuelve `404`). El frontend lo consume como *blob* con el Bearer.

---

## 2. Manejo Global de Errores y Excepciones

Para evitar la exposición de trazas de código (*stack traces*) en producción y mantener una experiencia de usuario fluida, se estandariza el manejo de excepciones.

### A. Estructura de Respuesta JSON Estándar
Todas las respuestas de error de la API deben retornar un formato predecible mediante un *Custom Exception Handler* en Django REST Framework:

```json
{
  "success": false,
  "message": "Ocurrió un error al procesar la solicitud.",
  "error_id": "a1b2c3d4-e5f6-7890-abcd-ef0123456789",
  "data": null,
  "errors": [
    { "field": null, "code": "internal_server_error", "message": "Ocurrió un error inesperado. Contacte a soporte técnico." }
  ]
}
```

* **`[E-02]`:** `errors` es **siempre un arreglo** `[{field, code, message}]`, igual que en `01_CORE_SPECS.md` y `03_BACKEND_API_SPEC.md`. No se utiliza el formato de objeto `{campo: [...]}`.

* **`error_id`:** UUID único generado al capturar una excepción no controlada (`500`); es `null` en los demás errores. El backend registra el *stack trace* completo en los logs internos asociado a este ID, permitiendo al equipo de soporte rastrear fallos sin exponer información sensible al cliente.

### B. Integridad Transaccional (`transaction.atomic`)
* Todas las operaciones críticas de escritura (carga de facturas, creación de pólizas, cierre de periodos) deben envolverse en bloques transaccionales:
  ```python
  from django.db import transaction

  @transaction.atomic
  def create_accounting_entry(...):
      # Si falla cualquier validación o inserción, se ejecuta un rollback automático
      pass
  ```
* **Carga masiva `[E-24]`:** no se usa `ATOMIC_REQUESTS`. Cada archivo se procesa en su propio `transaction.atomic()` (savepoint), de modo que un fallo individual no revierte el lote completo.

### C. Interceptores de Axios en el Frontend (Vue 3 / Pinia)
El cliente frontend gestiona de forma centralizada las respuestas HTTP mediante interceptores:
* **Código `401 (Unauthorized)` `[E-08]`:** Un único intento de *refresh*; si falla, invalida el token actual en Pinia, limpia el almacenamiento local y redirige al usuario a `/login`.
* **Código `403 (Forbidden)` `[E-08]`:** Si el `code` es `tenant_access_denied`, limpia la empresa activa y redirige a `/select-company`. Si es `role_permission_denied`, despliega un *Toast* indicando falta de permisos para la acción solicitada.
* **Código `500 (Internal Server Error)`:** Muestra un mensaje limpio al usuario junto con el `error_id` devuelto por el servidor como folio de seguimiento.

---

## 3. Protección de Rutas y Prevención de Inyección

### A. Prevención de XSS y SQL Injection
* **SQL Injection:** Protegido nativamente mediante el uso estricto del ORM de Django (consultas parametrizadas). Se prohíbe el uso de `.raw()` o consultas SQL concatenadas manualmente.
* **XSS (Cross-Site Scripting):** Vue 3 escapa automáticamente las variables renderizadas en las plantillas (`{{ variable }}`). Adicionalmente, los formularios validan las entradas en el frontend y se sanitizan en los serializadores de DRF.

### B. Configuración de CORS y Cabeceras de Seguridad en Django `[E-09]`
Configuración requerida en `settings.py` mediante `django-cors-headers` y cabeceras HTTP de hardening:

```python
# CORS Configuration
CORS_ALLOWED_ORIGINS = [
    "http://localhost:5173",  # Desarrollo Frontend (Vite)
    "https://tudominio-produccion.com",
]
CORS_ALLOW_CREDENTIALS = False  # Se autentica con Bearer, no con cookies

# X-Company-ID no está en los headers permitidos por defecto: sin esto el navegador
# bloquea todas las peticiones operativas.
from corsheaders.defaults import default_headers
CORS_ALLOW_HEADERS = list(default_headers) + ["x-company-id"]

# Security Headers
# SECURE_BROWSER_XSS_FILTER se eliminó en Django 4.0: ya no se usa.
X_FRAME_OPTIONS = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"

# Solo en settings/production.py
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
# Content-Security-Policy mediante django-csp (y en nginx.conf)
```

### C. Autenticación y Dependencias `[E-09]`
* **Throttling de login:** `POST /api/v1/auth/login/` limitado a 5 intentos por minuto por IP (`429`).
* **JWT en `localStorage`:** riesgo aceptado para el MVP, mitigado con una política CSP estricta y la ausencia de HTML inyectado (Vue escapa por defecto; prohibido `v-html` con datos externos).
* **Auditoría de dependencias:** antes de la demo se ejecutan `python manage.py check --deploy`, `pip-audit` y `npm audit`.

---

## 4. Datos de Prueba para la Demo del Hackathon (`seed_accounting_data`)

Para garantizar una presentación fluida y sin vacíos de información, se implementará un comando de gestión en Django que pueble la base de datos con un escenario realista.

### Instrucciones de Ejecución
```bash
python manage.py seed_accounting_data
```

### Especificación del Comando (`seed_accounting_data.py`)
El comando generará automáticamente los siguientes elementos de forma idempotente:

1. **Empresas Demo (2) `[E-17]`:**
   * *Comercializadora del Norte* (RFC simulado: `CNO200101AB9`)
   * *Servicios Digitales del Altiplano* (RFC simulado: `SDA210515XY1`)
   * Las razones sociales van **sin régimen societario** (CFDI 4.0). Los RFC deben pasar el `RFC_REGEX` de `02_DATABASE_SPEC.md`.
2. **Usuarios con los 4 Roles del Sistema:**
   * **Socio:** Control total y administración de ambas empresas.
   * **Auxiliar:** Captura de pólizas y subida de XMLs.
   * **Auditor:** Acceso exclusivo de consulta y revisión de reportes.
   * **Cliente:** Acceso a los comprobantes de **su empresa** `[E-13]` y a la vista resumida de reportes (solo en la primera empresa demo).
   * Correos tipo `socio@demo.mx`, `auxiliar@demo.mx`, `auditor@demo.mx`, `cliente@demo.mx`; la contraseña se lee de la variable de entorno `DEMO_PASSWORD`. Los usuarios se crean con el modelo `User` personalizado `[E-10]`.
3. **Periodos Contables `[E-25]`:**
   * Periodos mensuales abiertos (ej. Periodo actual) y cerrados (ej. Mes anterior) para demostrar el bloqueo de modificaciones en periodos cerrados.
   * **Orden obligatorio:** crear periodos → cargar documentos y pólizas con los **mismos servicios** que usa la API → **al final**, cerrar el mes anterior (de lo contrario el propio bloqueo impediría cargar los datos).
4. **Comprobantes Simulados (10 Facturas XML):**
   * Archivos XML de prueba con estructura CFDI 4.0 válida asociados a las empresas demo (ingresos y egresos), permitiendo demostrar listados con paginación, filtros por fecha y cálculos de IVA/ISR en tiempo real. Se ingieren con el servicio `parse_cfdi_xml` / `bulk-upload`, no con inserciones directas.
5. **Pólizas y Conciliación (bloques posteriores):** 6 pólizas `POSTED` (2 ingresos, 2 egresos, 2 diario) y 1 `DRAFT`, todas cuadradas y creadas con `create_accounting_entry`; 12 movimientos bancarios en CSV (la mitad conciliables).

### Salvaguardas del Comando `[E-25]`
* Es **idempotente**: ejecutarlo dos veces deja los mismos conteos.
* Se **niega a correr con `DEBUG=False`** salvo que se pase `--force`.
* Las contraseñas provienen de `DEMO_PASSWORD`; nunca se escriben en el código.
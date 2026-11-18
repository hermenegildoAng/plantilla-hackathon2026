# `04_FRONTEND_UI_SYSTEM.md` — Sistema de Diseño y Estándares UI/UX

**Stack Tecnológico:** Vue 3 (Composition API + `<script setup>`), Tailwind CSS v3.4+, Lucide Vue Next.  
**Filosofía Visual:** **ERP Financiero de Alta Densidad (Compact SaaS)**. Prioriza la legibilidad numérica, la prevención de errores de contexto multi-tenant y el escaneo rápido de grandes volúmenes de pólizas y CFDI sin fatiga visual.

> **Precedencia:** `docs/00_ERRATA.md` prevalece sobre este documento. Los puntos ajustados por la errata se marcan con `[E-xx]`.

---

## 1. Paleta de Colores y Tokens (`tailwind.config.js`)

El sistema utiliza una base neutra fría (`Slate`) para reducir el deslumbramiento en jornadas largas, combinada con un acento corporativo (`Indigo`) y colores semánticos estrictos para operaciones contables (cargos, abonos, estados del SAT y bloqueos de periodo).

### 1.1 Superficies y Fondos
| Token / Clase Tailwind | Valor Hex | Uso en la Interfaz |
| :--- | :--- | :--- |
| `bg-slate-50` | `#F8FAFC` | Fondo general del canvas de la aplicación (área de trabajo). |
| `bg-white` | `#FFFFFF` | Tarjetas (*Cards*), contenedores de tablas, modales y Topbar. |
| `bg-slate-900` | `#0F172A` | Sidebar lateral principal (contraste alto para delimitar navegación). |
| `bg-slate-100` | `#F1F5F9` | Cabeceras de tablas (`<thead>`), filas alternas (*zebra striping* opcional) y estados *hover* en listas. |
| `border-slate-200` | `#E2E8F0` | Bordes estructurales principales (divisores de layout, tarjetas y celdas de tabla). |

### 1.2 Acentos Corporativos y Marca
| Token / Clase Tailwind | Valor Hex | Uso en la Interfaz |
| :--- | :--- | :--- |
| `indigo-600` (Primary) | `#4F46E5` | Botones de acción principal ("Guardar Póliza", "Cargar Archivos"), enlaces activos, indicadores de foco (`ring-indigo-500`). |
| `indigo-700` (Hover) | `#4338CA` | Estado *hover* de botones primarios. |
| `indigo-50` (Tint) | `#EEF2FF` | Fondo del badge de **Empresa Activa** en la Topbar y filas seleccionadas en tablas. |
| `indigo-900` (Text Tint) | `#312E81` | Texto de alto contraste sobre fondos `indigo-50`. |

### 1.3 Semántica Contable y Fiscal (SAT / Estados)
| Significado Contable | Fondo (`bg-*`) | Texto (`text-*`) | Borde (`border-*`) | Uso Específico |
| :--- | :--- | :--- | :--- | :--- |
| **Éxito / Cargos / Vigente** | `bg-emerald-50` | `text-emerald-700` | `border-emerald-200` | CFDI Vigente, Póliza Cuadrada, Saldo a favor, Conciliado. |
| **Error / Saldos Negativos** | `bg-rose-50` | `text-rose-700` | `border-rose-200` | CFDI Cancelado, Póliza Descuadrada, Pérdida, Errores de validación XML. |
| **Advertencia / Periodo Cerrado** | `bg-amber-50` | `text-amber-800` | `border-amber-300` | Periodo Contable Cerrado (Solo Lectura), Póliza en Borrador, Pendiente de pago. |
| **Informativo / Abonos** | `bg-sky-50` | `text-sky-700` | `border-sky-200` | Etiquetas de tipo de póliza (Ingreso, Egreso, Diario) y tooltips de ayuda. |

> **Estado SAT `[E-16]`:** el badge de estado de un CFDI refleja `sat_status`: `VALID` → "Vigente" (emerald), `CANCELLED` → "Cancelado" (rose), `UNVERIFIED` → "Sin verificar" (slate). El MVP solo valida la estructura del XML; no consulta el webservice del SAT.

> **Regla de Accesibilidad:** Todo texto informativo debe cumplir con un ratio de contraste mínimo **WCAG AA (4.5:1)**. Nunca usar tonos `400` o inferiores para texto sobre fondos claros.

---

## 2. Tipografía y Escala Numérica

Se utiliza **Inter** como fuente única de interfaz por su excelente legibilidad en tamaños pequeños y su soporte nativo para números tabulares.

### 2.1 Configuración de Fuente y OpenType
* **Familia:** `'Inter', system-ui, -apple-system, sans-serif` (importada vía Google Fonts con pesos `400`, `500`, `600`, `700`).
* **Regla Crítica para Cifras (`tabular-nums`):** Todo monto monetario, RFC, folio fiscal (UUID), cuenta contable y porcentaje **DEBE** incluir la utilidad `tabular-nums` (`font-variant-numeric: tabular-nums`). Esto garantiza que los dígitos tengan el mismo ancho fijo y las columnas de decimales se alineen verticalmente con precisión milimétrica.
* **Cálculo de Montos `[E-23]`:** la API entrega los importes como *string*. Toda suma, resta o comparación en el cliente usa `decimal.js` (composable `useCurrency`); nunca `parseFloat` ni aritmética de punto flotante.

### 2.2 Escala Tipográfica (Densidad Compacta ERP)
| Rol Visual | Clases Tailwind | Tamaño / Interlineado | Uso |
| :--- | :--- | :--- | :--- |
| **Título de Vista (`H1`)** | `text-lg font-semibold text-slate-900 tracking-tight` | `18px / 24px` | Encabezado principal de módulo (ej. "Pólizas Contables"). |
| **Subtítulo / Sección (`H2`)** | `text-sm font-semibold text-slate-800` | `14px / 20px` | Títulos de tarjetas, secciones de formulario y modales. |
| **Texto Base / Inputs** | `text-xs font-normal text-slate-700` | `12px / 16px` | Contenido de celdas de tabla, etiquetas de formularios y cuerpo general. |
| **Cabecera de Tabla (`<th>`)** | `text-[11px] font-semibold uppercase tracking-wider text-slate-600` | `11px / 16px` | Encabezados de columnas financieras. `[E-20]` Se usa `text-slate-600` (no `500`) para cumplir WCAG AA 4.5:1 sobre `bg-slate-100`. |
| **Monto Financiero (Tabla)** | `text-xs font-medium tabular-nums text-right` | `12px / 16px` | Columnas de Debe, Haber, Saldo Inicial, Saldo Final. |
| **KPI / Totalizador** | `text-xl font-bold tabular-nums tracking-tight` | `20px / 28px` | Tarjetas de resumen en Dashboard y totales de balanza. |
| **Metadatos / UUID / RFC** | `text-[11px] font-mono text-slate-500` | `11px / 14px` | Folios fiscales del SAT, códigos de catálogo agrupador y timestamps. |

---

## 3. Iconografía y Estándares Visuales

Se adopta **`lucide-vue-next`** como librería estándar única por su trazo uniforme (`stroke-width="1.75"`), geometría limpia y claridad en tamaños reducidos (`16px` y `18px`).

### 3.1 Tamaños Estándar de Iconos
* **Navegación Sidebar:** `w-4 h-4` (`16px`).
* **Botones de Acción y Topbar:** `w-4 h-4` (`16px`).
* **Indicadores de Estado en Tablas / Badges:** `w-3.5 h-3.5` (`14px`).
* **Ilustración de Estados Vacíos / Drag & Drop:** `w-8 h-8` (`32px`) en tono `text-slate-400`.

### 3.2 Diccionario Semántico de Iconos Contables
| Concepto / Acción | Icono Lucide | Color Sugerido | Contexto de Uso |
| :--- | :--- | :--- | :--- |
| **Empresa Activa (Tenant)** | `Building2` | `text-indigo-600` | Topbar junto al nombre de la razón social y RFC. |
| **Cambio de Empresa** | `ChevronsUpDown` | `text-slate-400` | Trigger del dropdown selector de tenant. |
| **Pólizas Contables** | `FileSpreadsheet` | `text-slate-300` | Módulo principal de pólizas y asientos. |
| **Bóveda Fiscal / CFDI (XML)** | `FileCode2` | `text-emerald-600` | Representación de archivos XML descargados del SAT. |
| **Representación Impresa (PDF)** | `FileText` | `text-rose-600` | Vista previa o descarga de facturas PDF. |
| **Catálogo de Cuentas** | `FolderTree` | `text-slate-300` | Estructura jerárquica de cuentas y subcuentas. |
| **Periodo Abierto** | `LockOpen` | `text-emerald-600` | Indicador de ejercicio/mes habilitado para captura. |
| **Periodo Cerrado (Bloqueado)** | `Lock` | `text-amber-600` | Banner de advertencia o candado en meses cerrados. |
| **Póliza Descuadrada / Error** | `AlertTriangle` | `text-rose-600` | Alerta cuando $\sum \text{Cargos} \neq \sum \text{Abonos}$. |
| **Conciliación Bancaria** | `ArrowLeftRight` | `text-indigo-600` | Cruce de movimientos bancarios contra pólizas. |
| **Carga Masiva XML** | `UploadCloud` | `text-indigo-600` | Zona de Drag & Drop para importar comprobantes. |

---

## 4. Patrones de Componentes Reutilizables (UI Kit)

### 4.1 Layout Base (Shell Multi-Tenant)
Estructura fija de viewport completo (`h-screen overflow-hidden flex bg-slate-50`) diseñada para evitar scroll doble en la página y mantener los controles críticos siempre accesibles:

* **Sidebar Izquierdo Colapsable:**
  * **Ancho expandido:** `w-56` (`224px`) / **Ancho colapsado:** `w-14` (`56px`) con transición suave (`transition-all duration-200`).
  * **Estilo:** Fondo oscuro `bg-slate-900 text-slate-300`, ítems con altura compacta (`h-8 px-2.5 rounded-md text-xs font-medium`).
  * **Estado Activo:** Fondo `bg-indigo-600 text-white` con icono resaltado.
  * **Footer del Sidebar:** Indicador compacto del **Ejercicio y Periodo Activo** (ej. `Noviembre 2026` con icono `LockOpen` verde o `Lock` ámbar).

* **Topbar Superior (`h-12 bg-white border-b border-slate-200 px-4`):**
  * **Zona Izquierda:** Botón de colapso de sidebar + *Breadcrumbs* dinámicos (`text-xs text-slate-500`).
  * **Zona Central / Derecha (Selector de Empresa Activa):**
    * **Trigger Visual Destacado:** Contenedor tipo píldora/tarjeta compacta (`bg-indigo-50/70 hover:bg-indigo-50 border border-indigo-200 rounded-md px-3 py-1 flex items-center gap-2.5 cursor-pointer`).
    * **Contenido Visible Siempre:** Icono `Building2` (`indigo-600`) + Razón Social truncada (`max-w-[220px] truncate text-xs font-semibold text-indigo-950`) + Badge de RFC (`text-[10px] font-mono bg-white text-indigo-700 px-1.5 py-0.5 rounded border border-indigo-200`) + `ChevronsUpDown`.
    * **Menú Desplegable (Dropdown):** Ancho fijo `w-80`, sombra `shadow-lg border border-slate-200 rounded-lg bg-white`. Incluye un **input de búsqueda autofocus** en la parte superior (`placeholder="Buscar por empresa o RFC..."`) y lista scrolleable (`max-h-64`) donde cada ítem muestra Razón Social, RFC y Régimen Fiscal, marcando con un `Check` (`indigo-600`) el tenant actual.
  * **Extremo Derecho:** Placeholder de notificaciones (sin lógica en el MVP; la descarga masiva del SAT está fuera de alcance `[E-20]`) y menú de perfil de usuario.

---

### 4.2 Tablas Financieras (Estilo ERP Compacto)
Diseñadas para soportar cientos de registros con lectura horizontal y vertical sin esfuerzo:

* **Contenedor:** `bg-white border border-slate-200 rounded-lg overflow-hidden flex flex-col`.
* **Cabeceras Fijas (*Sticky Header*):** `sticky top-0 z-10 bg-slate-100 border-b border-slate-200`. Permite hacer scroll vertical en las pólizas sin perder de vista qué columna es Debe o Haber.
* **Densidad de Filas:**
  * Altura de celda compacta: `py-1.5 px-3` (`~32px` de altura total por fila).
  * Divisores horizontales sutiles: `divide-y divide-slate-100`.
  * Divisores verticales opcionales en columnas numéricas: `border-l border-slate-100` para separar claramente `Debe`, `Haber` y `Saldo`.
  * Interacción: `hover:bg-slate-50/90 transition-colors`.
* **Reglas de Alineación:**
  * **Izquierda (`text-left`):** Fechas (`DD/MM/AAAA`), Tipo de Póliza, Concepto, Nombre de Cuenta, Proveedor.
  * **Centro (`text-center`):** Badges de Estado (Vigente/Cancelado, Cuadrada/Descuadrada) y botones de acción rápida (`w-7 h-7`).
  * **Derecha (`text-right tabular-nums`):** Todos los importes monetarios (`$14,250.00`), tasas de impuestos y cantidades. Los saldos negativos se formatean con signo menos o paréntesis en color `text-rose-700 font-semibold`.
* **Fila de Totalizadores (*Sticky Footer*):** `sticky bottom-0 bg-slate-50 border-t-2 border-slate-300 font-semibold text-xs tabular-nums` mostrando la sumatoria exacta de columnas numéricas y un badge visual que confirma si la póliza/balanza está cuadrada (`Diferencia: $0.00`).

---

### 4.3 Modales y Alertas Críticas
Patrón estandarizado para prevenir pérdida de información o alteraciones indebidas en la contabilidad:

* **Backdrop:** `fixed inset-0 bg-slate-900/50 backdrop-blur-[1px] z-50 flex items-center justify-center p-4`.
* **Contenedor Modal:** `bg-white rounded-lg shadow-xl border border-slate-200 w-full max-w-md overflow-hidden`.
* **Anatomía de Confirmación Crítica (ej. Modificar Periodo Cerrado o Cancelar Póliza):**
  1. **Cabecera con Icono Semántico:** Círculo de advertencia (`bg-amber-100 text-amber-700` para advertencias de periodo; `bg-rose-100 text-rose-700` para acciones destructivas) + Título claro (`text-sm font-semibold text-slate-900`).
  2. **Cuerpo Informativo:** Explicación concisa del impacto contable (`text-xs text-slate-600 leading-relaxed`) resaltando en **negrita** el folio de la póliza, empresa afectada o periodo fiscal.
  3. **Pie de Acción (`bg-slate-50 px-4 py-2.5 border-t border-slate-200 flex justify-end gap-2`):**
     * Botón Secundario: `bg-white border border-slate-300 text-slate-700 hover:bg-slate-50 text-xs font-medium px-3 py-1.5 rounded-md` ("Cancelar").
     * Botón Destructivo / Crítico: `bg-rose-600 hover:bg-rose-700 text-white text-xs font-medium px-3 py-1.5 rounded-md` ("Confirmar Cancelación").
* **Banners Persistentes (Contexto de Solo Lectura):** Si el usuario entra a un mes cerrado, se renderiza inmediatamente debajo de la Topbar un banner compacto (`bg-amber-50 border-b border-amber-200 px-4 py-1.5 text-xs text-amber-900 flex items-center gap-2`) con el icono `Lock` indicando que las ediciones están bloqueadas.

---

### 4.4 Zona de Carga Masiva (`Drag & Drop` XML / PDF)
Componente especializado para la recepción de comprobantes fiscales (CFDI 4.0) y generación automática de pólizas:

* **Estado Reposo:**
  * Contenedor rectangular con borde discontinuo: `border-2 border-dashed border-slate-300 hover:border-indigo-400 bg-slate-50/50 hover:bg-indigo-50/30 rounded-lg p-6 text-center transition-colors cursor-pointer`.
  * Contenido: Icono `UploadCloud` (`w-8 h-8 text-indigo-500 mx-auto mb-2`), título `"Arrastra tus archivos XML o PDF aquí"` (`text-xs font-semibold text-slate-700`), y subtítulo `"Soporta carga masiva de múltiples CFDI (.xml) y representaciones impresas (.pdf)"` (`text-[11px] text-slate-500`).
* **Estado Drag-Over (Archivo sobre la zona):**
  * Cambio inmediato de contraste: `border-indigo-600 bg-indigo-50/80 ring-2 ring-indigo-500/20`.
* **Cola de Procesamiento (Feedback Inmediato):**
  * Lista compacta debajo de la zona de carga (`divide-y divide-slate-100 border border-slate-200 rounded-md bg-white mt-3`) mostrando por cada archivo:
    * Icono según extensión (`FileCode2` para XML, `FileText` para PDF).
    * Nombre de archivo / UUID extraído + Tamaño (`text-xs`).
    * Barra de progreso delgada (`h-1 bg-indigo-600 rounded-full`) o badge de validación SAT (`Válido`, `UUID Duplicado`, `RFC Receptor no coincide con empresa activa`, `PDF sin XML`, `Archivo demasiado grande`).
* **Límites y Validación Previa `[E-04]` `[E-06]`:** XML ≤ 2 MB, PDF ≤ 5 MB, máximo 50 archivos por petición (los lotes mayores se dividen automáticamente). Cada PDF se empareja con el XML de mismo nombre base; sin pareja se reporta `orphan_pdf`. Al terminar se muestra un panel de resultados con los `processed` y `failed` que devuelve el backend (código y mensaje en español por archivo).

---

## 5. Resumen de Tokens Rápidos para Desarrollo

* **Border Radius Estándar:** `rounded-md` (`6px`) for buttons, inputs, and badges; `rounded-lg` (`8px`) for cards, tables, and modals.
* **Sombras `[E-20]`:** `shadow-sm` en tarjetas estáticas (`shadow-xs` no existe en Tailwind 3.4); `shadow-lg` únicamente en elementos flotantes (Dropdown de Empresa Activa, Tooltips y Modales).
* **Focus Ring Global:** `focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-1` para navegación rápida por teclado (crucial para capturistas contables que operan sin mouse).
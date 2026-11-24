<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import {
  AlertCircle,
  FileCode2,
  FilePlus2,
  FileText,
  Loader2,
  Lock,
  Paperclip,
  RefreshCw,
  Search,
  Trash2,
  UploadCloud,
} from 'lucide-vue-next'

import {
  deleteDocument,
  downloadDocumentFile,
  listAllDocuments,
  listAllPeriods,
  listDocuments,
} from '../api/documents'
import AttachPdfModal from '../components/documents/AttachPdfModal.vue'
import DropzoneUploader from '../components/documents/DropzoneUploader.vue'
import ManualDocumentModal from '../components/documents/ManualDocumentModal.vue'
import BaseBadge from '../components/ui/BaseBadge.vue'
import BaseButton from '../components/ui/BaseButton.vue'
import BaseInput from '../components/ui/BaseInput.vue'
import ConfirmModal from '../components/ui/ConfirmModal.vue'
import DataTable from '../components/ui/DataTable.vue'
import MoneyCell from '../components/ui/MoneyCell.vue'
import PaginationBar from '../components/ui/PaginationBar.vue'
import { useActivePeriod } from '../composables/useActivePeriod'
import { useCurrency } from '../composables/useCurrency'
import { ROLES, useRBAC } from '../composables/useRBAC'
import { useToast } from '../composables/useToast'

const MONTHS = [
  'Enero',
  'Febrero',
  'Marzo',
  'Abril',
  'Mayo',
  'Junio',
  'Julio',
  'Agosto',
  'Septiembre',
  'Octubre',
  'Noviembre',
  'Diciembre',
]

const DIRECTION_LABELS = {
  ISSUED: 'Emitido',
  RECEIVED: 'Recibido',
}

const CFDI_TYPE_LABELS = {
  I: 'Ingreso',
  E: 'Egreso',
  T: 'Traslado',
  N: 'Nómina',
  P: 'Pago',
  M: 'Manual',
}

const SAT_STATUS = {
  VALID: { label: 'Vigente', variant: 'success' },
  CANCELLED: { label: 'Cancelado', variant: 'danger' },
  UNVERIFIED: { label: 'Sin verificar', variant: 'neutral' },
}

const PAGE_SIZE = 25

const selectClass =
  'block h-8 w-full rounded-md border border-slate-300 bg-white px-2.5 text-xs text-slate-700 shadow-sm transition-colors focus:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-1 disabled:cursor-not-allowed disabled:bg-slate-50'

const columns = [
  { key: 'issue_date', label: 'Fecha', align: 'left', width: '92px' },
  { key: 'type', label: 'Tipo', align: 'center', width: '112px' },
  { key: 'counterpart', label: 'Emisor / Receptor', align: 'left' },
  { key: 'uuid', label: 'UUID', align: 'left', width: '190px' },
  { key: 'subtotal', label: 'Subtotal', align: 'right', width: '118px' },
  { key: 'iva_transferred', label: 'IVA', align: 'right', width: '104px' },
  { key: 'total', label: 'Total', align: 'right', width: '128px' },
  { key: 'status', label: 'Estado', align: 'center', width: '140px' },
  { key: 'actions', label: 'Acciones', align: 'center', width: '150px' },
]

const { can, isPartner } = useRBAC()
const { formatMoney, sum } = useCurrency()
const { setClosed, setReferenceDate, setFromPeriod } = useActivePeriod()
const toast = useToast()

const filters = reactive({
  fiscal_period: '',
  direction: '',
  cfdi_type: '',
  is_accounted: '',
  search: '',
})

const documents = ref([])
const count = ref(0)
const page = ref(1)
const loading = ref(false)
const totalsLoading = ref(false)
const loadError = ref('')
const periods = ref([])
const periodsLoading = ref(false)
const totals = ref({
  subtotal: '0.00',
  iva_transferred: '0.00',
  total: '0.00',
})

const showDropzone = ref(true)
const manualOpen = ref(false)
const attachOpen = ref(false)
const attachTarget = ref(null)
const deleteTarget = ref(null)
const deleting = ref(false)
const downloading = ref('')

let filterTimer = null
let filtersReady = false
let documentsRequestId = 0
let totalsRequestId = 0
let defaultPeriodApplied = false

const canUpload = computed(() =>
  can([ROLES.PARTNER, ROLES.ACCOUNTANT, ROLES.CLIENT]),
)
// GET /periods/ solo está disponible para roles internos (03 §3.6). El
// portal CLIENT conserva la bóveda y la carga, pero no la lista de periodos.
const canReadPeriods = computed(() =>
  can([ROLES.PARTNER, ROLES.ACCOUNTANT, ROLES.AUDITOR]),
)
const selectedPeriod = computed(
  () =>
    periods.value.find(
      (period) => String(period.id) === String(filters.fiscal_period),
    ) || null,
)
const periodClosed = computed(() => Boolean(selectedPeriod.value?.is_closed))
const canWrite = computed(() => canUpload.value && !periodClosed.value)
const canDelete = computed(
  () => isPartner.value && Boolean(selectedPeriod.value) && !periodClosed.value,
)

const periodLabel = computed(() => {
  if (!selectedPeriod.value) return 'Todos los periodos'
  return `${MONTHS[selectedPeriod.value.month - 1]} ${selectedPeriod.value.year}`
})

const totalsFormatted = computed(() => ({
  subtotal: formatMoney(totals.value.subtotal),
  iva_transferred: formatMoney(totals.value.iva_transferred),
  total: formatMoney(totals.value.total),
}))

function filterParams() {
  const params = {}
  if (filters.fiscal_period) params.fiscal_period = filters.fiscal_period
  if (filters.direction) params.direction = filters.direction
  if (filters.cfdi_type) params.cfdi_type = filters.cfdi_type
  if (filters.is_accounted !== '') params.is_accounted = filters.is_accounted
  const term = filters.search.trim()
  if (term) params.search = term
  return params
}

async function loadDocuments() {
  const requestId = ++documentsRequestId
  loading.value = true
  loadError.value = ''
  try {
    const payload = await listDocuments({
      ...filterParams(),
      page: page.value,
      page_size: PAGE_SIZE,
    })
    if (requestId !== documentsRequestId) return

    documents.value = payload?.results || []
    count.value = Number(payload?.count || 0)

    const maxPage = Math.max(1, Math.ceil(count.value / PAGE_SIZE))
    if (page.value > maxPage) {
      page.value = maxPage
      await loadDocuments()
    }
  } catch (error) {
    if (requestId !== documentsRequestId) return
    loadError.value =
      error?.message || 'No fue posible consultar los documentos de la empresa.'
    documents.value = []
    count.value = 0
  } finally {
    if (requestId === documentsRequestId) loading.value = false
  }
}

async function loadTotals() {
  const requestId = ++totalsRequestId
  totalsLoading.value = true
  try {
    const { results } = await listAllDocuments({
      ...filterParams(),
      page_size: 100,
    })
    if (requestId !== totalsRequestId) return

    totals.value = {
      subtotal: sum(results.map((document) => document.subtotal)),
      iva_transferred: sum(
        results.map((document) => document.iva_transferred),
      ),
      total: sum(results.map((document) => document.total)),
    }
  } catch {
    if (requestId === totalsRequestId) {
      totals.value = { subtotal: '0.00', iva_transferred: '0.00', total: '0.00' }
    }
  } finally {
    if (requestId === totalsRequestId) totalsLoading.value = false
  }
}

async function refreshAll() {
  await Promise.all([loadDocuments(), loadTotals()])
}

async function loadPeriods() {
  if (!canReadPeriods.value) {
    periods.value = []
    return
  }

  periodsLoading.value = true
  try {
    const { results } = await listAllPeriods()
    periods.value = [...results].sort(
      (left, right) =>
        right.year - left.year || right.month - left.month,
    )

    if (!defaultPeriodApplied && !filters.fiscal_period) {
      const now = new Date()
      const current = periods.value.find(
        (period) =>
          period.year === now.getFullYear() &&
          period.month === now.getMonth() + 1,
      )
      const target = current || periods.value[0]
      if (target) {
        filters.fiscal_period = String(target.id)
        defaultPeriodApplied = true
      }
    }
  } catch {
    periods.value = []
  } finally {
    periodsLoading.value = false
  }
}

function applyFilters() {
  clearTimeout(filterTimer)
  if (page.value !== 1) page.value = 1
  refreshAll()
}

function clearFilters() {
  filters.fiscal_period = ''
  filters.direction = ''
  filters.cfdi_type = ''
  filters.is_accounted = ''
  filters.search = ''
}

function changePage(nextPage) {
  if (nextPage === page.value) return
  page.value = nextPage
  loadDocuments()
}

watch(
  filters,
  () => {
    if (!filtersReady) return
    clearTimeout(filterTimer)
    filterTimer = setTimeout(applyFilters, 300)
  },
  { deep: true },
)

watch(
  selectedPeriod,
  (period) => {
    setFromPeriod(period)
  },
  { immediate: true },
)

onMounted(async () => {
  await loadPeriods()
  filtersReady = true
  await refreshAll()
})

onBeforeUnmount(() => {
  clearTimeout(filterTimer)
  setClosed(false)
  setReferenceDate(new Date())
})

function formatDate(value) {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '—'
  return new Intl.DateTimeFormat('es-MX', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    timeZone: 'America/Mexico_City',
  }).format(date)
}

function satStatus(value) {
  return SAT_STATUS[value] || { label: value || 'Sin verificar', variant: 'neutral' }
}

function documentLabel(document) {
  return (
    document?.uuid ||
    document?.original_filename ||
    (document?.folio ? `Folio ${document.folio}` : `Documento ${document?.id}`)
  )
}

function buildDownloadName(doc, kind) {
  const original = doc?.original_filename || ''
  const stem =
    original.replace(/\.[^.]+$/, '') ||
    doc?.uuid ||
    `documento-${doc?.id}`
  return `${String(stem).replace(/[\\/:*?"<>|]/g, '-')}.${kind}`
}

function isDownloading(doc, kind) {
  return downloading.value === `${doc.id}-${kind}`
}

async function downloadFile(doc, kind) {
  if (downloading.value) return
  downloading.value = `${doc.id}-${kind}`
  try {
    const blob = await downloadDocumentFile(doc.id, kind)
    const url = URL.createObjectURL(blob)
    const link = window.document.createElement('a')
    link.href = url
    link.download = buildDownloadName(doc, kind)
    window.document.body.appendChild(link)
    link.click()
    link.remove()
    window.setTimeout(() => URL.revokeObjectURL(url), 1000)
  } catch (error) {
    toast.error(
      error?.message || 'No fue posible descargar el archivo solicitado.',
      { title: 'Descarga no disponible' },
    )
  } finally {
    downloading.value = ''
  }
}

function openAttach(document) {
  if (!canWrite.value) return
  attachTarget.value = document
  attachOpen.value = true
}

function requestDelete(document) {
  if (!canDelete.value || document?.is_accounted) return
  deleteTarget.value = document
}

async function confirmDelete() {
  if (!deleteTarget.value) return
  deleting.value = true
  try {
    await deleteDocument(deleteTarget.value.id)
    toast.success('Documento eliminado correctamente.')
    deleteTarget.value = null
    await loadPeriods()
    await refreshAll()
  } catch (error) {
    toast.error(
      error?.message || 'No fue posible eliminar el documento.',
      { title: 'No se pudo eliminar' },
    )
  } finally {
    deleting.value = false
  }
}

async function onUploadCompleted(result) {
  const processed = Number(result?.summary?.processed_count || 0)
  const failed = Number(result?.summary?.failed_count || 0)

  if (failed > 0) {
    toast.warning(
      `${processed} importado${processed === 1 ? '' : 's'} y ` +
        `${failed} con error${failed === 1 ? '' : 'es'}.`,
      { title: 'Carga masiva finalizada con incidencias' },
    )
  } else {
    toast.success(
      `${processed} comprobante${processed === 1 ? '' : 's'} importado${processed === 1 ? '' : 's'}.`,
      { title: 'Carga masiva finalizada' },
    )
  }

  page.value = 1
  await loadPeriods()
  await refreshAll()
}

async function onManualSaved() {
  manualOpen.value = false
  page.value = 1
  await loadPeriods()
  await refreshAll()
}

async function onPdfAttached() {
  attachOpen.value = false
  await refreshAll()
}
</script>

<template>
  <section class="space-y-3">
    <header class="flex flex-wrap items-start justify-between gap-2">
      <div class="min-w-0">
        <h1 class="text-lg font-semibold tracking-tight text-slate-900">
          Documentos
        </h1>
        <p class="mt-1 max-w-2xl text-xs text-slate-600">
          Bóveda fiscal de CFDI (XML) y representaciones impresas (PDF) de
          <span class="font-medium text-slate-800">{{ periodLabel }}</span>.
        </p>
      </div>

      <div class="flex flex-wrap items-center gap-2">
        <BaseBadge v-if="periodClosed" variant="warning" dot>
          Periodo cerrado
        </BaseBadge>
        <BaseBadge v-else-if="!canUpload" variant="neutral" dot>
          Solo lectura
        </BaseBadge>

        <BaseButton
          v-if="canWrite"
          variant="secondary"
          @click="showDropzone = !showDropzone"
        >
          <template #icon>
            <UploadCloud class="w-3.5 h-3.5" aria-hidden="true" />
          </template>
          {{ showDropzone ? 'Ocultar carga' : 'Cargar XML/PDF' }}
        </BaseButton>

        <BaseButton v-if="canWrite" @click="manualOpen = true">
          <template #icon>
            <FilePlus2 class="w-3.5 h-3.5" aria-hidden="true" />
          </template>
          Comprobante manual
        </BaseButton>

        <BaseButton
          variant="ghost"
          size="sm"
          :loading="loading"
          title="Actualizar documentos"
          @click="refreshAll"
        >
          <template #icon>
            <RefreshCw class="w-3.5 h-3.5" aria-hidden="true" />
          </template>
          Actualizar
        </BaseButton>
      </div>
    </header>

    <div
      v-if="loadError"
      class="flex items-start gap-2 rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-[11px] text-rose-800"
      role="alert"
    >
      <AlertCircle class="mt-0.5 w-3.5 h-3.5 shrink-0" aria-hidden="true" />
      <p>{{ loadError }}</p>
    </div>

    <div class="rounded-lg border border-slate-200 bg-white p-3 shadow-sm">
      <div class="grid gap-2 sm:grid-cols-2 lg:grid-cols-6">
        <div>
          <label for="filter-period" class="mb-1 block text-[11px] font-medium text-slate-600">
            Periodo fiscal
            <span v-if="!canReadPeriods" class="font-normal text-slate-400">
              · rol interno
            </span>
          </label>
          <select
            id="filter-period"
            v-model="filters.fiscal_period"
            :class="selectClass"
            :disabled="periodsLoading || !canReadPeriods"
            :title="canReadPeriods ? undefined : 'La lista de periodos está disponible para roles internos.'"
          >
            <option value="">Todos los periodos</option>
            <option v-for="period in periods" :key="period.id" :value="String(period.id)">
              {{ MONTHS[period.month - 1] }} {{ period.year }}
              {{ period.is_closed ? ' · cerrado' : '' }}
            </option>
          </select>
        </div>

        <div>
          <label for="filter-direction" class="mb-1 block text-[11px] font-medium text-slate-600">
            Dirección
          </label>
          <select id="filter-direction" v-model="filters.direction" :class="selectClass">
            <option value="">Todas</option>
            <option value="ISSUED">Emitido</option>
            <option value="RECEIVED">Recibido</option>
          </select>
        </div>

        <div>
          <label for="filter-cfdi-type" class="mb-1 block text-[11px] font-medium text-slate-600">
            Tipo CFDI
          </label>
          <select id="filter-cfdi-type" v-model="filters.cfdi_type" :class="selectClass">
            <option value="">Todos</option>
            <option value="I">I · Ingreso</option>
            <option value="E">E · Egreso</option>
            <option value="T">T · Traslado</option>
            <option value="N">N · Nómina</option>
            <option value="P">P · Pago</option>
            <option value="M">M · Manual</option>
          </select>
        </div>

        <div>
          <label for="filter-accounted" class="mb-1 block text-[11px] font-medium text-slate-600">
            Contabilizado
          </label>
          <select id="filter-accounted" v-model="filters.is_accounted" :class="selectClass">
            <option value="">Todos</option>
            <option value="true">Contabilizados</option>
            <option value="false">Pendientes</option>
          </select>
        </div>

        <BaseInput
          v-model="filters.search"
          label="Búsqueda"
          placeholder="UUID, RFC o razón social"
          wrapper-class="lg:col-span-2"
          @keydown.enter="applyFilters"
        >
          <template #icon>
            <Search class="w-3.5 h-3.5" aria-hidden="true" />
          </template>
        </BaseInput>
      </div>

      <div class="mt-2 flex flex-wrap items-center justify-between gap-2">
        <p class="text-[11px] text-slate-500">
          <span class="font-semibold tabular-nums text-slate-700">{{ count }}</span>
          documento{{ count === 1 ? '' : 's' }} en el filtro
          <span v-if="totalsLoading" class="ml-1 text-slate-400">
            · calculando totalizadores…
          </span>
        </p>
        <BaseButton variant="ghost" size="sm" @click="clearFilters">
          Limpiar filtros
        </BaseButton>
      </div>
    </div>

    <DropzoneUploader
      v-if="canWrite && showDropzone"
      :disabled="loading"
      @completed="onUploadCompleted"
    />

    <div
      v-else-if="canUpload && periodClosed"
      class="flex items-center gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-[11px] text-amber-900"
      role="status"
    >
      <Lock class="w-3.5 h-3.5 shrink-0 text-amber-600" aria-hidden="true" />
      <p>
        El periodo <span class="font-semibold">{{ periodLabel }}</span> está
        cerrado. La carga, el adjunto de PDF y la eliminación están
        deshabilitados.
      </p>
    </div>

    <DataTable
      :columns="columns"
      :rows="documents"
      :loading="loading"
      row-key="id"
      max-height="62vh"
      :totals="totalsFormatted"
      footer-label="Totales del filtro"
      empty-title="Sin documentos"
      empty-description="Ajusta los filtros o carga comprobantes XML/PDF para esta empresa."
    >
      <template #cell-issue_date="{ row }">
        <span class="whitespace-nowrap text-xs text-slate-700">
          {{ formatDate(row.issue_date) }}
        </span>
      </template>

      <template #cell-type="{ row }">
        <div class="flex flex-col items-center gap-0.5">
          <BaseBadge :variant="row.direction === 'ISSUED' ? 'brand' : 'info'">
            {{ DIRECTION_LABELS[row.direction] || row.direction }}
          </BaseBadge>
          <span class="text-[10px] text-slate-500">
            {{ CFDI_TYPE_LABELS[row.cfdi_type] || row.cfdi_type }}
          </span>
        </div>
      </template>

      <template #cell-counterpart="{ row }">
        <div class="min-w-0 max-w-[320px]">
          <p class="truncate text-xs font-medium text-slate-800" :title="row.issuer_name">
            {{ row.issuer_name }}
          </p>
          <p class="truncate font-mono text-[10px] text-slate-500">
            {{ row.issuer_rfc }}
            <span class="text-slate-400" aria-hidden="true">→</span>
            {{ row.receiver_rfc }}
          </p>
          <p class="truncate text-[10px] text-slate-500" :title="row.receiver_name">
            {{ row.receiver_name }}
          </p>
        </div>
      </template>

      <template #cell-uuid="{ row }">
        <p
          v-if="row.uuid"
          class="truncate font-mono text-[11px] text-slate-600"
          :title="row.uuid"
        >
          {{ row.uuid }}
        </p>
        <span v-else class="text-[11px] text-slate-400">Sin UUID</span>
      </template>

      <template #cell-subtotal="{ row }">
        <MoneyCell :value="row.subtotal" />
      </template>

      <template #cell-iva_transferred="{ row }">
        <MoneyCell :value="row.iva_transferred" />
      </template>

      <template #cell-total="{ row }">
        <MoneyCell :value="row.total" class="font-medium text-slate-900" />
      </template>

      <template #cell-status="{ row }">
        <div class="flex flex-col items-center gap-1">
          <BaseBadge :variant="row.is_accounted ? 'success' : 'warning'" dot>
            {{ row.is_accounted ? 'Contabilizado' : 'Pendiente' }}
          </BaseBadge>
          <BaseBadge :variant="satStatus(row.sat_status).variant">
            {{ satStatus(row.sat_status).label }}
          </BaseBadge>
        </div>
      </template>

      <template #cell-actions="{ row }">
        <div class="flex items-center justify-center gap-0.5">
          <button
            v-if="row.xml_url"
            type="button"
            class="inline-flex h-7 w-7 items-center justify-center rounded-md text-slate-500 transition-colors hover:bg-slate-100 hover:text-slate-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 disabled:opacity-50"
            title="Descargar XML"
            aria-label="Descargar XML"
            :disabled="Boolean(downloading)"
            @click="downloadFile(row, 'xml')"
          >
            <Loader2
              v-if="isDownloading(row, 'xml')"
              class="w-3.5 h-3.5 animate-spin"
              aria-hidden="true"
            />
            <FileCode2 v-else class="w-3.5 h-3.5" aria-hidden="true" />
          </button>

          <button
            v-if="row.pdf_url"
            type="button"
            class="inline-flex h-7 w-7 items-center justify-center rounded-md text-slate-500 transition-colors hover:bg-slate-100 hover:text-slate-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 disabled:opacity-50"
            title="Descargar PDF"
            aria-label="Descargar PDF"
            :disabled="Boolean(downloading)"
            @click="downloadFile(row, 'pdf')"
          >
            <Loader2
              v-if="isDownloading(row, 'pdf')"
              class="w-3.5 h-3.5 animate-spin"
              aria-hidden="true"
            />
            <FileText v-else class="w-3.5 h-3.5" aria-hidden="true" />
          </button>

          <button
            v-if="canWrite"
            type="button"
            class="inline-flex h-7 w-7 items-center justify-center rounded-md text-slate-500 transition-colors hover:bg-slate-100 hover:text-slate-700 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            :title="row.pdf_url ? 'Reemplazar PDF' : 'Adjuntar PDF'"
            :aria-label="row.pdf_url ? 'Reemplazar PDF' : 'Adjuntar PDF'"
            @click="openAttach(row)"
          >
            <Paperclip class="w-3.5 h-3.5" aria-hidden="true" />
          </button>

          <button
            v-if="canDelete && !row.is_accounted"
            type="button"
            class="inline-flex h-7 w-7 items-center justify-center rounded-md text-slate-400 transition-colors hover:bg-rose-50 hover:text-rose-700 focus:outline-none focus:ring-2 focus:ring-rose-500"
            title="Eliminar documento"
            aria-label="Eliminar documento"
            @click="requestDelete(row)"
          >
            <Trash2 class="w-3.5 h-3.5" aria-hidden="true" />
          </button>

          <span
            v-if="!row.xml_url && !row.pdf_url && !canWrite && !(canDelete && !row.is_accounted)"
            class="text-[11px] text-slate-400"
          >
            —
          </span>
        </div>
      </template>
    </DataTable>

    <PaginationBar
      :page="page"
      :page-size="PAGE_SIZE"
      :count="count"
      :loading="loading"
      @change="changePage"
    />

    <ManualDocumentModal v-model="manualOpen" @saved="onManualSaved" />
    <AttachPdfModal
      v-model="attachOpen"
      :document="attachTarget"
      @attached="onPdfAttached"
    />

    <ConfirmModal
      :model-value="Boolean(deleteTarget)"
      title="Eliminar documento"
      confirm-text="Eliminar documento"
      variant="danger"
      :loading="deleting"
      @update:model-value="(value) => { if (!value) deleteTarget = null }"
      @confirm="confirmDelete"
      @cancel="deleteTarget = null"
    >
      <p>
        Se eliminará permanentemente el comprobante
        <strong class="font-mono text-slate-900">
          {{ deleteTarget ? documentLabel(deleteTarget) : '' }}
        </strong>
        y sus archivos XML/PDF. Esta acción no se puede deshacer.
      </p>
      <p class="mt-1.5 text-[11px] text-slate-500">
        Solo se permite eliminar documentos no contabilizados de un periodo
        abierto.
      </p>
    </ConfirmModal>
  </section>
</template>

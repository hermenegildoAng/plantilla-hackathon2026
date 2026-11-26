<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  AlertCircle,
  Eye,
  Plus,
  RefreshCw,
  Search,
} from 'lucide-vue-next'

import { listAllPeriods, listEntries } from '../api/accounting'
import EntryDetailDrawer from '../components/accounting/EntryDetailDrawer.vue'
import BaseBadge from '../components/ui/BaseBadge.vue'
import BaseButton from '../components/ui/BaseButton.vue'
import BaseInput from '../components/ui/BaseInput.vue'
import DataTable from '../components/ui/DataTable.vue'
import MoneyCell from '../components/ui/MoneyCell.vue'
import PaginationBar from '../components/ui/PaginationBar.vue'
import { useActivePeriod } from '../composables/useActivePeriod'
import { useCurrency } from '../composables/useCurrency'
import { ROLES, useRBAC } from '../composables/useRBAC'

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

const ENTRY_TYPE_LABELS = {
  INCOME: 'Ingreso',
  EXPENSE: 'Egreso',
  JOURNAL: 'Diario',
}

const STATUS_LABELS = {
  POSTED: 'Contabilizada',
  DRAFT: 'Borrador',
}

const PAGE_SIZE = 25

const selectClass =
  'block h-8 w-full rounded-md border border-slate-300 bg-white px-2.5 text-xs text-slate-700 shadow-sm transition-colors focus:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-1 disabled:cursor-not-allowed disabled:bg-slate-50'

const columns = [
  { key: 'entry_date', label: 'Fecha', align: 'left', width: '96px' },
  { key: 'folio', label: 'Folio', align: 'left', width: '140px' },
  { key: 'entry_type', label: 'Tipo', align: 'center', width: '96px' },
  { key: 'concept', label: 'Concepto', align: 'left' },
  { key: 'period_label', label: 'Periodo', align: 'center', width: '92px' },
  { key: 'status', label: 'Estado', align: 'center', width: '128px' },
  { key: 'total_debit', label: 'Cargos', align: 'right', width: '126px' },
  { key: 'total_credit', label: 'Abonos', align: 'right', width: '126px' },
  { key: 'actions', label: 'Acciones', align: 'center', width: '88px' },
]

const route = useRoute()
const router = useRouter()
const { can } = useRBAC()
const { sum } = useCurrency()
const { setFromPeriod } = useActivePeriod()

const canManage = computed(() => can([ROLES.PARTNER, ROLES.ACCOUNTANT]))

const filters = reactive({
  fiscal_period: '',
  entry_type: '',
  status: '',
  date_from: '',
  date_to: '',
  search: '',
})

const entries = ref([])
const periods = ref([])
const count = ref(0)
const page = ref(1)
const loading = ref(false)
const periodsLoading = ref(false)
const loadError = ref('')
const selectedEntry = ref(null)

let filterTimer = null
let filtersReady = false
let requestId = 0
let defaultPeriodApplied = false

const selectedPeriod = computed(
  () =>
    periods.value.find(
      (period) => String(period.id) === String(filters.fiscal_period),
    ) || null,
)

const pageTotals = computed(() => ({
  total_debit: sum(entries.value.map((entry) => entry.total_debit)),
  total_credit: sum(entries.value.map((entry) => entry.total_credit)),
}))

const selectedEntryPeriod = computed(() => {
  if (!selectedEntry.value) return null
  return (
    periods.value.find(
      (period) =>
        String(period.id) === String(selectedEntry.value.fiscal_period),
    ) || null
  )
})

const selectedEntryClosed = computed(() =>
  Boolean(selectedEntryPeriod.value?.is_closed),
)

function filterParams() {
  const params = {}
  if (filters.fiscal_period) params.fiscal_period = filters.fiscal_period
  if (filters.entry_type) params.entry_type = filters.entry_type
  if (filters.status) params.status = filters.status
  if (filters.date_from) params.date_from = filters.date_from
  if (filters.date_to) params.date_to = filters.date_to
  const term = filters.search.trim()
  if (term) params.search = term
  return params
}

async function loadPeriods() {
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
      if (current) {
        filters.fiscal_period = String(current.id)
        defaultPeriodApplied = true
      }
    }
  } catch {
    periods.value = []
  } finally {
    periodsLoading.value = false
  }
}

async function loadEntries() {
  const currentRequest = ++requestId
  loading.value = true
  loadError.value = ''
  try {
    const payload = await listEntries({
      ...filterParams(),
      page: page.value,
      page_size: PAGE_SIZE,
    })
    if (currentRequest !== requestId) return

    entries.value = payload?.results || []
    count.value = Number(payload?.count || 0)

    const maxPage = Math.max(1, Math.ceil(count.value / PAGE_SIZE))
    if (page.value > maxPage) {
      page.value = maxPage
      await loadEntries()
    }
  } catch (error) {
    if (currentRequest !== requestId) return
    entries.value = []
    count.value = 0
    loadError.value =
      error?.message || 'No fue posible consultar las pólizas de la empresa.'
  } finally {
    if (currentRequest === requestId) loading.value = false
  }
}

function applyFilters() {
  clearTimeout(filterTimer)
  if (page.value !== 1) page.value = 1
  loadEntries()
}

function clearFilters() {
  filters.fiscal_period = ''
  filters.entry_type = ''
  filters.status = ''
  filters.date_from = ''
  filters.date_to = ''
  filters.search = ''
}

function changePage(nextPage) {
  if (nextPage === page.value) return
  page.value = nextPage
  loadEntries()
}

function openDetail(entry) {
  selectedEntry.value = entry
}

function editSelected() {
  if (!selectedEntry.value) return
  const entryIdValue = selectedEntry.value.id
  selectedEntry.value = null
  router.push({
    name: 'entry-edit',
    params: { id: route.params.id, entryId: entryIdValue },
  })
}

function formatDate(value) {
  if (!value) return '—'
  const [year, month, day] = String(value).split('-')
  if (!year || !month || !day) return value
  return `${day}/${month}/${year}`
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
  await loadEntries()
})

onBeforeUnmount(() => {
  clearTimeout(filterTimer)
})
</script>

<template>
  <section class="space-y-3">
    <header class="flex flex-wrap items-start justify-between gap-2">
      <div class="min-w-0">
        <h1 class="text-lg font-semibold tracking-tight text-slate-900">
          Pólizas
        </h1>
        <p class="mt-1 max-w-2xl text-xs text-slate-600">
          Pólizas de ingreso, egreso y diario con validación estricta de partida
          doble.
        </p>
      </div>

      <div class="flex flex-wrap items-center gap-2">
        <BaseButton
          variant="ghost"
          size="sm"
          :loading="loading"
          title="Actualizar pólizas"
          @click="loadEntries"
        >
          <template #icon>
            <RefreshCw class="w-3.5 h-3.5" aria-hidden="true" />
          </template>
          Actualizar
        </BaseButton>
        <BaseButton
          v-if="canManage"
          @click="router.push({ name: 'entry-create', params: { id: route.params.id } })"
        >
          <template #icon>
            <Plus class="w-3.5 h-3.5" aria-hidden="true" />
          </template>
          Nueva póliza
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
          <label for="entry-filter-period" class="mb-1 block text-[11px] font-medium text-slate-600">
            Periodo fiscal
          </label>
          <select
            id="entry-filter-period"
            v-model="filters.fiscal_period"
            :class="selectClass"
            :disabled="periodsLoading"
          >
            <option value="">Todos los periodos</option>
            <option
              v-for="period in periods"
              :key="period.id"
              :value="String(period.id)"
            >
              {{ MONTHS[period.month - 1] }} {{ period.year }}
              {{ period.is_closed ? ' · cerrado' : '' }}
            </option>
          </select>
        </div>

        <div>
          <label for="entry-filter-type" class="mb-1 block text-[11px] font-medium text-slate-600">
            Tipo
          </label>
          <select id="entry-filter-type" v-model="filters.entry_type" :class="selectClass">
            <option value="">Todos</option>
            <option value="INCOME">Ingreso</option>
            <option value="EXPENSE">Egreso</option>
            <option value="JOURNAL">Diario</option>
          </select>
        </div>

        <div>
          <label for="entry-filter-status" class="mb-1 block text-[11px] font-medium text-slate-600">
            Estado
          </label>
          <select id="entry-filter-status" v-model="filters.status" :class="selectClass">
            <option value="">Todos</option>
            <option value="POSTED">Contabilizada</option>
            <option value="DRAFT">Borrador</option>
          </select>
        </div>

        <div>
          <label for="entry-filter-from" class="mb-1 block text-[11px] font-medium text-slate-600">
            Desde
          </label>
          <input id="entry-filter-from" v-model="filters.date_from" type="date" :class="selectClass" />
        </div>

        <div>
          <label for="entry-filter-to" class="mb-1 block text-[11px] font-medium text-slate-600">
            Hasta
          </label>
          <input id="entry-filter-to" v-model="filters.date_to" type="date" :class="selectClass" />
        </div>

        <BaseInput
          v-model="filters.search"
          label="Búsqueda"
          placeholder="Folio o concepto"
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
          póliza{{ count === 1 ? '' : 's' }} en el filtro
        </p>
        <BaseButton variant="ghost" size="sm" @click="clearFilters">
          Limpiar filtros
        </BaseButton>
      </div>
    </div>

    <DataTable
      :columns="columns"
      :rows="entries"
      :loading="loading"
      row-key="id"
      max-height="62vh"
      :totals="pageTotals"
      footer-label="Totales de la página"
      row-clickable
      empty-title="Sin pólizas"
      empty-description="Ajusta los filtros o registra la primera póliza de la empresa."
      @row-click="openDetail"
    >
      <template #cell-entry_date="{ row }">
        <span class="whitespace-nowrap text-xs text-slate-700">
          {{ formatDate(row.entry_date) }}
        </span>
      </template>

      <template #cell-folio="{ row }">
        <span class="font-mono text-[11px] font-medium text-slate-800">
          {{ row.folio }}
        </span>
      </template>

      <template #cell-entry_type="{ row }">
        <BaseBadge variant="info">
          {{ ENTRY_TYPE_LABELS[row.entry_type] || row.entry_type }}
        </BaseBadge>
      </template>

      <template #cell-concept="{ row }">
        <p class="max-w-[420px] truncate text-xs text-slate-800" :title="row.concept">
          {{ row.concept }}
        </p>
      </template>

      <template #cell-period_label="{ row }">
        <span class="text-[11px] tabular-nums text-slate-600">
          {{ row.period_label }}
        </span>
      </template>

      <template #cell-status="{ row }">
        <BaseBadge
          :variant="row.status === 'POSTED' ? 'success' : 'warning'"
          dot
        >
          {{ STATUS_LABELS[row.status] || row.status }}
        </BaseBadge>
      </template>

      <template #cell-total_debit="{ row }">
        <MoneyCell :value="row.total_debit" />
      </template>

      <template #cell-total_credit="{ row }">
        <MoneyCell :value="row.total_credit" />
      </template>

      <template #cell-actions="{ row }">
        <button
          type="button"
          class="inline-flex h-7 w-7 items-center justify-center rounded-md text-slate-500 transition-colors hover:bg-slate-100 hover:text-slate-700 focus:outline-none focus:ring-2 focus:ring-indigo-500"
          title="Ver detalle de la póliza"
          aria-label="Ver detalle de la póliza"
          @click.stop="openDetail(row)"
        >
          <Eye class="w-3.5 h-3.5" aria-hidden="true" />
        </button>
      </template>
    </DataTable>

    <PaginationBar
      :page="page"
      :page-size="PAGE_SIZE"
      :count="count"
      :loading="loading"
      @change="changePage"
    />

    <EntryDetailDrawer
      :entry="selectedEntry"
      :can-edit="canManage"
      :period-closed="selectedEntryClosed"
      @close="selectedEntry = null"
      @edit="editSelected"
    />
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import {
  AlertCircle,
  Lock,
  LockOpen,
  RefreshCw,
} from 'lucide-vue-next'

import {
  closePeriod,
  listAllEntries,
  listAllPeriods,
  reopenPeriod,
} from '../api/accounting'
import { listAllDocuments } from '../api/documents'
import ClosePeriodModal from '../components/periods/ClosePeriodModal.vue'
import ReopenPeriodModal from '../components/periods/ReopenPeriodModal.vue'
import BaseBadge from '../components/ui/BaseBadge.vue'
import BaseButton from '../components/ui/BaseButton.vue'
import DataTable from '../components/ui/DataTable.vue'
import { useActivePeriod } from '../composables/useActivePeriod'
import { mapPeriodApiError } from '../composables/useEntryErrors'
import { useRBAC } from '../composables/useRBAC'
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

const columns = [
  { key: 'period', label: 'Periodo', align: 'left', width: '190px' },
  { key: 'status', label: 'Estado', align: 'center', width: '120px' },
  { key: 'entries_count', label: 'Pólizas', align: 'right', width: '96px' },
  {
    key: 'unaccounted_documents_count',
    label: 'Docs. sin contabilizar',
    align: 'right',
    width: '160px',
  },
  { key: 'closed_at', label: 'Cierre', align: 'left', width: '160px' },
  { key: 'closed_by_name', label: 'Cerrado por', align: 'left' },
  { key: 'actions', label: 'Acciones', align: 'center', width: '180px' },
]

const { isPartner } = useRBAC()
const { setFromPeriod } = useActivePeriod()
const toast = useToast()

const periods = ref([])
const loading = ref(false)
const loadError = ref('')

const closeTarget = ref(null)
const closeDrafts = ref([])
const closeDocuments = ref([])
const closeLoading = ref(false)
const closeError = ref('')

const reopenTarget = ref(null)
const reopenLoading = ref(false)
const reopenError = ref('')

const closeModalOpen = computed({
  get: () => Boolean(closeTarget.value),
  set: (value) => {
    if (!value && !closeLoading.value) closeTarget.value = null
  },
})

const reopenModalOpen = computed({
  get: () => Boolean(reopenTarget.value),
  set: (value) => {
    if (!value && !reopenLoading.value) reopenTarget.value = null
  },
})

function periodLabel(period) {
  if (!period) return '—'
  return `${MONTHS[period.month - 1]} ${period.year}`
}

function formatDateTime(value) {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '—'
  return new Intl.DateTimeFormat('es-MX', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    timeZone: 'America/Mexico_City',
  }).format(date)
}

async function loadPeriods() {
  loading.value = true
  loadError.value = ''
  try {
    const { results } = await listAllPeriods()
    periods.value = [...results].sort(
      (left, right) =>
        right.year - left.year || right.month - left.month,
    )

    const now = new Date()
    const current =
      periods.value.find(
        (period) =>
          period.year === now.getFullYear() &&
          period.month === now.getMonth() + 1,
      ) || periods.value[0]
    setFromPeriod(current || null)
  } catch (error) {
    periods.value = []
    loadError.value =
      error?.message || 'No fue posible consultar los periodos fiscales.'
  } finally {
    loading.value = false
  }
}

async function openCloseModal(period) {
  closeTarget.value = period
  closeDrafts.value = []
  closeDocuments.value = []
  closeError.value = ''
  closeLoading.value = true
  try {
    const [draftsPayload, documentsPayload] = await Promise.all([
      listAllEntries({
        fiscal_period: period.id,
        status: 'DRAFT',
        page_size: 100,
      }),
      listAllDocuments({
        fiscal_period: period.id,
        is_accounted: 'false',
        page_size: 100,
      }),
    ])
    closeDrafts.value = draftsPayload.results
    closeDocuments.value = documentsPayload.results
  } catch (error) {
    closeError.value =
      error?.message || 'No fue posible cargar los pendientes del periodo.'
  } finally {
    closeLoading.value = false
  }
}

async function confirmClose() {
  if (!closeTarget.value) return
  closeLoading.value = true
  closeError.value = ''
  try {
    const updated = await closePeriod(closeTarget.value.id)
    toast.success(
      `Periodo ${periodLabel(closeTarget.value)} cerrado correctamente.`,
    )
    closeTarget.value = null
    setFromPeriod(updated)
    await loadPeriods()
  } catch (error) {
    const mapped = mapPeriodApiError(error)
    closeError.value = mapped.message
    toast.error(mapped.message, { title: 'No se pudo cerrar el periodo' })
  } finally {
    closeLoading.value = false
  }
}

function openReopenModal(period) {
  reopenTarget.value = period
  reopenError.value = ''
}

async function confirmReopen(justification) {
  if (!reopenTarget.value) return
  reopenLoading.value = true
  reopenError.value = ''
  try {
    const updated = await reopenPeriod(reopenTarget.value.id, justification)
    toast.success(
      `Periodo ${periodLabel(reopenTarget.value)} reabierto correctamente.`,
    )
    reopenTarget.value = null
    setFromPeriod(updated)
    await loadPeriods()
  } catch (error) {
    const mapped = mapPeriodApiError(error)
    reopenError.value = mapped.message
    toast.error(mapped.message, { title: 'No se pudo reabrir el periodo' })
  } finally {
    reopenLoading.value = false
  }
}

onMounted(loadPeriods)
</script>

<template>
  <section class="space-y-3">
    <header class="flex flex-wrap items-start justify-between gap-2">
      <div class="min-w-0">
        <h1 class="text-lg font-semibold tracking-tight text-slate-900">
          Periodos
        </h1>
        <p class="mt-1 max-w-2xl text-xs text-slate-600">
          Control de periodos fiscales mensuales, cierre y reapertura con
          justificación auditada.
        </p>
      </div>

      <div class="flex flex-wrap items-center gap-2">
        <BaseBadge v-if="!isPartner" variant="neutral" dot>
          Cierre y reapertura: solo socio
        </BaseBadge>
        <BaseButton
          variant="ghost"
          size="sm"
          :loading="loading"
          title="Actualizar periodos"
          @click="loadPeriods"
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

    <DataTable
      :columns="columns"
      :rows="periods"
      :loading="loading"
      row-key="id"
      max-height="66vh"
      empty-title="Sin periodos"
      empty-description="Los periodos fiscales se crean automáticamente al registrar pólizas o documentos."
    >
      <template #cell-period="{ row }">
        <div>
          <p class="text-xs font-semibold text-slate-900">{{ periodLabel(row) }}</p>
          <p class="text-[10px] tabular-nums text-slate-500">
            {{ row.year }}-{{ String(row.month).padStart(2, '0') }}
          </p>
        </div>
      </template>

      <template #cell-status="{ row }">
        <BaseBadge
          :variant="row.is_closed ? 'warning' : 'success'"
          dot
        >
          <template #icon>
            <component
              :is="row.is_closed ? Lock : LockOpen"
              class="w-3 h-3"
              aria-hidden="true"
            />
          </template>
          {{ row.is_closed ? 'Cerrado' : 'Abierto' }}
        </BaseBadge>
      </template>

      <template #cell-entries_count="{ row }">
        <span class="text-xs tabular-nums text-slate-700">
          {{ row.entries_count ?? 0 }}
        </span>
      </template>

      <template #cell-unaccounted_documents_count="{ row }">
        <BaseBadge
          :variant="Number(row.unaccounted_documents_count) ? 'warning' : 'success'"
        >
          {{ row.unaccounted_documents_count ?? 0 }}
        </BaseBadge>
      </template>

      <template #cell-closed_at="{ row }">
        <span class="whitespace-nowrap text-[11px] text-slate-600">
          {{ formatDateTime(row.closed_at) }}
        </span>
      </template>

      <template #cell-closed_by_name="{ row }">
        <span class="text-[11px] text-slate-600">
          {{ row.closed_by_name || '—' }}
        </span>
      </template>

      <template #cell-actions="{ row }">
        <div class="flex items-center justify-center">
          <BaseButton
            v-if="isPartner && !row.is_closed"
            variant="warning"
            size="sm"
            @click="openCloseModal(row)"
          >
            <template #icon>
              <Lock class="w-3.5 h-3.5" aria-hidden="true" />
            </template>
            Cerrar periodo
          </BaseButton>
          <BaseButton
            v-else-if="isPartner && row.is_closed"
            variant="secondary"
            size="sm"
            @click="openReopenModal(row)"
          >
            <template #icon>
              <LockOpen class="w-3.5 h-3.5" aria-hidden="true" />
            </template>
            Reabrir periodo
          </BaseButton>
          <span v-else class="text-[11px] text-slate-400">—</span>
        </div>
      </template>
    </DataTable>

    <ClosePeriodModal
      v-model="closeModalOpen"
      :period="closeTarget"
      :drafts="closeDrafts"
      :documents="closeDocuments"
      :loading="closeLoading"
      :error="closeError"
      @confirm="confirmClose"
    />

    <ReopenPeriodModal
      v-model="reopenModalOpen"
      :period="reopenTarget"
      :loading="reopenLoading"
      :error="reopenError"
      @confirm="confirmReopen"
    />
  </section>
</template>

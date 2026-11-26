<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  AlertCircle,
  ArrowLeft,
  Lock,
  Save,
  ShieldAlert,
} from 'lucide-vue-next'

import {
  createEntry,
  getEntry,
  listAllAccounts,
  listAllPeriods,
  updateEntry,
} from '../api/accounting'
import { listAllDocuments } from '../api/documents'
import BalanceIndicator from '../components/accounting/BalanceIndicator.vue'
import EntryLinesEditor from '../components/accounting/EntryLinesEditor.vue'
import BaseBadge from '../components/ui/BaseBadge.vue'
import BaseButton from '../components/ui/BaseButton.vue'
import { useActivePeriod } from '../composables/useActivePeriod'
import { useCurrency } from '../composables/useCurrency'
import {
  ENTRY_STATUS_OPTIONS,
  ENTRY_TYPE_OPTIONS,
  buildEntryPayload,
  createEntryLine,
  entryToLines,
  todayIsoDate,
  useEntryForm,
} from '../composables/useEntryForm'
import { mapEntryApiError } from '../composables/useEntryErrors'
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

const selectClass =
  'block h-8 w-full rounded-md border border-slate-300 bg-white px-2.5 text-xs text-slate-700 shadow-sm transition-colors focus:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-1 disabled:cursor-not-allowed disabled:bg-slate-50'

const route = useRoute()
const router = useRouter()
const toast = useToast()
const { can } = useRBAC()
const { formatMoney } = useCurrency()
const { setFromPeriod } = useActivePeriod()

const canManage = computed(() =>
  can([ROLES.PARTNER, ROLES.ACCOUNTANT]),
)

const entryId = computed(() => route.params.entryId)
const isEdit = computed(() => Boolean(entryId.value))

const form = reactive({
  entry_type: 'INCOME',
  entry_date: todayIsoDate(),
  concept: '',
  status: 'POSTED',
  fiscal_period: '',
})

const lines = ref([])
const periods = ref([])
const accounts = ref([])
const documents = ref([])
const documentStubs = ref([])
const loading = ref(false)
const saving = ref(false)
const loadError = ref('')
const errorMessages = ref([])
const formErrors = ref({})

const selectedPeriod = computed(() => {
  const byId = periods.value.find(
    (period) => String(period.id) === String(form.fiscal_period),
  )
  if (byId) return byId
  if (!form.entry_date) return null
  const [year, month] = form.entry_date.split('-').map(Number)
  return (
    periods.value.find(
      (period) => period.year === year && period.month === month,
    ) || null
  )
})

const periodClosed = computed(() => Boolean(selectedPeriod.value?.is_closed))
const readOnly = computed(() => periodClosed.value || !canManage.value)

const { debitTotal, creditTotal, difference, isBalanced, canSave } = useEntryForm({
  lines,
  readOnly,
})

const periodLabel = computed(() => {
  if (!selectedPeriod.value) return 'Sin periodo registrado'
  return `${MONTHS[selectedPeriod.value.month - 1]} ${selectedPeriod.value.year}`
})

function mergeDocuments(fetched) {
  const byId = new Map()
  fetched.forEach((document) => byId.set(String(document.id), document))
  documentStubs.value.forEach((document) => {
    if (!byId.has(String(document.id))) byId.set(String(document.id), document)
  })
  documents.value = Array.from(byId.values())
}

async function loadDocuments() {
  const period = selectedPeriod.value
  if (!period) {
    documents.value = [...documentStubs.value]
    return
  }
  try {
    const { results } = await listAllDocuments({
      fiscal_period: period.id,
      is_accounted: 'false',
      page_size: 100,
    })
    mergeDocuments(results)
  } catch {
    documents.value = [...documentStubs.value]
  }
}

function onDateChange() {
  if (!form.entry_date) {
    form.fiscal_period = ''
    loadDocuments()
    return
  }
  const [year, month] = form.entry_date.split('-').map(Number)
  const match = periods.value.find(
    (period) => period.year === year && period.month === month,
  )
  form.fiscal_period = match ? String(match.id) : ''
  loadDocuments()
}

function addLine(line) {
  lines.value = [...lines.value, line || createEntryLine()]
}

function removeLine(index) {
  lines.value = lines.value.filter((_line, lineIndex) => lineIndex !== index)
}

async function loadData() {
  loading.value = true
  loadError.value = ''
  try {
    const [periodPayload, accountsPayload] = await Promise.all([
      listAllPeriods(),
      listAllAccounts({ is_selectable: 'true', is_active: 'true' }),
    ])
    periods.value = [...periodPayload.results].sort(
      (left, right) =>
        right.year - left.year || right.month - left.month,
    )
    accounts.value = accountsPayload.results

    if (isEdit.value) {
      const entry = await getEntry(entryId.value)
      form.entry_type = entry.entry_type
      form.entry_date = entry.entry_date
      form.concept = entry.concept
      form.status = entry.status
      form.fiscal_period = String(entry.fiscal_period)
      lines.value = entryToLines(entry)
      documentStubs.value = (entry.items || [])
        .filter((item) => item.document)
        .map((item) => ({
          id: item.document,
          uuid: item.document_uuid,
          is_accounted: null,
          total: null,
          subtotal: null,
          iva_transferred: null,
        }))
    } else {
      lines.value = [createEntryLine(), createEntryLine()]
    }

    if (lines.value.length < 2) addLine()
  } catch (error) {
    loadError.value =
      error?.message || 'No fue posible cargar la información de la póliza.'
  } finally {
    loading.value = false
  }

  await loadDocuments()
}

async function save() {
  errorMessages.value = []
  formErrors.value = {}

  if (!canSave.value) {
    errorMessages.value = [
      'La póliza debe tener al menos dos renglones y estar cuadrada antes de guardar.',
    ]
    return
  }

  if (!form.concept.trim()) {
    formErrors.value = { concept: 'El concepto de la póliza es obligatorio.' }
    errorMessages.value = ['Captura el concepto de la póliza.']
    return
  }

  saving.value = true
  try {
    const payload = buildEntryPayload({
      entryType: form.entry_type,
      entryDate: form.entry_date,
      concept: form.concept,
      status: form.status,
      fiscalPeriod: form.fiscal_period,
      lines: lines.value,
    })

    if (isEdit.value) {
      await updateEntry(entryId.value, payload)
      toast.success('Póliza actualizada correctamente.')
    } else {
      await createEntry(payload)
      toast.success('Póliza registrada correctamente.')
    }

    router.push({ name: 'entries', params: { id: route.params.id } })
  } catch (error) {
    const mapped = mapEntryApiError(error)
    formErrors.value = mapped.fieldErrors
    errorMessages.value = mapped.messages
    toast.error(mapped.message || 'No fue posible guardar la póliza.', {
      title: 'Póliza no guardada',
    })
  } finally {
    saving.value = false
  }
}

function cancel() {
  router.push({ name: 'entries', params: { id: route.params.id } })
}

onMounted(async () => {
  await loadData()
  setFromPeriod(selectedPeriod.value)
})
</script>

<template>
  <section class="space-y-3">
    <header class="flex flex-wrap items-start justify-between gap-2">
      <div class="min-w-0">
        <button
          type="button"
          class="mb-1 inline-flex items-center gap-1 text-[11px] font-medium text-slate-500 transition-colors hover:text-slate-700 focus:outline-none focus:ring-2 focus:ring-indigo-500"
          @click="cancel"
        >
          <ArrowLeft class="w-3 h-3" aria-hidden="true" />
          Volver a pólizas
        </button>
        <h1 class="text-lg font-semibold tracking-tight text-slate-900">
          {{ isEdit ? 'Editar póliza' : 'Nueva póliza' }}
        </h1>
        <p class="mt-1 max-w-2xl text-xs text-slate-600">
          Registra cargos y abonos con validación estricta de partida doble.
        </p>
      </div>

      <div class="flex flex-wrap items-center gap-2">
        <BaseBadge v-if="periodClosed" variant="warning" dot>
          Periodo cerrado
        </BaseBadge>
        <BaseBadge v-else-if="!canManage" variant="neutral" dot>
          Solo lectura
        </BaseBadge>
        <BaseButton variant="secondary" :disabled="saving" @click="cancel">
          Cancelar
        </BaseButton>
        <BaseButton
          :disabled="!canSave"
          :loading="saving"
          @click="save"
        >
          <template #icon>
            <Save class="w-3.5 h-3.5" aria-hidden="true" />
          </template>
          Guardar póliza
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

    <div
      v-if="periodClosed"
      class="flex items-start gap-2 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-[11px] text-amber-900"
      role="status"
    >
      <Lock class="mt-0.5 w-3.5 h-3.5 shrink-0 text-amber-600" aria-hidden="true" />
      <p>
        El periodo <span class="font-semibold">{{ periodLabel }}</span> está
        cerrado. El formulario se muestra en solo lectura y no admite cambios.
      </p>
    </div>

    <div
      v-else-if="!canManage"
      class="flex items-start gap-2 rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-[11px] text-slate-700"
      role="status"
    >
      <ShieldAlert class="mt-0.5 w-3.5 h-3.5 shrink-0 text-slate-500" aria-hidden="true" />
      <p>Tu rol no permite crear ni modificar pólizas. La captura es de solo lectura.</p>
    </div>

    <div
      v-if="errorMessages.length"
      class="rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-[11px] text-rose-800"
      role="alert"
    >
      <div class="flex items-start gap-2">
        <AlertCircle class="mt-0.5 w-3.5 h-3.5 shrink-0" aria-hidden="true" />
        <ul class="list-inside list-disc space-y-0.5">
          <li v-for="message in errorMessages" :key="message">{{ message }}</li>
        </ul>
      </div>
    </div>

    <form class="space-y-3" @submit.prevent="save">
      <div class="rounded-lg border border-slate-200 bg-white p-3 shadow-sm">
        <div class="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
          <div>
            <label for="entry-type" class="mb-1 block text-[11px] font-medium text-slate-600">
              Tipo de póliza
            </label>
            <select
              id="entry-type"
              v-model="form.entry_type"
              :class="selectClass"
              :disabled="readOnly || saving"
            >
              <option
                v-for="option in ENTRY_TYPE_OPTIONS"
                :key="option.value"
                :value="option.value"
              >
                {{ option.label }}
              </option>
            </select>
            <p v-if="formErrors.entry_type" class="mt-1 text-[11px] text-rose-700">
              {{ formErrors.entry_type }}
            </p>
          </div>

          <div>
            <label for="entry-date" class="mb-1 block text-[11px] font-medium text-slate-600">
              Fecha de la póliza
            </label>
            <input
              id="entry-date"
              v-model="form.entry_date"
              type="date"
              :class="selectClass"
              :disabled="readOnly || saving"
              @change="onDateChange"
            />
            <p v-if="formErrors.entry_date" class="mt-1 text-[11px] text-rose-700">
              {{ formErrors.entry_date }}
            </p>
          </div>

          <div class="sm:col-span-2">
            <label for="entry-concept" class="mb-1 block text-[11px] font-medium text-slate-600">
              Concepto
            </label>
            <input
              id="entry-concept"
              v-model="form.concept"
              type="text"
              maxlength="500"
              placeholder="Describe el motivo de la póliza"
              :class="selectClass"
              :disabled="readOnly || saving"
            />
            <p v-if="formErrors.concept" class="mt-1 text-[11px] text-rose-700">
              {{ formErrors.concept }}
            </p>
          </div>

          <div>
            <label for="entry-status" class="mb-1 block text-[11px] font-medium text-slate-600">
              Estado
            </label>
            <select
              id="entry-status"
              v-model="form.status"
              :class="selectClass"
              :disabled="readOnly || saving"
            >
              <option
                v-for="option in ENTRY_STATUS_OPTIONS"
                :key="option.value"
                :value="option.value"
              >
                {{ option.label }}
              </option>
            </select>
          </div>

          <div class="sm:col-span-2 lg:col-span-3">
            <p class="mb-1 text-[11px] font-medium text-slate-600">Periodo fiscal</p>
            <div class="flex h-8 flex-wrap items-center gap-2 text-xs text-slate-700">
              <span class="font-medium">{{ periodLabel }}</span>
              <BaseBadge
                :variant="periodClosed ? 'warning' : 'success'"
                dot
              >
                {{ periodClosed ? 'Cerrado' : 'Abierto' }}
              </BaseBadge>
              <span v-if="!selectedPeriod" class="text-[11px] text-slate-500">
                Se creará automáticamente al guardar.
              </span>
            </div>
            <p v-if="formErrors.fiscal_period" class="mt-1 text-[11px] text-rose-700">
              {{ formErrors.fiscal_period }}
            </p>
          </div>
        </div>
      </div>

      <EntryLinesEditor
        v-model="lines"
        :accounts="accounts"
        :documents="documents"
        :read-only="readOnly || saving"
        @add="addLine"
        @remove="removeLine"
      />

      <div class="rounded-lg border border-slate-200 bg-white p-3 shadow-sm">
        <div class="grid gap-2 sm:grid-cols-3">
          <div class="rounded-md border border-slate-200 bg-slate-50 px-3 py-2">
            <p class="text-[10px] font-semibold uppercase tracking-wider text-slate-500">
              Total cargos
            </p>
            <p class="mt-0.5 text-right text-sm font-semibold tabular-nums text-slate-900">
              {{ formatMoney(debitTotal) }}
            </p>
          </div>
          <div class="rounded-md border border-slate-200 bg-slate-50 px-3 py-2">
            <p class="text-[10px] font-semibold uppercase tracking-wider text-slate-500">
              Total abonos
            </p>
            <p class="mt-0.5 text-right text-sm font-semibold tabular-nums text-slate-900">
              {{ formatMoney(creditTotal) }}
            </p>
          </div>
          <div class="flex items-center justify-end rounded-md border border-slate-200 bg-slate-50 px-3 py-2 sm:flex-col sm:items-end sm:justify-center">
            <BalanceIndicator :difference="difference" :balanced="isBalanced" />
          </div>
        </div>

        <p v-if="lines.length < 2" class="mt-2 text-[11px] text-rose-700">
          Agrega al menos dos renglones para poder guardar la póliza.
        </p>
        <p v-else-if="!isBalanced" class="mt-2 text-[11px] text-rose-700">
          El botón Guardar se habilitará cuando los cargos y abonos sean iguales.
        </p>

        <div class="mt-3 flex justify-end gap-2">
          <BaseButton variant="secondary" :disabled="saving" @click="cancel">
            Cancelar
          </BaseButton>
          <BaseButton :disabled="!canSave" :loading="saving" @click="save">
            <template #icon>
              <Save class="w-3.5 h-3.5" aria-hidden="true" />
            </template>
            Guardar póliza
          </BaseButton>
        </div>
      </div>
    </form>

    <p v-if="loading" class="text-[11px] text-slate-500">
      Cargando catálogo, periodos y documentos…
    </p>
  </section>
</template>

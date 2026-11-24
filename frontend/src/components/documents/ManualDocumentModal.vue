<script setup>
import { computed, nextTick, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { AlertCircle, FilePlus2, FileText, UploadCloud, X } from 'lucide-vue-next'

import { createManualDocument } from '../../api/documents'
import { useCurrency } from '../../composables/useCurrency'
import { useToast } from '../../composables/useToast'
import { formatFileSize, validateDocumentFile } from '../../utils/documentFiles'
import BaseButton from '../ui/BaseButton.vue'
import BaseInput from '../ui/BaseInput.vue'

const props = defineProps({
  modelValue: Boolean,
})

const emit = defineEmits(['update:modelValue', 'saved'])

const { sum, toFixed } = useCurrency()
const toast = useToast()

const RFC_PATTERN = /^[A-ZÑ&]{3,4}\d{6}[A-Z0-9]{3}$/i
const MONEY_PATTERN = /^\d+(\.\d{1,2})?$/

const pdfInput = ref(null)
const submitting = ref(false)
const generalError = ref('')
const fieldErrors = ref({})
const totalTouched = ref(false)
const form = reactive({
  pdf_file: null,
  issue_date: '',
  direction: 'RECEIVED',
  issuer_rfc: '',
  issuer_name: '',
  subtotal: '',
  iva_transferred: '',
  total: '',
  series: '',
  folio: '',
  payment_method: '',
})

const selectClass =
  'block h-8 w-full rounded-md border border-slate-300 bg-white px-2.5 text-xs text-slate-700 shadow-sm transition-colors focus:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-1 disabled:cursor-not-allowed disabled:bg-slate-50'

const pdfName = computed(() => form.pdf_file?.name || '')

function localToday() {
  const now = new Date()
  const local = new Date(now.getTime() - now.getTimezoneOffset() * 60000)
  return local.toISOString().slice(0, 10)
}

function resetForm() {
  form.pdf_file = null
  form.issue_date = localToday()
  form.direction = 'RECEIVED'
  form.issuer_rfc = ''
  form.issuer_name = ''
  form.subtotal = ''
  form.iva_transferred = ''
  form.total = ''
  form.series = ''
  form.folio = ''
  form.payment_method = ''
  totalTouched.value = false
  fieldErrors.value = {}
  generalError.value = ''
  submitting.value = false
}

function close(force = false) {
  if (submitting.value && !force) return
  emit('update:modelValue', false)
}

function selectPdf() {
  if (submitting.value) return
  pdfInput.value?.click()
}

function onPdfChange(event) {
  const file = event.target?.files?.[0]
  event.target.value = ''
  if (!file) return

  const validation = validateDocumentFile(file)
  if (!validation.valid) {
    form.pdf_file = null
    fieldErrors.value = {
      ...fieldErrors.value,
      pdf_file: validation.message,
    }
    return
  }

  form.pdf_file = file
  const nextErrors = { ...fieldErrors.value }
  delete nextErrors.pdf_file
  fieldErrors.value = nextErrors
}

function syncTotal() {
  if (totalTouched.value) return
  const hasSubtotal = String(form.subtotal).trim() !== ''
  const hasIva = String(form.iva_transferred).trim() !== ''
  if (!hasSubtotal && !hasIva) {
    form.total = ''
    return
  }
  form.total = sum([form.subtotal || 0, form.iva_transferred || 0])
}

function onTotalChange(value) {
  totalTouched.value = true
  form.total = value
}

function isMoney(value) {
  return MONEY_PATTERN.test(String(value || '').trim())
}

function validate() {
  const errors = {}

  if (!form.pdf_file) {
    errors.pdf_file = 'El comprobante manual requiere un archivo PDF.'
  } else {
    const validation = validateDocumentFile(form.pdf_file)
    if (!validation.valid) errors.pdf_file = validation.message
  }

  if (!form.issue_date) {
    errors.issue_date = 'La fecha de emisión es obligatoria.'
  }
  if (!form.direction) {
    errors.direction = 'Selecciona la dirección del comprobante.'
  }

  const rfc = form.issuer_rfc.trim().toUpperCase()
  if (!rfc) {
    errors.issuer_rfc = 'El RFC del emisor es obligatorio.'
  } else if (!RFC_PATTERN.test(rfc)) {
    errors.issuer_rfc = 'El RFC no tiene un formato válido.'
  }

  if (!form.issuer_name.trim()) {
    errors.issuer_name = 'La razón social del emisor es obligatoria.'
  }

  if (!isMoney(form.subtotal)) {
    errors.subtotal = 'Captura un subtotal válido con hasta dos decimales.'
  }
  if (!isMoney(form.iva_transferred)) {
    errors.iva_transferred = 'Captura un IVA trasladado válido.'
  }
  if (!isMoney(form.total)) {
    errors.total = 'Captura un total válido con hasta dos decimales.'
  }

  fieldErrors.value = errors
  return Object.keys(errors).length === 0
}

async function submit() {
  if (submitting.value) return
  generalError.value = ''
  if (!validate()) return

  submitting.value = true
  try {
    const document = await createManualDocument({
      pdf_file: form.pdf_file,
      issue_date: `${form.issue_date}T12:00:00-06:00`,
      direction: form.direction,
      issuer_rfc: form.issuer_rfc.trim().toUpperCase(),
      issuer_name: form.issuer_name.trim(),
      subtotal: toFixed(form.subtotal, 2),
      iva_transferred: toFixed(form.iva_transferred, 2),
      total: toFixed(form.total, 2),
      series: form.series.trim(),
      folio: form.folio.trim(),
      payment_method: form.payment_method,
    })

    toast.success('Comprobante manual registrado correctamente.')
    emit('saved', document)
    close(true)
  } catch (error) {
    generalError.value =
      error?.message || 'No fue posible registrar el comprobante manual.'
    fieldErrors.value = error?.fieldErrors || {}
  } finally {
    submitting.value = false
  }
}

function handleKeydown(event) {
  if (!props.modelValue) return
  if (event.key === 'Escape' && !submitting.value) close()
}

watch(
  () => [form.subtotal, form.iva_transferred],
  () => syncTotal(),
)

watch(
  () => props.modelValue,
  async (open) => {
    if (typeof document !== 'undefined') {
      document.body.style.overflow = open ? 'hidden' : ''
      if (open) {
        resetForm()
        document.addEventListener('keydown', handleKeydown)
        await nextTick()
      } else {
        document.removeEventListener('keydown', handleKeydown)
      }
    }
  },
  { immediate: true },
)

onBeforeUnmount(() => {
  if (typeof document !== 'undefined') {
    document.body.style.overflow = ''
    document.removeEventListener('keydown', handleKeydown)
  }
})
</script>

<template>
  <Teleport to="body">
    <Transition
      enter-active-class="transition duration-150 ease-out"
      enter-from-class="opacity-0"
      enter-to-class="opacity-100"
      leave-active-class="transition duration-100 ease-in"
      leave-from-class="opacity-100"
      leave-to-class="opacity-0"
    >
      <div
        v-if="modelValue"
        class="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4 backdrop-blur-[1px]"
        role="presentation"
        @click.self="!submitting && close()"
      >
        <div
          class="flex max-h-[calc(100vh-2rem)] w-full max-w-2xl flex-col overflow-hidden rounded-lg border border-slate-200 bg-white shadow-xl"
          role="dialog"
          aria-modal="true"
          aria-labelledby="manual-document-title"
        >
          <header class="flex items-start gap-3 border-b border-slate-200 px-4 py-3">
            <div
              class="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-indigo-100 text-indigo-700"
            >
              <FilePlus2 class="w-4 h-4" aria-hidden="true" />
            </div>
            <div class="min-w-0 flex-1">
              <h2
                id="manual-document-title"
                class="text-sm font-semibold text-slate-900"
              >
                Registrar comprobante manual
              </h2>
              <p class="mt-0.5 text-[11px] text-slate-500">
                Para comprobantes sin XML. El PDF de respaldo es obligatorio y se
                registra como tipo M.
              </p>
            </div>
            <button
              type="button"
              class="rounded-md p-1 text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-600 focus:outline-none focus:ring-2 focus:ring-indigo-500"
              aria-label="Cerrar"
              :disabled="submitting"
              @click="close"
            >
              <X class="w-4 h-4" aria-hidden="true" />
            </button>
          </header>

          <div class="min-h-0 flex-1 overflow-y-auto px-4 py-3">
            <div
              v-if="generalError"
              class="mb-3 flex items-start gap-2 rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-[11px] text-rose-800"
              role="alert"
            >
              <AlertCircle class="mt-0.5 w-3.5 h-3.5 shrink-0" aria-hidden="true" />
              <p>{{ generalError }}</p>
            </div>

            <form class="space-y-3" @submit.prevent="submit">
              <div>
                <span class="mb-1 block text-xs font-medium text-slate-700">
                  PDF de respaldo
                  <span class="text-rose-600" aria-hidden="true">*</span>
                </span>
                <div
                  class="flex flex-wrap items-center gap-2 rounded-md border border-dashed border-slate-300 bg-slate-50/60 px-3 py-2.5"
                  :class="fieldErrors.pdf_file ? 'border-rose-300 bg-rose-50/40' : ''"
                >
                  <div
                    class="flex h-8 w-8 items-center justify-center rounded-md bg-white text-rose-500 shadow-sm"
                  >
                    <FileText v-if="pdfName" class="w-4 h-4" aria-hidden="true" />
                    <UploadCloud v-else class="w-4 h-4" aria-hidden="true" />
                  </div>
                  <div class="min-w-0 flex-1">
                    <p
                      v-if="pdfName"
                      class="truncate text-xs font-medium text-slate-800"
                      :title="pdfName"
                    >
                      {{ pdfName }}
                    </p>
                    <p v-else class="text-xs text-slate-600">
                      Selecciona el PDF que respalda el comprobante.
                    </p>
                    <p class="text-[10px] text-slate-500">
                      PDF ≤ 5 MB · obligatorio
                      <span v-if="pdfName">
                        · {{ formatFileSize(form.pdf_file?.size) }}
                      </span>
                    </p>
                  </div>
                  <BaseButton
                    variant="secondary"
                    size="sm"
                    :disabled="submitting"
                    @click="selectPdf"
                  >
                    {{ pdfName ? 'Cambiar PDF' : 'Seleccionar PDF' }}
                  </BaseButton>
                  <input
                    ref="pdfInput"
                    type="file"
                    class="hidden"
                    accept=".pdf,application/pdf"
                    :disabled="submitting"
                    @change="onPdfChange"
                  />
                </div>
                <p
                  v-if="fieldErrors.pdf_file"
                  class="mt-1 text-[11px] text-rose-700"
                >
                  {{ fieldErrors.pdf_file }}
                </p>
              </div>

              <div class="grid gap-3 sm:grid-cols-2">
                <BaseInput
                  v-model="form.issue_date"
                  label="Fecha de emisión"
                  type="date"
                  required
                  :error="fieldErrors.issue_date"
                />

                <div>
                  <label
                    for="manual-direction"
                    class="mb-1 block text-xs font-medium text-slate-700"
                  >
                    Dirección
                    <span class="text-rose-600" aria-hidden="true">*</span>
                  </label>
                  <select
                    id="manual-direction"
                    v-model="form.direction"
                    :class="selectClass"
                    :disabled="submitting"
                  >
                    <option value="RECEIVED">Recibido (gasto / compra)</option>
                    <option value="ISSUED">Emitido (ingreso / venta)</option>
                  </select>
                  <p
                    v-if="fieldErrors.direction"
                    class="mt-1 text-[11px] text-rose-700"
                  >
                    {{ fieldErrors.direction }}
                  </p>
                </div>

                <BaseInput
                  v-model="form.issuer_rfc"
                  label="RFC del emisor"
                  placeholder="XAXX010101000"
                  required
                  maxlength="13"
                  :error="fieldErrors.issuer_rfc"
                  input-class="font-mono uppercase"
                />

                <BaseInput
                  v-model="form.issuer_name"
                  label="Razón social del emisor"
                  placeholder="Proveedor sin CFDI"
                  required
                  :error="fieldErrors.issuer_name"
                />

                <BaseInput
                  v-model="form.subtotal"
                  label="Subtotal"
                  type="text"
                  inputmode="decimal"
                  placeholder="0.00"
                  required
                  :error="fieldErrors.subtotal"
                />

                <BaseInput
                  v-model="form.iva_transferred"
                  label="IVA trasladado"
                  type="text"
                  inputmode="decimal"
                  placeholder="0.00"
                  required
                  :error="fieldErrors.iva_transferred"
                />

                <BaseInput
                  :model-value="form.total"
                  label="Total"
                  type="text"
                  inputmode="decimal"
                  placeholder="0.00"
                  required
                  :error="fieldErrors.total"
                  @update:model-value="onTotalChange"
                />

                <BaseInput
                  v-model="form.payment_method"
                  label="Método de pago (opcional)"
                  placeholder="PUE o PPD"
                  maxlength="5"
                />

                <BaseInput
                  v-model="form.series"
                  label="Serie (opcional)"
                  maxlength="25"
                />

                <BaseInput
                  v-model="form.folio"
                  label="Folio (opcional)"
                  maxlength="40"
                />
              </div>
            </form>
          </div>

          <footer
            class="flex justify-end gap-2 border-t border-slate-200 bg-slate-50 px-4 py-2.5"
          >
            <BaseButton
              variant="secondary"
              :disabled="submitting"
              @click="close"
            >
              Cancelar
            </BaseButton>
            <BaseButton :loading="submitting" @click="submit">
              Registrar comprobante
            </BaseButton>
          </footer>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

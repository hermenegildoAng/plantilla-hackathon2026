<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { AlertCircle, AlertTriangle, X } from 'lucide-vue-next'

import BaseButton from '../ui/BaseButton.vue'

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

const MIN_LENGTH = 15

const props = defineProps({
  modelValue: Boolean,
  period: {
    type: Object,
    default: null,
  },
  loading: Boolean,
  error: {
    type: String,
    default: '',
  },
})

const emit = defineEmits(['update:modelValue', 'confirm'])

const justification = ref('')

const periodLabel = computed(() => {
  if (!props.period) return ''
  return `${MONTHS[props.period.month - 1]} ${props.period.year}`
})

const length = computed(() => justification.value.trim().length)
const canConfirm = computed(
  () => Boolean(props.period) && length.value >= MIN_LENGTH && !props.loading,
)

function close() {
  if (props.loading) return
  emit('update:modelValue', false)
}

function confirm() {
  if (!canConfirm.value) return
  emit('confirm', justification.value.trim())
}

function handleKeydown(event) {
  if (!props.modelValue) return
  if (event.key === 'Escape') close()
}

watch(
  () => props.modelValue,
  (open) => {
    if (typeof document === 'undefined') return
    if (open) {
      justification.value = ''
      document.body.style.overflow = 'hidden'
      document.addEventListener('keydown', handleKeydown)
    } else {
      document.body.style.overflow = ''
      document.removeEventListener('keydown', handleKeydown)
    }
  },
  { immediate: true },
)

onBeforeUnmount(() => {
  if (typeof document === 'undefined') return
  document.body.style.overflow = ''
  document.removeEventListener('keydown', handleKeydown)
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
        @click.self="close"
      >
        <div
          class="w-full max-w-md overflow-hidden rounded-lg border border-slate-200 bg-white shadow-xl"
          role="dialog"
          aria-modal="true"
          aria-labelledby="reopen-period-title"
        >
          <div class="flex items-start gap-3 px-4 py-4">
            <div class="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-amber-100 text-amber-700">
              <AlertTriangle class="w-4 h-4" aria-hidden="true" />
            </div>

            <div class="min-w-0 flex-1">
              <h2 id="reopen-period-title" class="text-sm font-semibold text-slate-900">
                Reabrir periodo fiscal
              </h2>
              <div class="mt-1 text-xs leading-relaxed text-slate-600">
                <p>
                  Vas a reabrir el periodo
                  <strong class="font-semibold text-slate-900">{{ periodLabel }}</strong>.
                  La acción quedará registrada en la bitácora de auditoría con tu
                  justificación.
                </p>

                <label for="reopen-justification" class="mt-2 block text-[11px] font-medium text-slate-700">
                  Justificación
                  <span class="text-rose-600" aria-hidden="true">*</span>
                </label>
                <textarea
                  id="reopen-justification"
                  v-model="justification"
                  rows="3"
                  maxlength="500"
                  class="mt-1 block w-full rounded-md border border-slate-300 bg-white px-2.5 py-1.5 text-xs text-slate-700 shadow-sm placeholder:text-slate-400 focus:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-1"
                  placeholder="Describe el motivo de la reapertura contable…"
                  :disabled="loading"
                  :aria-invalid="length > 0 && length < MIN_LENGTH ? 'true' : undefined"
                />
                <div class="mt-1 flex items-center justify-between gap-2">
                  <p
                    class="text-[11px]"
                    :class="length > 0 && length < MIN_LENGTH ? 'text-rose-700' : 'text-slate-500'"
                  >
                    Mínimo {{ MIN_LENGTH }} caracteres.
                  </p>
                  <p
                    class="text-[11px] tabular-nums"
                    :class="length >= MIN_LENGTH ? 'text-emerald-700' : 'text-slate-500'"
                    data-testid="justification-counter"
                  >
                    {{ length }} / {{ MIN_LENGTH }} caracteres
                  </p>
                </div>

                <div v-if="error" class="mt-2 flex items-start gap-1.5 rounded-md border border-rose-200 bg-rose-50 px-2 py-1.5 text-[11px] text-rose-800" role="alert">
                  <AlertCircle class="mt-0.5 w-3.5 h-3.5 shrink-0" aria-hidden="true" />
                  <p>{{ error }}</p>
                </div>
              </div>
            </div>

            <button
              type="button"
              class="rounded-md p-1 text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-600 focus:outline-none focus:ring-2 focus:ring-indigo-500"
              aria-label="Cerrar"
              :disabled="loading"
              @click="close"
            >
              <X class="w-4 h-4" aria-hidden="true" />
            </button>
          </div>

          <div class="flex justify-end gap-2 border-t border-slate-200 bg-slate-50 px-4 py-2.5">
            <BaseButton variant="secondary" :disabled="loading" @click="close">
              Cancelar
            </BaseButton>
            <BaseButton
              variant="warning"
              :disabled="!canConfirm"
              :loading="loading"
              @click="confirm"
            >
              Confirmar reapertura
            </BaseButton>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

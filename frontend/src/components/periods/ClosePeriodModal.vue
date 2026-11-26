<script setup>
import { computed, onBeforeUnmount, watch } from 'vue'
import { AlertCircle, AlertTriangle, FileText, Lock, X } from 'lucide-vue-next'

import BaseBadge from '../ui/BaseBadge.vue'
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

const props = defineProps({
  modelValue: Boolean,
  period: {
    type: Object,
    default: null,
  },
  drafts: {
    type: Array,
    default: () => [],
  },
  documents: {
    type: Array,
    default: () => [],
  },
  loading: Boolean,
  error: {
    type: String,
    default: '',
  },
})

const emit = defineEmits(['update:modelValue', 'confirm'])

const periodLabel = computed(() => {
  if (!props.period) return ''
  return `${MONTHS[props.period.month - 1]} ${props.period.year}`
})

const canConfirm = computed(
  () => Boolean(props.period) && props.drafts.length === 0 && !props.loading,
)

function close() {
  if (props.loading) return
  emit('update:modelValue', false)
}

function confirm() {
  if (!canConfirm.value) return
  emit('confirm')
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
          aria-labelledby="close-period-title"
        >
          <div class="flex items-start gap-3 px-4 py-4">
            <div class="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-amber-100 text-amber-700">
              <Lock class="w-4 h-4" aria-hidden="true" />
            </div>

            <div class="min-w-0 flex-1">
              <h2 id="close-period-title" class="text-sm font-semibold text-slate-900">
                Cerrar periodo fiscal
              </h2>
              <div class="mt-1 text-xs leading-relaxed text-slate-600">
                <p>
                  Se cerrará el periodo
                  <strong class="font-semibold text-slate-900">{{ periodLabel }}</strong>.
                  Después del cierre, las pólizas y documentos del mes quedarán
                  bloqueados para edición.
                </p>

                <div class="mt-2 space-y-1.5">
                  <div class="flex items-center justify-between rounded border border-slate-200 bg-slate-50 px-2 py-1.5">
                    <span>Pólizas en el periodo</span>
                    <span class="font-semibold tabular-nums text-slate-800">
                      {{ period?.entries_count ?? 0 }}
                    </span>
                  </div>
                  <div class="flex items-center justify-between rounded border border-slate-200 bg-slate-50 px-2 py-1.5">
                    <span>Pólizas en borrador</span>
                    <BaseBadge :variant="drafts.length ? 'danger' : 'success'" dot>
                      {{ drafts.length }}
                    </BaseBadge>
                  </div>
                  <div class="flex items-center justify-between rounded border border-slate-200 bg-slate-50 px-2 py-1.5">
                    <span>Documentos sin contabilizar</span>
                    <BaseBadge :variant="documents.length ? 'warning' : 'success'" dot>
                      {{ documents.length }}
                    </BaseBadge>
                  </div>
                </div>

                <div v-if="drafts.length" class="mt-2 rounded-md border border-rose-200 bg-rose-50 px-2 py-1.5 text-[11px] text-rose-800">
                  <p class="flex items-center gap-1 font-semibold">
                    <AlertTriangle class="w-3.5 h-3.5" aria-hidden="true" />
                    Concluye o elimina las pólizas en borrador antes de cerrar.
                  </p>
                  <ul class="mt-1 list-inside list-disc space-y-0.5">
                    <li v-for="draft in drafts" :key="draft.id">
                      <span class="font-mono">{{ draft.folio }}</span>
                      · {{ draft.concept }}
                    </li>
                  </ul>
                </div>

                <div v-if="documents.length" class="mt-2 rounded-md border border-amber-200 bg-amber-50 px-2 py-1.5 text-[11px] text-amber-900">
                  <p class="flex items-center gap-1 font-semibold">
                    <FileText class="w-3.5 h-3.5" aria-hidden="true" />
                    Documentos pendientes de contabilizar (no bloquean el cierre).
                  </p>
                  <p class="mt-0.5 text-amber-800">
                    {{ documents.length }} comprobante{{ documents.length === 1 ? '' : 's' }}
                    quedarán sin póliza asociada.
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
              Confirmar cierre
            </BaseButton>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

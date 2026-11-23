<script setup>
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { AlertTriangle, Info, X } from 'lucide-vue-next'

import BaseButton from './BaseButton.vue'

const props = defineProps({
  modelValue: Boolean,
  title: {
    type: String,
    default: 'Confirmar operación',
  },
  message: {
    type: String,
    default: '',
  },
  confirmText: {
    type: String,
    default: 'Confirmar',
  },
  cancelText: {
    type: String,
    default: 'Cancelar',
  },
  variant: {
    type: String,
    default: 'warning',
    validator: (value) => ['warning', 'danger', 'primary'].includes(value),
  },
  loading: Boolean,
})

const emit = defineEmits(['update:modelValue', 'confirm', 'cancel'])

const confirmButton = ref(null)

const ICON_STYLES = {
  warning: 'bg-amber-100 text-amber-700',
  danger: 'bg-rose-100 text-rose-700',
  primary: 'bg-indigo-100 text-indigo-700',
}

const BUTTON_VARIANTS = {
  warning: 'warning',
  danger: 'danger',
  primary: 'primary',
}

const iconStyle = computed(() => ICON_STYLES[props.variant] || ICON_STYLES.warning)
const confirmVariant = computed(() => BUTTON_VARIANTS[props.variant] || 'warning')
const Icon = computed(() => (props.variant === 'primary' ? Info : AlertTriangle))

function close() {
  emit('update:modelValue', false)
  emit('cancel')
}

function confirm() {
  if (props.loading) return
  emit('confirm')
}

function handleKeydown(event) {
  if (!props.modelValue) return
  if (event.key === 'Escape' && !props.loading) close()
}

watch(
  () => props.modelValue,
  async (open) => {
    if (typeof document !== 'undefined') {
      document.body.style.overflow = open ? 'hidden' : ''
      if (open) {
        document.addEventListener('keydown', handleKeydown)
        await nextTick()
        confirmButton.value?.$el?.focus?.()
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
        @click.self="!loading && close()"
      >
        <div
          class="w-full max-w-md overflow-hidden rounded-lg border border-slate-200 bg-white shadow-xl"
          role="dialog"
          aria-modal="true"
          aria-labelledby="confirm-modal-title"
          aria-describedby="confirm-modal-description"
        >
          <div class="flex items-start gap-3 px-4 py-4">
            <div
              class="flex h-9 w-9 shrink-0 items-center justify-center rounded-full"
              :class="iconStyle"
            >
              <component :is="Icon" class="w-4 h-4" aria-hidden="true" />
            </div>

            <div class="min-w-0 flex-1">
              <h2
                id="confirm-modal-title"
                class="text-sm font-semibold text-slate-900"
              >
                {{ title }}
              </h2>
              <div
                id="confirm-modal-description"
                class="mt-1 text-xs leading-relaxed text-slate-600"
              >
                <slot>{{ message }}</slot>
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

          <div
            class="flex justify-end gap-2 border-t border-slate-200 bg-slate-50 px-4 py-2.5"
          >
            <BaseButton variant="secondary" :disabled="loading" @click="close">
              {{ cancelText }}
            </BaseButton>
            <BaseButton
              ref="confirmButton"
              :variant="confirmVariant"
              :loading="loading"
              @click="confirm"
            >
              {{ confirmText }}
            </BaseButton>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

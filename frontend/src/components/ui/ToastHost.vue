<script setup>
import { computed } from 'vue'
import { AlertTriangle, CheckCircle2, Info, X, XCircle } from 'lucide-vue-next'

import { useToast } from '../../composables/useToast'

const { toasts, removeToast } = useToast()

const ICONS = {
  success: CheckCircle2,
  error: XCircle,
  warning: AlertTriangle,
  info: Info,
}

const TONES = {
  success: 'text-emerald-600 bg-emerald-50 border-emerald-200',
  error: 'text-rose-600 bg-rose-50 border-rose-200',
  warning: 'text-amber-600 bg-amber-50 border-amber-300',
  info: 'text-sky-600 bg-sky-50 border-sky-200',
}

const BORDERS = {
  success: 'border-l-emerald-500',
  error: 'border-l-rose-500',
  warning: 'border-l-amber-500',
  info: 'border-l-sky-500',
}

function iconFor(type) {
  return ICONS[type] || Info
}

const hasToasts = computed(() => toasts.length > 0)
</script>

<template>
  <div
    v-if="hasToasts"
    class="pointer-events-none fixed right-4 top-4 z-[70] flex w-80 max-w-[calc(100vw-2rem)] flex-col gap-2"
    aria-live="polite"
    aria-atomic="false"
  >
    <TransitionGroup
      enter-active-class="transition duration-200 ease-out"
      enter-from-class="opacity-0 translate-y-1"
      enter-to-class="opacity-100 translate-y-0"
      leave-active-class="transition duration-150 ease-in"
      leave-from-class="opacity-100"
      leave-to-class="opacity-0"
    >
      <div
        v-for="toast in toasts"
        :key="toast.id"
        class="pointer-events-auto flex items-start gap-2.5 rounded-lg border border-l-4 border-slate-200 bg-white p-3 shadow-lg"
        :class="BORDERS[toast.type] || BORDERS.info"
        role="status"
      >
        <div
          class="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full border"
          :class="TONES[toast.type] || TONES.info"
        >
          <component
            :is="iconFor(toast.type)"
            class="w-3.5 h-3.5"
            aria-hidden="true"
          />
        </div>

        <div class="min-w-0 flex-1">
          <p class="text-xs font-semibold text-slate-900">{{ toast.title }}</p>
          <p v-if="toast.message" class="mt-0.5 text-xs leading-relaxed text-slate-600">
            {{ toast.message }}
          </p>
        </div>

        <button
          type="button"
          class="rounded-md p-1 text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-600 focus:outline-none focus:ring-2 focus:ring-indigo-500"
          aria-label="Cerrar notificación"
          @click="removeToast(toast.id)"
        >
          <X class="w-3.5 h-3.5" aria-hidden="true" />
        </button>
      </div>
    </TransitionGroup>
  </div>
</template>

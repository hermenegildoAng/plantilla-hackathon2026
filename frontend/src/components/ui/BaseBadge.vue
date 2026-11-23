<script setup>
import { computed } from 'vue'

const props = defineProps({
  variant: {
    type: String,
    default: 'neutral',
    validator: (value) =>
      ['success', 'danger', 'warning', 'info', 'neutral', 'brand'].includes(value),
  },
  dot: Boolean,
})

const VARIANT_CLASSES = {
  success: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  danger: 'bg-rose-50 text-rose-700 border-rose-200',
  warning: 'bg-amber-50 text-amber-800 border-amber-300',
  info: 'bg-sky-50 text-sky-700 border-sky-200',
  neutral: 'bg-slate-100 text-slate-700 border-slate-200',
  brand: 'bg-indigo-50 text-indigo-700 border-indigo-200',
}

const DOT_CLASSES = {
  success: 'bg-emerald-600',
  danger: 'bg-rose-600',
  warning: 'bg-amber-600',
  info: 'bg-sky-600',
  neutral: 'bg-slate-500',
  brand: 'bg-indigo-600',
}

const classes = computed(() => [
  'inline-flex items-center gap-1 rounded-md border px-1.5 py-0.5 text-[11px] font-medium whitespace-nowrap',
  VARIANT_CLASSES[props.variant],
])
</script>

<template>
  <span :class="classes">
    <span
      v-if="dot"
      class="h-1.5 w-1.5 rounded-full"
      :class="DOT_CLASSES[variant]"
      aria-hidden="true"
    />
    <slot name="icon" />
    <slot />
  </span>
</template>

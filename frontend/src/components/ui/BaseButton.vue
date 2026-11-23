<script setup>
import { computed } from 'vue'
import { Loader2 } from 'lucide-vue-next'

const props = defineProps({
  variant: {
    type: String,
    default: 'primary',
    validator: (value) =>
      ['primary', 'secondary', 'danger', 'warning', 'ghost', 'subtle'].includes(value),
  },
  size: {
    type: String,
    default: 'md',
    validator: (value) => ['sm', 'md'].includes(value),
  },
  type: {
    type: String,
    default: 'button',
  },
  disabled: Boolean,
  loading: Boolean,
  block: Boolean,
})

const emit = defineEmits(['click'])

const VARIANT_CLASSES = {
  primary:
    'bg-indigo-600 text-white border border-transparent hover:bg-indigo-700 focus-visible:ring-indigo-500',
  secondary:
    'bg-white text-slate-700 border border-slate-300 hover:bg-slate-50 focus-visible:ring-indigo-500',
  danger:
    'bg-rose-600 text-white border border-transparent hover:bg-rose-700 focus-visible:ring-rose-500',
  warning:
    'bg-amber-700 text-white border border-transparent hover:bg-amber-800 focus-visible:ring-amber-500',
  ghost:
    'bg-transparent text-slate-600 border border-transparent hover:bg-slate-100 focus-visible:ring-indigo-500',
  subtle:
    'bg-indigo-50 text-indigo-700 border border-indigo-200 hover:bg-indigo-100 focus-visible:ring-indigo-500',
}

const SIZE_CLASSES = {
  sm: 'h-7 px-2.5 text-[11px] gap-1.5',
  md: 'h-8 px-3 text-xs gap-2',
}

const classes = computed(() => [
  'inline-flex items-center justify-center rounded-md font-medium transition-colors',
  'focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-1',
  SIZE_CLASSES[props.size],
  VARIANT_CLASSES[props.variant],
  props.block ? 'w-full' : '',
  props.disabled || props.loading ? 'cursor-not-allowed opacity-50' : '',
])

function handleClick(event) {
  if (props.disabled || props.loading) {
    event.preventDefault()
    return
  }
  emit('click', event)
}
</script>

<template>
  <button
    :type="type"
    :class="classes"
    :disabled="disabled || loading"
    :aria-busy="loading || undefined"
    @click="handleClick"
  >
    <Loader2 v-if="loading" class="w-4 h-4 animate-spin" aria-hidden="true" />
    <slot v-else name="icon" />
    <slot />
  </button>
</template>

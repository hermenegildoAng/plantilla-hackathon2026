<script setup>
import { computed } from 'vue'

defineOptions({ inheritAttrs: false })

let inputCounter = 0

const props = defineProps({
  modelValue: {
    type: [String, Number],
    default: '',
  },
  label: {
    type: String,
    default: '',
  },
  error: {
    type: String,
    default: '',
  },
  hint: {
    type: String,
    default: '',
  },
  id: {
    type: String,
    default: '',
  },
  type: {
    type: String,
    default: 'text',
  },
  placeholder: {
    type: String,
    default: '',
  },
  required: Boolean,
  disabled: Boolean,
  wrapperClass: {
    type: [String, Array, Object],
    default: '',
  },
  inputClass: {
    type: [String, Array, Object],
    default: '',
  },
})

const emit = defineEmits(['update:modelValue', 'blur', 'focus', 'keydown'])

const inputId = computed(() => props.id || `base-input-${++inputCounter}`)
const describedBy = computed(() => {
  if (props.error) return `${inputId.value}-error`
  if (props.hint) return `${inputId.value}-hint`
  return undefined
})

const inputClasses = computed(() => [
  'block w-full rounded-md border bg-white px-2.5 py-1.5 text-xs text-slate-700',
  'placeholder:text-slate-400 shadow-sm transition-colors',
  'focus:outline-none focus:ring-2 focus:ring-offset-1',
  'disabled:cursor-not-allowed disabled:bg-slate-50 disabled:text-slate-500',
  props.error
    ? 'border-rose-300 focus:border-rose-400 focus:ring-rose-500'
    : 'border-slate-300 focus:border-indigo-400 focus:ring-indigo-500',
  props.inputClass,
])
</script>

<template>
  <div :class="wrapperClass">
    <label
      v-if="label"
      :for="inputId"
      class="mb-1 block text-xs font-medium text-slate-700"
    >
      {{ label }}
      <span v-if="required" class="text-rose-600" aria-hidden="true">*</span>
    </label>

    <div class="relative">
      <div
        v-if="$slots.icon"
        class="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-2.5 text-slate-400"
        aria-hidden="true"
      >
        <slot name="icon" />
      </div>

      <input
        :id="inputId"
        :value="modelValue"
        :type="type"
        :placeholder="placeholder"
        :required="required"
        :disabled="disabled"
        :aria-invalid="error ? 'true' : undefined"
        :aria-describedby="describedBy"
        :class="[inputClasses, $slots.icon ? 'pl-8' : '']"
        v-bind="$attrs"
        @input="emit('update:modelValue', $event.target.value)"
        @blur="emit('blur', $event)"
        @focus="emit('focus', $event)"
        @keydown="emit('keydown', $event)"
      />
    </div>

    <p v-if="error" :id="`${inputId}-error`" class="mt-1 text-[11px] text-rose-700">
      {{ error }}
    </p>
    <p
      v-else-if="hint"
      :id="`${inputId}-hint`"
      class="mt-1 text-[11px] text-slate-500"
    >
      {{ hint }}
    </p>
  </div>
</template>

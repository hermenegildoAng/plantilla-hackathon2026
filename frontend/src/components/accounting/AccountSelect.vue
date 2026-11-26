<script setup>
import { computed, ref, watch } from 'vue'
import { Check, Search, X } from 'lucide-vue-next'

import { useClickOutside } from '../../composables/useClickOutside'

const props = defineProps({
  modelValue: {
    type: [String, Number],
    default: '',
  },
  accounts: {
    type: Array,
    default: () => [],
  },
  placeholder: {
    type: String,
    default: 'Buscar cuenta afectable…',
  },
  disabled: Boolean,
  error: {
    type: String,
    default: '',
  },
})

const emit = defineEmits(['update:modelValue'])

const root = ref(null)
const open = ref(false)
const search = ref('')

useClickOutside(root, () => {
  open.value = false
  search.value = ''
})

const selectableAccounts = computed(() =>
  props.accounts
    .filter(
      (account) =>
        account?.is_selectable !== false && account?.is_active !== false,
    )
    .slice()
    .sort((left, right) =>
      String(left.code || '').localeCompare(String(right.code || ''), 'es'),
    ),
)

const selected = computed(
  () =>
    selectableAccounts.value.find(
      (account) => String(account.id) === String(props.modelValue),
    ) || null,
)

const filtered = computed(() => {
  const term = search.value.trim().toLowerCase()
  if (!term) return selectableAccounts.value.slice(0, 80)
  return selectableAccounts.value
    .filter(
      (account) =>
        String(account.code || '').toLowerCase().includes(term) ||
        String(account.name || '').toLowerCase().includes(term),
    )
    .slice(0, 80)
})

const displayValue = computed(() => {
  if (open.value) return search.value
  if (!selected.value) return ''
  return `${selected.value.code} · ${selected.value.name}`
})

watch(
  () => props.disabled,
  (disabled) => {
    if (disabled) {
      open.value = false
      search.value = ''
    }
  },
)

function openList() {
  if (props.disabled) return
  open.value = true
  search.value = ''
}

function choose(account) {
  emit('update:modelValue', account.id)
  open.value = false
  search.value = ''
}

function clear() {
  emit('update:modelValue', '')
  open.value = false
  search.value = ''
}
</script>

<template>
  <div ref="root" class="relative">
    <div class="relative">
      <Search
        class="pointer-events-none absolute left-2 top-1/2 w-3.5 h-3.5 -translate-y-1/2 text-slate-400"
        aria-hidden="true"
      />
      <input
        :value="displayValue"
        type="text"
        :placeholder="placeholder"
        :disabled="disabled"
        :aria-invalid="error ? 'true' : undefined"
        class="block h-8 w-full rounded-md border bg-white pl-7 pr-7 text-xs text-slate-700 shadow-sm transition-colors placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-offset-1 disabled:cursor-not-allowed disabled:bg-slate-50 disabled:text-slate-500"
        :class="
          error
            ? 'border-rose-300 focus:border-rose-400 focus:ring-rose-500'
            : 'border-slate-300 focus:border-indigo-400 focus:ring-indigo-500'
        "
        role="combobox"
        aria-autocomplete="list"
        :aria-expanded="open"
        @focus="openList"
        @input="search = $event.target.value"
      />
      <button
        v-if="modelValue && !disabled"
        type="button"
        class="absolute right-1.5 top-1/2 -translate-y-1/2 rounded p-0.5 text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-600 focus:outline-none focus:ring-2 focus:ring-indigo-500"
        aria-label="Quitar cuenta seleccionada"
        @click="clear"
      >
        <X class="w-3.5 h-3.5" aria-hidden="true" />
      </button>
    </div>

    <div
      v-if="open"
      class="absolute z-40 mt-1 max-h-56 w-full min-w-[260px] overflow-y-auto rounded-md border border-slate-200 bg-white py-1 shadow-lg"
      role="listbox"
    >
      <button
        v-for="account in filtered"
        :key="account.id"
        type="button"
        class="flex w-full items-center gap-2 px-2.5 py-1.5 text-left text-xs transition-colors hover:bg-slate-50 focus:bg-slate-50 focus:outline-none"
        role="option"
        :aria-selected="String(account.id) === String(modelValue)"
        @click="choose(account)"
      >
        <Check
          class="w-3.5 h-3.5 shrink-0"
          :class="
            String(account.id) === String(modelValue)
              ? 'text-indigo-600'
              : 'text-transparent'
          "
          aria-hidden="true"
        />
        <span class="shrink-0 font-mono text-[10px] text-slate-500">
          {{ account.code }}
        </span>
        <span class="truncate text-slate-700">{{ account.name }}</span>
      </button>

      <p v-if="filtered.length === 0" class="px-3 py-2 text-[11px] text-slate-500">
        Sin cuentas afectables que coincidan con la búsqueda.
      </p>
    </div>

    <p v-if="error" class="mt-1 text-[11px] text-rose-700">{{ error }}</p>
  </div>
</template>

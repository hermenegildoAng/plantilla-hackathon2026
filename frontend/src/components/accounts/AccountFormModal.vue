<script setup>
import { computed, onBeforeUnmount, reactive, watch } from 'vue'
import { AlertCircle, FolderTree, X } from 'lucide-vue-next'

import BaseButton from '../ui/BaseButton.vue'

const ACCOUNT_TYPES = [
  { value: 'ASSET', label: 'Activo' },
  { value: 'LIABILITY', label: 'Pasivo' },
  { value: 'EQUITY', label: 'Capital' },
  { value: 'REVENUE', label: 'Ingresos' },
  { value: 'EXPENSE', label: 'Costos y gastos' },
  { value: 'ORDER', label: 'Cuentas de orden' },
]

const NATURES = [
  { value: 'DEBIT', label: 'Deudora' },
  { value: 'CREDIT', label: 'Acreedora' },
]

const props = defineProps({
  modelValue: Boolean,
  account: {
    type: Object,
    default: null,
  },
  accounts: {
    type: Array,
    default: () => [],
  },
  mode: {
    type: String,
    default: 'full',
  },
  loading: Boolean,
  error: {
    type: String,
    default: '',
  },
})

const emit = defineEmits(['update:modelValue', 'submit'])

const form = reactive({
  code: '',
  sat_group_code: '',
  name: '',
  account_type: 'ASSET',
  nature: 'DEBIT',
  parent: '',
  is_selectable: true,
  is_active: true,
})

const isNameMode = computed(() => props.mode === 'name')
const isEditing = computed(() => Boolean(props.account))
const title = computed(() => {
  if (isNameMode.value) return 'Editar nombre de la cuenta'
  return isEditing.value ? 'Editar cuenta contable' : 'Nueva cuenta contable'
})

const parentAccounts = computed(() =>
  props.accounts
    .filter((account) => account.id !== props.account?.id)
    .slice()
    .sort((left, right) =>
      String(left.code || '').localeCompare(String(right.code || ''), 'es'),
    ),
)

function resetForm() {
  const account = props.account
  form.code = account?.code || ''
  form.sat_group_code = account?.sat_group_code || ''
  form.name = account?.name || ''
  form.account_type = account?.account_type || 'ASSET'
  form.nature = account?.nature || 'DEBIT'
  form.parent = account?.parent ? String(account.parent) : ''
  form.is_selectable = account?.is_selectable ?? true
  form.is_active = account?.is_active ?? true
}

function close() {
  if (props.loading) return
  emit('update:modelValue', false)
}

function submit() {
  if (props.loading) return
  if (isNameMode.value) {
    emit('submit', { name: form.name.trim() })
    return
  }

  emit('submit', {
    code: form.code.trim(),
    sat_group_code: form.sat_group_code.trim(),
    name: form.name.trim(),
    account_type: form.account_type,
    nature: form.nature,
    parent: form.parent ? Number(form.parent) : null,
    is_selectable: form.is_selectable,
    is_active: form.is_active,
  })
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
      resetForm()
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
          class="w-full max-w-lg overflow-hidden rounded-lg border border-slate-200 bg-white shadow-xl"
          role="dialog"
          aria-modal="true"
          aria-labelledby="account-form-title"
        >
          <div class="flex items-start gap-3 border-b border-slate-200 px-4 py-3">
            <div class="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-indigo-100 text-indigo-700">
              <FolderTree class="w-4 h-4" aria-hidden="true" />
            </div>
            <div class="min-w-0 flex-1">
              <h2 id="account-form-title" class="text-sm font-semibold text-slate-900">
                {{ title }}
              </h2>
              <p class="mt-0.5 text-[11px] text-slate-500">
                {{
                  isNameMode
                    ? 'El auxiliar contable únicamente puede modificar el nombre.'
                    : 'Los cambios de código, tipo o naturaleza afectan la clasificación contable.'
                }}
              </p>
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

          <form class="space-y-2 px-4 py-3" @submit.prevent="submit">
            <div v-if="!isNameMode" class="grid gap-2 sm:grid-cols-2">
              <div>
                <label for="account-code" class="mb-1 block text-[11px] font-medium text-slate-600">
                  Código <span class="text-rose-600" aria-hidden="true">*</span>
                </label>
                <input
                  id="account-code"
                  v-model="form.code"
                  type="text"
                  maxlength="30"
                  class="block h-8 w-full rounded-md border border-slate-300 bg-white px-2.5 text-xs text-slate-700 shadow-sm focus:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-1"
                  :disabled="loading"
                  required
                />
              </div>
              <div>
                <label for="account-sat-code" class="mb-1 block text-[11px] font-medium text-slate-600">
                  Código agrupador SAT <span class="text-rose-600" aria-hidden="true">*</span>
                </label>
                <input
                  id="account-sat-code"
                  v-model="form.sat_group_code"
                  type="text"
                  maxlength="15"
                  class="block h-8 w-full rounded-md border border-slate-300 bg-white px-2.5 text-xs text-slate-700 shadow-sm focus:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-1"
                  :disabled="loading"
                  required
                />
              </div>
            </div>

            <div>
              <label for="account-name" class="mb-1 block text-[11px] font-medium text-slate-600">
                Nombre <span class="text-rose-600" aria-hidden="true">*</span>
              </label>
              <input
                id="account-name"
                v-model="form.name"
                type="text"
                maxlength="255"
                class="block h-8 w-full rounded-md border border-slate-300 bg-white px-2.5 text-xs text-slate-700 shadow-sm focus:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-1"
                :disabled="loading"
                required
              />
            </div>

            <template v-if="!isNameMode">
              <div class="grid gap-2 sm:grid-cols-2">
                <div>
                  <label for="account-type" class="mb-1 block text-[11px] font-medium text-slate-600">
                    Tipo de cuenta
                  </label>
                  <select
                    id="account-type"
                    v-model="form.account_type"
                    class="block h-8 w-full rounded-md border border-slate-300 bg-white px-2.5 text-xs text-slate-700 shadow-sm focus:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-1"
                    :disabled="loading"
                  >
                    <option v-for="option in ACCOUNT_TYPES" :key="option.value" :value="option.value">
                      {{ option.label }}
                    </option>
                  </select>
                </div>
                <div>
                  <label for="account-nature" class="mb-1 block text-[11px] font-medium text-slate-600">
                    Naturaleza
                  </label>
                  <select
                    id="account-nature"
                    v-model="form.nature"
                    class="block h-8 w-full rounded-md border border-slate-300 bg-white px-2.5 text-xs text-slate-700 shadow-sm focus:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-1"
                    :disabled="loading"
                  >
                    <option v-for="option in NATURES" :key="option.value" :value="option.value">
                      {{ option.label }}
                    </option>
                  </select>
                </div>
              </div>

              <div>
                <label for="account-parent" class="mb-1 block text-[11px] font-medium text-slate-600">
                  Cuenta padre
                </label>
                <select
                  id="account-parent"
                  v-model="form.parent"
                  class="block h-8 w-full rounded-md border border-slate-300 bg-white px-2.5 text-xs text-slate-700 shadow-sm focus:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-1"
                  :disabled="loading"
                >
                  <option value="">Sin cuenta padre</option>
                  <option
                    v-for="accountOption in parentAccounts"
                    :key="accountOption.id"
                    :value="String(accountOption.id)"
                  >
                    {{ accountOption.code }} · {{ accountOption.name }}
                  </option>
                </select>
              </div>

              <div class="flex flex-wrap items-center gap-4 pt-1">
                <label class="inline-flex items-center gap-1.5 text-[11px] font-medium text-slate-700">
                  <input
                    v-model="form.is_selectable"
                    type="checkbox"
                    class="h-3.5 w-3.5 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
                    :disabled="loading"
                  />
                  Cuenta afectable
                </label>
                <label class="inline-flex items-center gap-1.5 text-[11px] font-medium text-slate-700">
                  <input
                    v-model="form.is_active"
                    type="checkbox"
                    class="h-3.5 w-3.5 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
                    :disabled="loading"
                  />
                  Cuenta activa
                </label>
              </div>
            </template>

            <div v-if="error" class="flex items-start gap-1.5 rounded-md border border-rose-200 bg-rose-50 px-2 py-1.5 text-[11px] text-rose-800" role="alert">
              <AlertCircle class="mt-0.5 w-3.5 h-3.5 shrink-0" aria-hidden="true" />
              <p>{{ error }}</p>
            </div>
          </form>

          <div class="flex justify-end gap-2 border-t border-slate-200 bg-slate-50 px-4 py-2.5">
            <BaseButton variant="secondary" :disabled="loading" @click="close">
              Cancelar
            </BaseButton>
            <BaseButton :loading="loading" @click="submit">
              {{ isEditing ? 'Guardar cambios' : 'Crear cuenta' }}
            </BaseButton>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

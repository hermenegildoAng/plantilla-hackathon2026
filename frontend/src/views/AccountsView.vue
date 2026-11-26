<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import {
  AlertCircle,
  FolderTree,
  Pencil,
  Plus,
  Power,
  RefreshCw,
  Search,
  Trash2,
} from 'lucide-vue-next'

import {
  createAccount,
  deleteAccount,
  listAllAccounts,
  updateAccount,
} from '../api/accounting'
import AccountFormModal from '../components/accounts/AccountFormModal.vue'
import BaseBadge from '../components/ui/BaseBadge.vue'
import BaseButton from '../components/ui/BaseButton.vue'
import BaseInput from '../components/ui/BaseInput.vue'
import ConfirmModal from '../components/ui/ConfirmModal.vue'
import DataTable from '../components/ui/DataTable.vue'
import { ROLES, useRBAC } from '../composables/useRBAC'
import { useToast } from '../composables/useToast'

const ACCOUNT_TYPE_LABELS = {
  ASSET: 'Activo',
  LIABILITY: 'Pasivo',
  EQUITY: 'Capital',
  REVENUE: 'Ingresos',
  EXPENSE: 'Costos y gastos',
  ORDER: 'Cuentas de orden',
}

const NATURE_LABELS = {
  DEBIT: 'Deudora',
  CREDIT: 'Acreedora',
}

const selectClass =
  'block h-8 w-full rounded-md border border-slate-300 bg-white px-2.5 text-xs text-slate-700 shadow-sm transition-colors focus:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-1 disabled:cursor-not-allowed disabled:bg-slate-50'

const columns = [
  { key: 'code', label: 'Código', align: 'left', width: '130px' },
  { key: 'name', label: 'Nombre de la cuenta', align: 'left' },
  { key: 'account_type', label: 'Tipo', align: 'center', width: '124px' },
  { key: 'nature', label: 'Naturaleza', align: 'center', width: '110px' },
  { key: 'is_selectable', label: 'Afectable', align: 'center', width: '100px' },
  { key: 'is_active', label: 'Estado', align: 'center', width: '100px' },
  { key: 'actions', label: 'Acciones', align: 'center', width: '190px' },
]

const { can, currentRole } = useRBAC()
const toast = useToast()

const isPartner = computed(() => can([ROLES.PARTNER]))
const isAccountant = computed(() => currentRole.value === ROLES.ACCOUNTANT)

const filters = reactive({
  search: '',
  account_type: '',
})

const roots = ref([])
const loading = ref(false)
const loadError = ref('')

const modalOpen = ref(false)
const modalMode = ref('full')
const editingAccount = ref(null)
const modalLoading = ref(false)
const modalError = ref('')

const toggleTarget = ref(null)
const toggleLoading = ref(false)

const deleteTarget = ref(null)
const deleteLoading = ref(false)

let filterTimer = null
let filtersReady = false
let requestId = 0

function flattenTree(nodes, depth = 0, accumulator = []) {
  nodes.forEach((node) => {
    accumulator.push({ ...node, _depth: depth })
    if (Array.isArray(node.children) && node.children.length) {
      flattenTree(node.children, depth + 1, accumulator)
    }
  })
  return accumulator
}

const rows = computed(() => flattenTree(roots.value))

function filterParams() {
  const params = { tree: 'true' }
  const term = filters.search.trim()
  if (term) params.search = term
  if (filters.account_type) params.account_type = filters.account_type
  return params
}

async function loadAccounts() {
  const currentRequest = ++requestId
  loading.value = true
  loadError.value = ''
  try {
    const { results } = await listAllAccounts(filterParams())
    if (currentRequest !== requestId) return
    roots.value = results
  } catch (error) {
    if (currentRequest !== requestId) return
    roots.value = []
    loadError.value =
      error?.message || 'No fue posible consultar el catálogo de cuentas.'
  } finally {
    if (currentRequest === requestId) loading.value = false
  }
}

function applyFilters() {
  clearTimeout(filterTimer)
  loadAccounts()
}

function clearFilters() {
  filters.search = ''
  filters.account_type = ''
}

function openCreate() {
  if (!isPartner.value) return
  editingAccount.value = null
  modalMode.value = 'full'
  modalError.value = ''
  modalOpen.value = true
}

function openEdit(account) {
  if (!isPartner.value && !isAccountant.value) return
  editingAccount.value = account
  modalMode.value = isPartner.value ? 'full' : 'name'
  modalError.value = ''
  modalOpen.value = true
}

async function saveAccount(payload) {
  modalLoading.value = true
  modalError.value = ''
  try {
    if (editingAccount.value) {
      await updateAccount(editingAccount.value.id, payload)
      toast.success('Cuenta contable actualizada correctamente.')
    } else {
      await createAccount(payload)
      toast.success('Cuenta contable creada correctamente.')
    }
    modalOpen.value = false
    await loadAccounts()
  } catch (error) {
    modalError.value =
      error?.message || 'No fue posible guardar la cuenta contable.'
  } finally {
    modalLoading.value = false
  }
}

function requestToggle(account) {
  if (!isPartner.value) return
  toggleTarget.value = account
}

async function confirmToggle() {
  if (!toggleTarget.value) return
  toggleLoading.value = true
  try {
    const target = toggleTarget.value
    await updateAccount(target.id, { is_active: !target.is_active })
    toast.success(
      target.is_active
        ? 'Cuenta contable desactivada correctamente.'
        : 'Cuenta contable reactivada correctamente.',
    )
    toggleTarget.value = null
    await loadAccounts()
  } catch (error) {
    toast.error(
      error?.message || 'No fue posible cambiar el estado de la cuenta.',
      { title: 'No se pudo actualizar la cuenta' },
    )
  } finally {
    toggleLoading.value = false
  }
}

function requestDelete(account) {
  if (!isPartner.value) return
  deleteTarget.value = account
}

async function confirmDelete() {
  if (!deleteTarget.value) return
  deleteLoading.value = true
  try {
    await deleteAccount(deleteTarget.value.id)
    toast.success('Cuenta contable eliminada correctamente.')
    deleteTarget.value = null
    await loadAccounts()
  } catch (error) {
    toast.error(
      error?.message ||
        'No fue posible eliminar la cuenta. Verifica que no tenga movimientos ni cuentas hijas.',
      { title: 'No se pudo eliminar la cuenta' },
    )
  } finally {
    deleteLoading.value = false
  }
}

watch(
  filters,
  () => {
    if (!filtersReady) return
    clearTimeout(filterTimer)
    filterTimer = setTimeout(applyFilters, 300)
  },
  { deep: true },
)

onMounted(async () => {
  filtersReady = true
  await loadAccounts()
})

onBeforeUnmount(() => {
  clearTimeout(filterTimer)
})
</script>

<template>
  <section class="space-y-3">
    <header class="flex flex-wrap items-start justify-between gap-2">
      <div class="min-w-0">
        <h1 class="text-lg font-semibold tracking-tight text-slate-900">
          Catálogo de cuentas
        </h1>
        <p class="mt-1 max-w-2xl text-xs text-slate-600">
          Catálogo jerárquico de cuentas contables y agrupadores SAT de la
          empresa activa.
        </p>
      </div>

      <div class="flex flex-wrap items-center gap-2">
        <BaseBadge v-if="isAccountant" variant="info" dot>
          Puedes editar nombres
        </BaseBadge>
        <BaseBadge v-else-if="!isPartner" variant="neutral" dot>
          Solo lectura
        </BaseBadge>
        <BaseButton
          variant="ghost"
          size="sm"
          :loading="loading"
          title="Actualizar catálogo"
          @click="loadAccounts"
        >
          <template #icon>
            <RefreshCw class="w-3.5 h-3.5" aria-hidden="true" />
          </template>
          Actualizar
        </BaseButton>
        <BaseButton v-if="isPartner" @click="openCreate">
          <template #icon>
            <Plus class="w-3.5 h-3.5" aria-hidden="true" />
          </template>
          Nueva cuenta
        </BaseButton>
      </div>
    </header>

    <div
      v-if="loadError"
      class="flex items-start gap-2 rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-[11px] text-rose-800"
      role="alert"
    >
      <AlertCircle class="mt-0.5 w-3.5 h-3.5 shrink-0" aria-hidden="true" />
      <p>{{ loadError }}</p>
    </div>

    <div class="rounded-lg border border-slate-200 bg-white p-3 shadow-sm">
      <div class="grid gap-2 sm:grid-cols-2 lg:grid-cols-5">
        <BaseInput
          v-model="filters.search"
          label="Búsqueda"
          placeholder="Código o nombre de la cuenta"
          wrapper-class="lg:col-span-3"
          @keydown.enter="applyFilters"
        >
          <template #icon>
            <Search class="w-3.5 h-3.5" aria-hidden="true" />
          </template>
        </BaseInput>

        <div class="lg:col-span-2">
          <label for="account-filter-type" class="mb-1 block text-[11px] font-medium text-slate-600">
            Tipo de cuenta
          </label>
          <select id="account-filter-type" v-model="filters.account_type" :class="selectClass">
            <option value="">Todos los tipos</option>
            <option value="ASSET">Activo</option>
            <option value="LIABILITY">Pasivo</option>
            <option value="EQUITY">Capital</option>
            <option value="REVENUE">Ingresos</option>
            <option value="EXPENSE">Costos y gastos</option>
            <option value="ORDER">Cuentas de orden</option>
          </select>
        </div>
      </div>

      <div class="mt-2 flex flex-wrap items-center justify-between gap-2">
        <p class="text-[11px] text-slate-500">
          <span class="font-semibold tabular-nums text-slate-700">{{ rows.length }}</span>
          cuenta{{ rows.length === 1 ? '' : 's' }} en el filtro
        </p>
        <BaseButton variant="ghost" size="sm" @click="clearFilters">
          Limpiar filtros
        </BaseButton>
      </div>
    </div>

    <DataTable
      :columns="columns"
      :rows="rows"
      :loading="loading"
      row-key="id"
      max-height="66vh"
      empty-title="Sin cuentas contables"
      empty-description="Ajusta los filtros o crea una cuenta nueva en el catálogo."
    >
      <template #cell-code="{ row }">
        <span class="font-mono text-[11px] font-medium text-slate-700">
          {{ row.code }}
        </span>
      </template>

      <template #cell-name="{ row }">
        <div class="flex items-center gap-1.5" :style="{ paddingLeft: `${row._depth * 16}px` }">
          <FolderTree
            class="w-3.5 h-3.5 shrink-0"
            :class="row._depth === 0 ? 'text-indigo-500' : 'text-slate-300'"
            aria-hidden="true"
          />
          <span class="text-xs text-slate-800" :title="row.name">{{ row.name }}</span>
        </div>
      </template>

      <template #cell-account_type="{ row }">
        <BaseBadge variant="neutral">
          {{ ACCOUNT_TYPE_LABELS[row.account_type] || row.account_type }}
        </BaseBadge>
      </template>

      <template #cell-nature="{ row }">
        <span class="text-[11px] text-slate-600">
          {{ NATURE_LABELS[row.nature] || row.nature }}
        </span>
      </template>

      <template #cell-is_selectable="{ row }">
        <BaseBadge :variant="row.is_selectable ? 'info' : 'neutral'">
          {{ row.is_selectable ? 'Sí' : 'No' }}
        </BaseBadge>
      </template>

      <template #cell-is_active="{ row }">
        <BaseBadge :variant="row.is_active ? 'success' : 'danger'" dot>
          {{ row.is_active ? 'Activa' : 'Inactiva' }}
        </BaseBadge>
      </template>

      <template #cell-actions="{ row }">
        <div class="flex flex-wrap items-center justify-center gap-1">
          <template v-if="isPartner || isAccountant">
            <BaseButton
              variant="secondary"
              size="sm"
              @click="openEdit(row)"
            >
              <template #icon>
                <Pencil class="w-3.5 h-3.5" aria-hidden="true" />
              </template>
              {{ isPartner ? 'Editar' : 'Editar nombre' }}
            </BaseButton>
          </template>
          <BaseButton
            v-if="isPartner"
            :variant="row.is_active ? 'ghost' : 'subtle'"
            size="sm"
            @click="requestToggle(row)"
          >
            <template #icon>
              <Power class="w-3.5 h-3.5" aria-hidden="true" />
            </template>
            {{ row.is_active ? 'Desactivar' : 'Activar' }}
          </BaseButton>
          <button
            v-if="isPartner"
            type="button"
            class="inline-flex h-7 items-center gap-1 rounded-md px-2 text-[11px] font-medium text-rose-600 transition-colors hover:bg-rose-50 focus:outline-none focus:ring-2 focus:ring-rose-500"
            @click="requestDelete(row)"
          >
            <Trash2 class="w-3.5 h-3.5" aria-hidden="true" />
            Eliminar
          </button>
          <span v-if="!isPartner && !isAccountant" class="text-[11px] text-slate-400">
            —
          </span>
        </div>
      </template>
    </DataTable>

    <AccountFormModal
      v-model="modalOpen"
      :account="editingAccount"
      :accounts="rows"
      :mode="modalMode"
      :loading="modalLoading"
      :error="modalError"
      @submit="saveAccount"
    />

    <ConfirmModal
      :model-value="Boolean(toggleTarget)"
      :title="toggleTarget?.is_active ? 'Desactivar cuenta contable' : 'Reactivar cuenta contable'"
      :confirm-text="toggleTarget?.is_active ? 'Desactivar cuenta' : 'Reactivar cuenta'"
      :variant="toggleTarget?.is_active ? 'warning' : 'primary'"
      :loading="toggleLoading"
      @update:model-value="(value) => { if (!value) toggleTarget = null }"
      @confirm="confirmToggle"
      @cancel="toggleTarget = null"
    >
      <p>
        Se cambiará el estado de la cuenta
        <strong class="font-mono text-slate-900">
          {{ toggleTarget ? `${toggleTarget.code} · ${toggleTarget.name}` : '' }}
        </strong>.
      </p>
      <p class="mt-1.5 text-[11px] text-slate-500">
        Las cuentas con movimientos contables no deben eliminarse físicamente;
        la desactivación conserva el historial y evita nuevos movimientos.
      </p>
    </ConfirmModal>

    <ConfirmModal
      :model-value="Boolean(deleteTarget)"
      title="Eliminar cuenta contable"
      confirm-text="Eliminar cuenta"
      variant="danger"
      :loading="deleteLoading"
      @update:model-value="(value) => { if (!value) deleteTarget = null }"
      @confirm="confirmDelete"
      @cancel="deleteTarget = null"
    >
      <p>
        Se eliminará permanentemente la cuenta
        <strong class="font-mono text-slate-900">
          {{ deleteTarget ? `${deleteTarget.code} · ${deleteTarget.name}` : '' }}
        </strong>.
      </p>
      <p class="mt-1.5 text-[11px] text-slate-500">
        Solo puedes eliminar cuentas sin cuentas hijas ni movimientos
        contables. Si la cuenta tiene historial, desactívala en su lugar.
      </p>
    </ConfirmModal>
  </section>
</template>

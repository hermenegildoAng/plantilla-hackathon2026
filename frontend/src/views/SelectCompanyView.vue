<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import {
  ArrowRight,
  Building2,
  Check,
  Landmark,
  Loader2,
  LogOut,
  Search,
} from 'lucide-vue-next'

import BaseBadge from '../components/ui/BaseBadge.vue'
import BaseButton from '../components/ui/BaseButton.vue'
import BaseInput from '../components/ui/BaseInput.vue'
import EmptyState from '../components/ui/EmptyState.vue'
import { ROLE_LABELS } from '../composables/useRBAC'
import { useToast } from '../composables/useToast'
import { useAuthStore } from '../stores/auth'
import { useTenantStore } from '../stores/tenant'

const router = useRouter()
const auth = useAuthStore()
const tenant = useTenantStore()
const toast = useToast()

const search = ref('')
const loggingOut = ref(false)

const filteredCompanies = computed(() => {
  const term = search.value.trim().toLowerCase()
  if (!term) return tenant.companies
  return tenant.companies.filter((company) => {
    const name = String(company.legal_name || '').toLowerCase()
    const rfc = String(company.rfc || '').toLowerCase()
    return name.includes(term) || rfc.includes(term)
  })
})

onMounted(async () => {
  tenant.syncFromMemberships(auth.memberships)
  if (tenant.companies.length === 0) {
    try {
      await tenant.fetchCompanies()
    } catch {
      // El interceptor ya informa el error; la vista conserva las membresías.
    }
  }
})

function selectCompany(company) {
  tenant.setCurrentCompany(company)
  router.push({ name: 'dashboard', params: { id: String(company.id) } })
}

async function handleLogout() {
  if (loggingOut.value) return
  loggingOut.value = true
  try {
    await auth.logout()
  } finally {
    tenant.reset()
    loggingOut.value = false
    toast.success('Sesión cerrada correctamente.')
    router.replace({ name: 'login' })
  }
}

function roleLabel(company) {
  return ROLE_LABELS[company.user_role] || 'Miembro'
}
</script>

<template>
  <div class="flex min-h-screen flex-col bg-slate-50">
    <header class="border-b border-slate-200 bg-white">
      <div class="mx-auto flex h-14 max-w-4xl items-center gap-2.5 px-4">
        <div class="flex h-8 w-8 items-center justify-center rounded-md bg-indigo-600">
          <Landmark class="w-4 h-4 text-white" aria-hidden="true" />
        </div>
        <div class="min-w-0">
          <p class="text-xs font-semibold text-slate-900">Contable MX</p>
          <p class="text-[10px] text-slate-500">Sistema contable multiempresa</p>
        </div>

        <div class="ml-auto flex items-center gap-3">
          <div class="hidden text-right sm:block">
            <p class="max-w-[200px] truncate text-xs font-medium text-slate-700">
              {{ auth.fullName }}
            </p>
            <p class="max-w-[200px] truncate text-[10px] text-slate-500">
              {{ auth.user?.email }}
            </p>
          </div>
          <BaseButton variant="ghost" size="sm" :disabled="loggingOut" @click="handleLogout">
            <template #icon>
              <LogOut class="w-4 h-4" aria-hidden="true" />
            </template>
            Salir
          </BaseButton>
        </div>
      </div>
    </header>

    <main class="mx-auto w-full max-w-4xl flex-1 px-4 py-8">
      <div class="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 class="text-lg font-semibold tracking-tight text-slate-900">
            Selecciona una empresa
          </h1>
          <p class="mt-1 max-w-2xl text-xs text-slate-600">
            Elige el contribuyente con el que vas a trabajar. Todos los datos,
            permisos y movimientos se aislarán en esta empresa.
          </p>
        </div>
        <BaseBadge variant="brand">
          {{ tenant.companies.length }}
          {{ tenant.companies.length === 1 ? 'empresa disponible' : 'empresas disponibles' }}
        </BaseBadge>
      </div>

      <div class="mt-4 max-w-md">
        <BaseInput
          v-model="search"
          type="search"
          placeholder="Buscar por empresa o RFC..."
          aria-label="Buscar empresa"
        >
          <template #icon>
            <Search class="w-3.5 h-3.5" aria-hidden="true" />
          </template>
        </BaseInput>
      </div>

      <div v-if="tenant.loading" class="mt-8 flex items-center justify-center gap-2 text-xs text-slate-500">
        <Loader2 class="w-4 h-4 animate-spin" aria-hidden="true" />
        Cargando empresas...
      </div>

      <div v-else class="mt-4 space-y-2">
        <button
          v-for="company in filteredCompanies"
          :key="company.id"
          type="button"
          class="flex w-full items-center gap-3 rounded-lg border bg-white p-3 text-left shadow-sm transition-colors focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-1"
          :class="
            String(company.id) === String(tenant.currentCompanyId)
              ? 'border-indigo-300 bg-indigo-50/40'
              : 'border-slate-200 hover:border-indigo-300 hover:bg-slate-50'
          "
          @click="selectCompany(company)"
        >
          <div class="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-indigo-50">
            <Building2 class="w-4 h-4 text-indigo-600" aria-hidden="true" />
          </div>

          <div class="min-w-0 flex-1">
            <p class="truncate text-xs font-semibold text-slate-900">
              {{ company.legal_name }}
            </p>
            <div class="mt-1 flex flex-wrap items-center gap-1.5">
              <span
                class="rounded border border-slate-200 bg-white px-1.5 py-0.5 font-mono text-[10px] text-slate-600"
              >
                {{ company.rfc }}
              </span>
              <span class="text-[11px] text-slate-500">
                {{ company.tax_regime_display || company.tax_regime }}
              </span>
            </div>
            <p class="mt-1 text-[11px] text-slate-500">
              {{ roleLabel(company) }}
            </p>
          </div>

          <Check
            v-if="String(company.id) === String(tenant.currentCompanyId)"
            class="w-4 h-4 shrink-0 text-indigo-600"
            aria-label="Empresa activa"
          />
          <ArrowRight v-else class="w-4 h-4 shrink-0 text-slate-400" aria-hidden="true" />
        </button>

        <div
          v-if="filteredCompanies.length === 0"
          class="rounded-lg border border-slate-200 bg-white shadow-sm"
        >
          <EmptyState
            title="Sin empresas disponibles"
            :description="
              search
                ? 'No hay empresas que coincidan con la búsqueda.'
                : 'Tu usuario no tiene membresías activas. Solicita acceso al socio administrador del despacho.'
            "
          />
        </div>
      </div>

      <!-- TODO(bloque 8): agregar la creación de empresas para PARTNER/superusuario. -->
    </main>
  </div>
</template>

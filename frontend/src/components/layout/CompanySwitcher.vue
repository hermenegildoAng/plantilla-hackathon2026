<script setup>
import { computed, nextTick, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Building2, Check, ChevronsUpDown, Search } from 'lucide-vue-next'

import { useClickOutside } from '../../composables/useClickOutside'
import { ROLE_LABELS } from '../../composables/useRBAC'
import { useTenantStore } from '../../stores/tenant'

const route = useRoute()
const router = useRouter()
const tenant = useTenantStore()

const root = ref(null)
const searchInput = ref(null)
const open = ref(false)
const search = ref('')

const currentCompany = computed(
  () => tenant.currentCompany || tenant.companyById(route.params.id),
)

const filteredCompanies = computed(() => {
  const term = search.value.trim().toLowerCase()
  if (!term) return tenant.companies
  return tenant.companies.filter((company) => {
    const name = String(company.legal_name || '').toLowerCase()
    const rfc = String(company.rfc || '').toLowerCase()
    return name.includes(term) || rfc.includes(term)
  })
})

useClickOutside(root, () => {
  open.value = false
})

async function toggle() {
  open.value = !open.value
  if (open.value) {
    search.value = ''
    await nextTick()
    searchInput.value?.focus()
  }
}

function selectCompany(company) {
  tenant.setCurrentCompany(company)
  open.value = false

  if (String(company.id) === String(route.params.id)) return

  const name = route.name && route.name !== 'select-company' ? route.name : 'dashboard'
  router.push({
    name,
    params: { ...route.params, id: String(company.id) },
    query: route.query,
  })
}

function roleLabel(company) {
  return ROLE_LABELS[company.user_role] || 'Miembro'
}
</script>

<template>
  <div ref="root" class="relative">
    <button
      type="button"
      class="flex max-w-full items-center gap-2.5 rounded-md border border-indigo-200 bg-indigo-50/70 px-3 py-1 transition-colors hover:bg-indigo-50 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-1"
      :aria-expanded="open"
      aria-haspopup="listbox"
      @click="toggle"
    >
      <Building2 class="w-4 h-4 shrink-0 text-indigo-600" aria-hidden="true" />
      <span
        class="max-w-[220px] truncate text-xs font-semibold text-indigo-950"
        :title="currentCompany?.legal_name"
      >
        {{ currentCompany?.legal_name || 'Seleccionar empresa' }}
      </span>
      <span
        v-if="currentCompany?.rfc"
        class="hidden rounded border border-indigo-200 bg-white px-1.5 py-0.5 font-mono text-[10px] text-indigo-700 sm:inline"
      >
        {{ currentCompany.rfc }}
      </span>
      <ChevronsUpDown class="w-4 h-4 shrink-0 text-slate-400" aria-hidden="true" />
    </button>

    <div
      v-if="open"
      class="absolute right-0 z-50 mt-2 w-80 overflow-hidden rounded-lg border border-slate-200 bg-white shadow-lg"
      role="listbox"
      aria-label="Seleccionar empresa activa"
    >
      <div class="border-b border-slate-200 p-2">
        <div class="relative">
          <Search
            class="pointer-events-none absolute left-2.5 top-1/2 w-3.5 h-3.5 -translate-y-1/2 text-slate-400"
            aria-hidden="true"
          />
          <input
            ref="searchInput"
            v-model="search"
            type="search"
            class="w-full rounded-md border border-slate-300 bg-white py-1.5 pl-8 pr-2.5 text-xs text-slate-700 placeholder:text-slate-400 focus:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-1"
            placeholder="Buscar por empresa o RFC..."
            aria-label="Buscar empresa"
          />
        </div>
      </div>

      <div class="max-h-64 overflow-y-auto py-1">
        <button
          v-for="company in filteredCompanies"
          :key="company.id"
          type="button"
          class="flex w-full items-start gap-2.5 px-3 py-2 text-left transition-colors hover:bg-slate-50 focus:bg-slate-50 focus:outline-none"
          :class="
            String(company.id) === String(currentCompany?.id)
              ? 'bg-indigo-50/60'
              : ''
          "
          role="option"
          :aria-selected="String(company.id) === String(currentCompany?.id)"
          @click="selectCompany(company)"
        >
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
            v-if="String(company.id) === String(currentCompany?.id)"
            class="mt-0.5 w-4 h-4 shrink-0 text-indigo-600"
            aria-label="Empresa activa"
          />
        </button>

        <p
          v-if="filteredCompanies.length === 0"
          class="px-3 py-6 text-center text-xs text-slate-500"
        >
          No se encontraron empresas con ese criterio.
        </p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { RouterLink, RouterView, useRoute, useRouter } from 'vue-router'
import {
  Bell,
  ChevronDown,
  ChevronRight,
  Landmark,
  Lock,
  LockOpen,
  LogOut,
  PanelLeftClose,
  PanelLeftOpen,
} from 'lucide-vue-next'

import CompanySwitcher from '../components/layout/CompanySwitcher.vue'
import PeriodBanner from '../components/layout/PeriodBanner.vue'
import BaseBadge from '../components/ui/BaseBadge.vue'
import { useActivePeriod } from '../composables/useActivePeriod'
import { useClickOutside } from '../composables/useClickOutside'
import { useRBAC } from '../composables/useRBAC'
import { useToast } from '../composables/useToast'
import { useAuthStore } from '../stores/auth'
import { useTenantStore } from '../stores/tenant'

const COLLAPSE_KEY = 'contable.sidebar_collapsed'

function readCollapsed() {
  try {
    return localStorage.getItem(COLLAPSE_KEY) === '1'
  } catch {
    return false
  }
}

function persistCollapsed(value) {
  try {
    localStorage.setItem(COLLAPSE_KEY, value ? '1' : '0')
  } catch {
    /* noop */
  }
}

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const tenant = useTenantStore()
const { navItems, roleLabel } = useRBAC()
const { periodLabel, isClosed } = useActivePeriod()
const toast = useToast()

const collapsed = ref(readCollapsed())
const userMenuOpen = ref(false)
const userMenuRoot = ref(null)
const loggingOut = ref(false)

useClickOutside(userMenuRoot, () => {
  userMenuOpen.value = false
})

watch(collapsed, (value) => {
  persistCollapsed(value)
})

const company = computed(() => {
  const fromStore = tenant.currentCompany || tenant.companyById(route.params.id)
  if (fromStore) return fromStore

  const membership = auth.membershipFor(route.params.id)
  if (!membership) return null

  return {
    id: membership.company_id,
    legal_name: membership.legal_name,
    rfc: membership.rfc,
    tax_regime: membership.tax_regime,
    user_role: membership.role,
  }
})

const initials = computed(() => {
  const source = auth.fullName || 'Usuario'
  return (
    source
      .split(/\s+/)
      .filter(Boolean)
      .slice(0, 2)
      .map((part) => part.charAt(0))
      .join('')
      .toUpperCase() || 'U'
  )
})

const isActive = (item) => route.name === item.name

async function handleLogout() {
  if (loggingOut.value) return
  loggingOut.value = true
  try {
    await auth.logout()
  } finally {
    tenant.reset()
    loggingOut.value = false
    userMenuOpen.value = false
    toast.success('Sesión cerrada correctamente.')
    router.replace({ name: 'login' })
  }
}
</script>

<template>
  <div class="flex h-screen overflow-hidden bg-slate-50">
    <aside
      class="flex shrink-0 flex-col bg-slate-900 text-slate-300 transition-all duration-200"
      :class="collapsed ? 'w-14' : 'w-56'"
    >
      <div
        class="flex h-12 shrink-0 items-center gap-2 border-b border-slate-800 px-3"
      >
        <div
          class="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-indigo-600"
        >
          <Landmark class="w-4 h-4 text-white" aria-hidden="true" />
        </div>
        <div v-if="!collapsed" class="min-w-0">
          <p class="truncate text-xs font-semibold text-white">Contable MX</p>
          <p class="truncate text-[10px] text-slate-400">Sistema contable</p>
        </div>
      </div>

      <nav class="flex-1 space-y-0.5 overflow-y-auto p-2" aria-label="Navegación principal">
        <RouterLink
          v-for="item in navItems"
          :key="item.name"
          :to="item.to"
          class="flex h-8 items-center rounded-md px-2.5 text-xs font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 focus:ring-offset-slate-900"
          :class="[
            isActive(item)
              ? 'bg-indigo-600 text-white'
              : 'text-slate-300 hover:bg-slate-800 hover:text-white',
            collapsed ? 'justify-center' : 'gap-2',
          ]"
          :title="collapsed ? item.label : undefined"
        >
          <component
            :is="item.icon"
            class="w-4 h-4 shrink-0"
            :class="isActive(item) ? 'text-white' : 'text-slate-400'"
            aria-hidden="true"
          />
          <span v-if="!collapsed" class="truncate">{{ item.label }}</span>
        </RouterLink>
      </nav>

      <div class="shrink-0 border-t border-slate-800 p-2">
        <div
          class="flex items-center rounded-md px-2 py-1.5"
          :class="collapsed ? 'justify-center' : 'gap-2'"
          :title="`Periodo activo: ${periodLabel}`"
        >
          <component
            :is="isClosed ? Lock : LockOpen"
            class="w-4 h-4 shrink-0"
            :class="isClosed ? 'text-amber-500' : 'text-emerald-500'"
            aria-hidden="true"
          />
          <div v-if="!collapsed" class="min-w-0">
            <p class="text-[10px] uppercase tracking-wider text-slate-500">
              Periodo activo
            </p>
            <p class="truncate text-xs font-medium text-slate-200">
              {{ periodLabel }}
            </p>
          </div>
        </div>
      </div>
    </aside>

    <div class="flex min-w-0 flex-1 flex-col">
      <header
        class="flex h-12 shrink-0 items-center gap-3 border-b border-slate-200 bg-white px-4"
      >
        <button
          type="button"
          class="rounded-md p-1.5 text-slate-500 transition-colors hover:bg-slate-100 hover:text-slate-700 focus:outline-none focus:ring-2 focus:ring-indigo-500"
          :aria-label="collapsed ? 'Expandir menú lateral' : 'Colapsar menú lateral'"
          :title="collapsed ? 'Expandir menú lateral' : 'Colapsar menú lateral'"
          @click="collapsed = !collapsed"
        >
          <component
            :is="collapsed ? PanelLeftOpen : PanelLeftClose"
            class="w-4 h-4"
            aria-hidden="true"
          />
        </button>

        <nav
          class="hidden min-w-0 items-center gap-1 text-xs text-slate-500 sm:flex"
          aria-label="Ruta de navegación"
        >
          <RouterLink
            :to="{ name: 'select-company' }"
            class="shrink-0 transition-colors hover:text-slate-700"
          >
            Empresas
          </RouterLink>
          <ChevronRight class="w-3.5 h-3.5 shrink-0 text-slate-400" aria-hidden="true" />
          <RouterLink
            :to="{ name: 'dashboard', params: { id: company?.id } }"
            class="max-w-[220px] truncate transition-colors hover:text-slate-700"
            :title="company?.legal_name"
          >
            {{ company?.legal_name || 'Empresa' }}
          </RouterLink>
          <ChevronRight class="w-3.5 h-3.5 shrink-0 text-slate-400" aria-hidden="true" />
          <span class="truncate font-medium text-slate-700">
            {{ route.meta.title || 'Módulo' }}
          </span>
        </nav>

        <div class="ml-auto flex items-center gap-2">
          <CompanySwitcher />

          <button
            type="button"
            class="hidden cursor-default rounded-md p-1.5 text-slate-400 sm:block"
            title="Notificaciones (próximamente)"
            aria-label="Notificaciones (próximamente)"
            disabled
          >
            <Bell class="w-4 h-4" aria-hidden="true" />
          </button>

          <div ref="userMenuRoot" class="relative">
            <button
              type="button"
              class="flex items-center gap-1.5 rounded-md p-1 transition-colors hover:bg-slate-100 focus:outline-none focus:ring-2 focus:ring-indigo-500"
              :aria-expanded="userMenuOpen"
              aria-haspopup="menu"
              @click="userMenuOpen = !userMenuOpen"
            >
              <span
                class="flex h-7 w-7 items-center justify-center rounded-full bg-indigo-100 text-[11px] font-semibold text-indigo-700"
                aria-hidden="true"
              >
                {{ initials }}
              </span>
              <ChevronDown
                class="hidden w-3.5 h-3.5 text-slate-400 sm:block"
                aria-hidden="true"
              />
            </button>

            <div
              v-if="userMenuOpen"
              class="absolute right-0 z-50 mt-2 w-64 overflow-hidden rounded-lg border border-slate-200 bg-white shadow-lg"
              role="menu"
            >
              <div class="border-b border-slate-200 px-3 py-2.5">
                <p class="truncate text-xs font-semibold text-slate-900">
                  {{ auth.fullName }}
                </p>
                <p class="mt-0.5 truncate text-[11px] text-slate-500">
                  {{ auth.user?.email }}
                </p>
                <div class="mt-1.5">
                  <BaseBadge variant="brand">{{ roleLabel }}</BaseBadge>
                </div>
              </div>
              <button
                type="button"
                class="flex w-full items-center gap-2 px-3 py-2 text-left text-xs font-medium text-slate-700 transition-colors hover:bg-slate-50 focus:bg-slate-50 focus:outline-none"
                role="menuitem"
                :disabled="loggingOut"
                @click="handleLogout"
              >
                <LogOut class="w-4 h-4 text-slate-400" aria-hidden="true" />
                Cerrar sesión
              </button>
            </div>
          </div>
        </div>
      </header>

      <PeriodBanner v-if="isClosed" :period-label="periodLabel" />

      <main class="flex-1 overflow-y-auto p-4">
        <RouterView />
      </main>
    </div>
  </div>
</template>

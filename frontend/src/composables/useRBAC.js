import { computed, markRaw } from 'vue'
import {
  ArrowLeftRight,
  BarChart3,
  CalendarRange,
  FileCode2,
  FileSpreadsheet,
  FolderTree,
  LayoutDashboard,
  ScrollText,
  Users,
} from 'lucide-vue-next'

import { useAuthStore } from '../stores/auth'
import { useTenantStore } from '../stores/tenant'

export const ROLES = {
  PARTNER: 'PARTNER',
  ACCOUNTANT: 'ACCOUNTANT',
  AUDITOR: 'AUDITOR',
  CLIENT: 'CLIENT',
}

export const ROLE_LABELS = {
  [ROLES.PARTNER]: 'Socio / Administrador',
  [ROLES.ACCOUNTANT]: 'Auxiliar contable',
  [ROLES.AUDITOR]: 'Auditor',
  [ROLES.CLIENT]: 'Cliente (portal)',
}

const ALL_ROLES = Object.values(ROLES)
const INTERNAL_ROLES = [ROLES.PARTNER, ROLES.ACCOUNTANT, ROLES.AUDITOR]

/** 05 §3.2: CLIENT solo ve Documentos y Resumen. */
export const NAV_ITEMS = [
  {
    name: 'dashboard',
    label: 'Resumen',
    icon: markRaw(LayoutDashboard),
    roles: ALL_ROLES,
  },
  {
    name: 'documents',
    label: 'Documentos',
    icon: markRaw(FileCode2),
    roles: ALL_ROLES,
  },
  {
    name: 'entries',
    label: 'Pólizas',
    icon: markRaw(FileSpreadsheet),
    roles: INTERNAL_ROLES,
  },
  {
    name: 'periods',
    label: 'Periodos',
    icon: markRaw(CalendarRange),
    roles: INTERNAL_ROLES,
  },
  {
    name: 'accounts',
    label: 'Catálogo de cuentas',
    icon: markRaw(FolderTree),
    roles: INTERNAL_ROLES,
  },
  {
    name: 'reconciliation',
    label: 'Conciliación',
    icon: markRaw(ArrowLeftRight),
    roles: INTERNAL_ROLES,
  },
  {
    name: 'reports',
    label: 'Reportes',
    icon: markRaw(BarChart3),
    roles: INTERNAL_ROLES,
  },
  {
    name: 'audit-log',
    label: 'Bitácora',
    icon: markRaw(ScrollText),
    roles: [ROLES.PARTNER, ROLES.AUDITOR],
  },
  {
    name: 'members',
    label: 'Miembros',
    icon: markRaw(Users),
    roles: [ROLES.PARTNER],
  },
]

export function useRBAC() {
  const auth = useAuthStore()
  const tenant = useTenantStore()

  const currentRole = computed(
    () =>
      auth.roleFor(tenant.currentCompanyId) ||
      tenant.currentCompany?.user_role ||
      null,
  )

  function can(roles) {
    if (!Array.isArray(roles) || roles.length === 0) return true
    return Boolean(currentRole.value) && roles.includes(currentRole.value)
  }

  const navItems = computed(() =>
    NAV_ITEMS.filter((item) => can(item.roles)).map((item) => ({
      ...item,
      to: {
        name: item.name,
        params: { id: tenant.currentCompanyId },
      },
    })),
  )

  const roleLabel = computed(
    () => ROLE_LABELS[currentRole.value] || 'Sin rol en esta empresa',
  )

  const isPartner = computed(() => currentRole.value === ROLES.PARTNER)
  const isAuditor = computed(() => currentRole.value === ROLES.AUDITOR)
  const isClient = computed(() => currentRole.value === ROLES.CLIENT)

  return {
    currentRole,
    roleLabel,
    navItems,
    can,
    isPartner,
    isAuditor,
    isClient,
  }
}

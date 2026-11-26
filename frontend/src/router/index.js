import { createRouter, createWebHistory } from 'vue-router'

import DashboardLayout from '../layouts/DashboardLayout.vue'
import { ROLES } from '../composables/useRBAC'
import { useToast } from '../composables/useToast'
import { useAuthStore } from '../stores/auth'
import { useTenantStore } from '../stores/tenant'
import AccountsView from '../views/AccountsView.vue'
import DocumentsView from '../views/DocumentsView.vue'
import EntriesView from '../views/EntriesView.vue'
import EntryFormView from '../views/EntryFormView.vue'
import LoginView from '../views/LoginView.vue'
import NotFoundView from '../views/NotFoundView.vue'
import PeriodsView from '../views/PeriodsView.vue'
import PlaceholderView from '../views/PlaceholderView.vue'
import SelectCompanyView from '../views/SelectCompanyView.vue'

const ALL_ROLES = Object.values(ROLES)
const INTERNAL_ROLES = [ROLES.PARTNER, ROLES.ACCOUNTANT, ROLES.AUDITOR]

export const routes = [
  {
    path: '/',
    redirect: { name: 'login' },
  },
  {
    path: '/login',
    name: 'login',
    component: LoginView,
    meta: { public: true, title: 'Iniciar sesión' },
  },
  {
    path: '/select-company',
    name: 'select-company',
    component: SelectCompanyView,
    meta: { requiresAuth: true, title: 'Seleccionar empresa' },
  },
  {
    path: '/companies/:id',
    component: DashboardLayout,
    meta: { requiresAuth: true },
    children: [
      {
        path: '',
        redirect: (to) => ({ name: 'dashboard', params: { id: to.params.id } }),
      },
      {
        path: 'dashboard',
        name: 'dashboard',
        component: PlaceholderView,
        meta: {
          title: 'Resumen',
          description:
            'Resumen ejecutivo del periodo: ingresos, egresos, IVA y estado de la contabilidad.',
          roles: ALL_ROLES,
        },
      },
      {
        path: 'documents',
        name: 'documents',
        component: DocumentsView,
        meta: {
          title: 'Documentos',
          description:
            'Bóveda fiscal de CFDI (XML) y representaciones impresas (PDF) de la empresa activa.',
          roles: ALL_ROLES,
        },
      },
      {
        path: 'entries',
        name: 'entries',
        component: EntriesView,
        meta: {
          title: 'Pólizas',
          description:
            'Registro de pólizas de ingreso, egreso y diario con validación de partida doble.',
          roles: INTERNAL_ROLES,
        },
      },
      {
        path: 'entries/new',
        name: 'entry-create',
        component: EntryFormView,
        meta: {
          title: 'Nueva póliza',
          description:
            'Captura de una póliza contable con validación de partida doble.',
          roles: [ROLES.PARTNER, ROLES.ACCOUNTANT],
        },
      },
      {
        path: 'entries/:entryId/edit',
        name: 'entry-edit',
        component: EntryFormView,
        meta: {
          title: 'Editar póliza',
          description:
            'Edición de una póliza contable con validación de partida doble.',
          roles: [ROLES.PARTNER, ROLES.ACCOUNTANT],
        },
      },
      {
        path: 'periods',
        name: 'periods',
        component: PeriodsView,
        meta: {
          title: 'Periodos',
          description:
            'Control de periodos fiscales mensuales, cierre y reapertura con justificación.',
          roles: INTERNAL_ROLES,
        },
      },
      {
        path: 'accounts',
        name: 'accounts',
        component: AccountsView,
        meta: {
          title: 'Catálogo de cuentas',
          description:
            'Catálogo de cuentas contables y agrupadores SAT de la empresa activa.',
          roles: INTERNAL_ROLES,
        },
      },
      {
        path: 'reconciliation',
        name: 'reconciliation',
        component: PlaceholderView,
        meta: {
          title: 'Conciliación bancaria',
          description:
            'Cruce de movimientos bancarios contra pólizas y comprobantes fiscales.',
          roles: INTERNAL_ROLES,
        },
      },
      {
        path: 'reports',
        name: 'reports',
        component: PlaceholderView,
        meta: {
          title: 'Reportes',
          description:
            'Balanza de comprobación y resumen ejecutivo del periodo seleccionado.',
          roles: INTERNAL_ROLES,
        },
      },
      {
        path: 'audit-log',
        name: 'audit-log',
        component: PlaceholderView,
        meta: {
          title: 'Bitácora',
          description:
            'Registro de auditoría de las operaciones realizadas en la empresa activa.',
          roles: [ROLES.PARTNER, ROLES.AUDITOR],
        },
      },
      {
        path: 'members',
        name: 'members',
        component: PlaceholderView,
        meta: {
          title: 'Miembros',
          description:
            'Gestión de usuarios y roles asignados a la empresa activa.',
          roles: [ROLES.PARTNER],
        },
      },
    ],
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'not-found',
    component: NotFoundView,
    meta: { public: true, title: 'Página no encontrada' },
  },
]

function companyFromMembership(membership) {
  if (!membership) return null
  return {
    id: membership.company_id,
    rfc: membership.rfc,
    legal_name: membership.legal_name,
    tax_regime: membership.tax_regime,
    user_role: membership.role,
  }
}

function defaultAuthenticatedRoute(auth, tenant) {
  const current = tenant.currentCompany
  if (current && auth.hasMembership(current.id)) {
    return { name: 'dashboard', params: { id: String(current.id) } }
  }
  return { name: 'select-company' }
}

function safeRedirect(value) {
  if (typeof value !== 'string') return null
  if (!value.startsWith('/') || value.startsWith('//')) return null
  return value
}

export function installGuards(router) {
  router.beforeEach((to) => {
    const auth = useAuthStore()
    const tenant = useTenantStore()

    if (to.name === 'login' && auth.isAuthenticated) {
      const redirect = safeRedirect(to.query.redirect)
      return redirect || defaultAuthenticatedRoute(auth, tenant)
    }

    if (to.meta.requiresAuth && !auth.isAuthenticated) {
      return {
        name: 'login',
        query: to.fullPath && to.fullPath !== '/' ? { redirect: to.fullPath } : {},
      }
    }

    if (to.meta.requiresAuth && to.params.id) {
      const companyId = String(to.params.id)
      const membership = auth.membershipFor(companyId)

      // Deep linking: la URL solo es válida si el usuario pertenece a la empresa.
      if (!membership) {
        return { name: 'select-company' }
      }

      if (String(tenant.currentCompany?.id) !== companyId) {
        const company =
          tenant.companyById(companyId) || companyFromMembership(membership)
        tenant.setCurrentCompany(company)
      }

      const role = membership.role || tenant.roleFor(companyId)
      if (
        Array.isArray(to.meta.roles) &&
        to.meta.roles.length > 0 &&
        !to.meta.roles.includes(role)
      ) {
        useToast().warning('No tienes permisos para acceder a este módulo.')
        return { name: 'dashboard', params: { id: companyId } }
      }
    }

    return true
  })

  router.afterEach((to) => {
    if (typeof document === 'undefined') return
    document.title = to.meta.title ? `${to.meta.title} · Contable MX` : 'Contable MX'
  })
}

export function createAppRouter(history = createWebHistory()) {
  const router = createRouter({
    history,
    routes,
    scrollBehavior: () => ({ top: 0 }),
  })
  installGuards(router)
  return router
}

const router = createAppRouter()
export default router

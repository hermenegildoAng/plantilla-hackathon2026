import { beforeEach, describe, expect, it } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory } from 'vue-router'

import { createAppRouter } from '../index'
import { useAuthStore } from '../../stores/auth'
import { useTenantStore } from '../../stores/tenant'

function setSession(role = 'PARTNER', companyId = 1) {
  const auth = useAuthStore()
  auth.$patch({
    accessToken: 'access-token',
    refreshToken: 'refresh-token',
    user: { id: 10, email: 'demo@despacho.mx', full_name: 'Demo User' },
    memberships: [
      {
        company_id: companyId,
        rfc: 'CNO200101AB9',
        legal_name: 'Comercial del Norte',
        tax_regime: '601',
        role,
      },
    ],
  })

  const tenant = useTenantStore()
  tenant.$patch({
    companies: [
      {
        id: companyId,
        rfc: 'CNO200101AB9',
        legal_name: 'Comercial del Norte',
        tax_regime: '601',
        tax_regime_display: '601 - General de Ley Personas Morales',
        user_role: role,
      },
    ],
    currentCompany: null,
    currentCompanyId: null,
  })

  return { auth, tenant }
}

function makeRouter() {
  return createAppRouter(createMemoryHistory())
}

describe('router guards', () => {
  beforeEach(() => {
    localStorage.clear()
    setActivePinia(createPinia())
  })

  it('redirige a login preservando el destino cuando no hay sesión', async () => {
    const router = makeRouter()

    await router.push('/companies/1/dashboard')

    expect(router.currentRoute.value.name).toBe('login')
    expect(router.currentRoute.value.query.redirect).toBe(
      '/companies/1/dashboard',
    )
  })

  it('valida el deep link contra memberships y sincroniza la empresa activa', async () => {
    const { tenant } = setSession('PARTNER', 1)
    const router = makeRouter()

    await router.push('/companies/1/documents')

    expect(router.currentRoute.value.name).toBe('documents')
    expect(tenant.currentCompanyId).toBe('1')
    expect(tenant.currentCompany.legal_name).toBe('Comercial del Norte')
  })

  it('rechaza un deep link a una empresa sin membresía', async () => {
    setSession('PARTNER', 1)
    const router = makeRouter()

    await router.push('/companies/99/dashboard')

    expect(router.currentRoute.value.name).toBe('select-company')
  })

  it('CLIENT no puede entrar a módulos internos', async () => {
    setSession('CLIENT', 1)
    const router = makeRouter()

    await router.push('/companies/1/entries')

    expect(router.currentRoute.value.name).toBe('dashboard')
    expect(router.currentRoute.value.params.id).toBe('1')
  })

  it('CLIENT sí puede entrar a documentos y resumen', async () => {
    setSession('CLIENT', 1)
    const router = makeRouter()

    await router.push('/companies/1/documents')
    expect(router.currentRoute.value.name).toBe('documents')

    await router.push('/companies/1/dashboard')
    expect(router.currentRoute.value.name).toBe('dashboard')
  })

  it('AUDITOR puede entrar a la bitácora, pero no a miembros', async () => {
    setSession('AUDITOR', 1)
    const router = makeRouter()

    await router.push('/companies/1/audit-log')
    expect(router.currentRoute.value.name).toBe('audit-log')

    await router.push('/companies/1/members')
    expect(router.currentRoute.value.name).toBe('dashboard')
  })

  it('un usuario autenticado que abre /login vuelve a la selección o al resumen', async () => {
    setSession('PARTNER', 1)
    const router = makeRouter()

    await router.push('/login')

    expect(router.currentRoute.value.name).toBe('select-company')
  })

  it('un usuario autenticado con empresa persistida vuelve al resumen', async () => {
    const { tenant } = setSession('PARTNER', 1)
    tenant.setCurrentCompany(tenant.companies[0])
    const router = makeRouter()

    await router.push('/login')

    expect(router.currentRoute.value.name).toBe('dashboard')
    expect(router.currentRoute.value.params.id).toBe('1')
  })

  it('preserva el destino al abrir /login ya autenticado', async () => {
    setSession('PARTNER', 1)
    const router = makeRouter()

    await router.push('/login?redirect=/companies/1/documents')

    expect(router.currentRoute.value.name).toBe('documents')
    expect(router.currentRoute.value.params.id).toBe('1')
  })
})

import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'
import { createMemoryHistory } from 'vue-router'

import App from '../../App.vue'
import { createAppRouter } from '../../router'
import { useAuthStore } from '../../stores/auth'
import { useTenantStore } from '../../stores/tenant'

function setSession(role) {
  const auth = useAuthStore()
  auth.$patch({
    accessToken: 'access-token',
    refreshToken: 'refresh-token',
    user: {
      id: 10,
      email: 'cliente@despacho.mx',
      full_name: 'Cliente Demo',
    },
    memberships: [
      {
        company_id: 1,
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
        id: 1,
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
}

describe('DashboardLayout shell', () => {
  let pinia

  beforeEach(() => {
    localStorage.clear()
    pinia = createPinia()
    setActivePinia(pinia)
  })

  it('muestra el selector de empresa, breadcrumbs y menú filtrado por rol', async () => {
    setSession('CLIENT')

    const router = createAppRouter(createMemoryHistory())
    await router.push('/companies/1/dashboard')

    const wrapper = mount(App, {
      global: { plugins: [pinia, router] },
    })
    await flushPromises()

    const text = wrapper.text()
    expect(text).toContain('Comercial del Norte')
    expect(text).toContain('CNO200101AB9')
    expect(text).toContain('Resumen')
    expect(text).toContain('Documentos')
    expect(text).toContain('Periodo activo')
    expect(text).not.toContain('Bitácora')
    expect(text).not.toContain('Miembros')
    expect(text).not.toContain('Timbrar')

    wrapper.unmount()
  })
})

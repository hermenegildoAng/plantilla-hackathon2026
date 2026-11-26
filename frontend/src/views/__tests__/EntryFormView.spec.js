import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory } from 'vue-router'

import { createAppRouter } from '../../router'
import { useAuthStore } from '../../stores/auth'
import { useTenantStore } from '../../stores/tenant'
import EntryFormView from '../EntryFormView.vue'

vi.mock('../../api/accounting', () => ({
  listAllPeriods: vi.fn(async () => ({
    results: [{ id: 11, year: 2026, month: 11, is_closed: false }],
  })),
  listAllAccounts: vi.fn(async () => ({ results: [] })),
  getEntry: vi.fn(),
  createEntry: vi.fn(),
  updateEntry: vi.fn(),
}))

vi.mock('../../api/documents', () => ({
  listAllDocuments: vi.fn(async () => ({ results: [] })),
}))

function setSession() {
  const auth = useAuthStore()
  auth.$patch({
    accessToken: 'access-token',
    refreshToken: 'refresh-token',
    user: {
      id: 10,
      email: 'socio@despacho.mx',
      full_name: 'Socio Demo',
    },
    memberships: [
      {
        company_id: 1,
        rfc: 'CNO200101AB9',
        legal_name: 'Comercial del Norte',
        tax_regime: '601',
        role: 'PARTNER',
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
        user_role: 'PARTNER',
      },
    ],
    currentCompany: {
      id: 1,
      rfc: 'CNO200101AB9',
      legal_name: 'Comercial del Norte',
      tax_regime: '601',
      user_role: 'PARTNER',
    },
    currentCompanyId: '1',
  })
}

describe('EntryFormView', () => {
  let pinia

  beforeEach(() => {
    localStorage.clear()
    pinia = createPinia()
    setActivePinia(pinia)
  })

  it('deshabilita Guardar mientras la póliza no está cuadrada', async () => {
    setSession()
    const router = createAppRouter(createMemoryHistory())
    await router.push('/companies/1/entries/new')

    const wrapper = mount(EntryFormView, {
      global: { plugins: [pinia, router] },
    })
    await flushPromises()

    const saveButtons = wrapper
      .findAll('button')
      .filter((button) => button.text().includes('Guardar póliza'))

    expect(saveButtons.length).toBeGreaterThan(0)
    saveButtons.forEach((button) => {
      expect(button.attributes('disabled')).toBeDefined()
    })

    wrapper.unmount()
  })
})

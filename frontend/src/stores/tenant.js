import { defineStore } from 'pinia'

import { api } from '../api/http'

const KEYS = {
  companies: 'contable.companies',
  currentCompany: 'contable.current_company',
  currentCompanyId: 'contable.current_company_id',
}

export const TAX_REGIME_LABELS = {
  601: '601 - General de Ley Personas Morales',
  612: '612 - Personas Físicas con Actividades Empresariales y Profesionales',
  626: '626 - Régimen Simplificado de Confianza',
}

function readStorage(key, fallback) {
  if (typeof window === 'undefined') return fallback
  try {
    const raw = window.localStorage.getItem(key)
    return raw ? JSON.parse(raw) : fallback
  } catch {
    return fallback
  }
}

function writeStorage(key, value) {
  if (typeof window === 'undefined') return
  try {
    window.localStorage.setItem(key, value)
  } catch {
    /* noop */
  }
}

function removeStorage(key) {
  if (typeof window === 'undefined') return
  try {
    window.localStorage.removeItem(key)
  } catch {
    /* noop */
  }
}

function normalizeCompany(company) {
  if (!company) return null
  const id = company.id ?? company.company_id
  return {
    ...company,
    id,
    tax_regime_display:
      company.tax_regime_display ||
      TAX_REGIME_LABELS[company.tax_regime] ||
      company.tax_regime ||
      '',
  }
}

function uniqueCompanies(companies) {
  const byId = new Map()
  companies.forEach((company) => {
    const normalized = normalizeCompany(company)
    if (normalized?.id === null || normalized?.id === undefined) return
    byId.set(String(normalized.id), normalized)
  })
  return Array.from(byId.values()).sort((a, b) =>
    String(a.legal_name || '').localeCompare(String(b.legal_name || ''), 'es'),
  )
}

export const useTenantStore = defineStore('tenant', {
  state: () => {
    const currentCompany = normalizeCompany(readStorage(KEYS.currentCompany, null))
    return {
      companies: uniqueCompanies(readStorage(KEYS.companies, [])),
      currentCompany,
      currentCompanyId: currentCompany ? String(currentCompany.id) : null,
      loading: false,
    }
  },

  getters: {
    hasCompanies: (state) => state.companies.length > 0,
    companyById: (state) => (id) =>
      state.companies.find((company) => String(company.id) === String(id)) || null,
    roleFor: (state) => (id) => {
      const company =
        state.companies.find((item) => String(item.id) === String(id)) || null
      return company?.user_role || null
    },
  },

  actions: {
    persist() {
      writeStorage(KEYS.companies, JSON.stringify(this.companies))
      if (this.currentCompany) {
        writeStorage(KEYS.currentCompany, JSON.stringify(this.currentCompany))
        writeStorage(KEYS.currentCompanyId, String(this.currentCompany.id))
      } else {
        removeStorage(KEYS.currentCompany)
        removeStorage(KEYS.currentCompanyId)
      }
    },

    /** Convierte las membresías del login en empresas seleccionables. */
    syncFromMemberships(memberships = []) {
      if (!Array.isArray(memberships) || memberships.length === 0) return
      const fromMemberships = memberships.map((membership) =>
        normalizeCompany({
          id: membership.company_id,
          rfc: membership.rfc,
          legal_name: membership.legal_name,
          tax_regime: membership.tax_regime,
          currency: 'MXN',
          user_role: membership.role,
        }),
      )
      this.companies = uniqueCompanies([...this.companies, ...fromMemberships])

      if (this.currentCompany) {
        const refreshed = this.companyById(this.currentCompany.id)
        if (refreshed) this.currentCompany = refreshed
        else this.clearCurrentCompany()
      }
      this.persist()
    },

    async fetchCompanies() {
      if (this.loading) return this.companies
      this.loading = true
      try {
        const payload = await api.get('/companies/')
        const results = Array.isArray(payload) ? payload : payload?.results || []
        this.companies = uniqueCompanies([...this.companies, ...results])
        if (this.currentCompany) {
          const refreshed = this.companyById(this.currentCompany.id)
          this.currentCompany = refreshed || null
          if (!refreshed) this.currentCompanyId = null
        }
        this.persist()
        return this.companies
      } finally {
        this.loading = false
      }
    },

    setCurrentCompany(company) {
      const normalized =
        typeof company === 'object' && company !== null
          ? normalizeCompany(company)
          : this.companyById(company)

      if (!normalized) return false

      if (!this.companyById(normalized.id)) {
        this.companies = uniqueCompanies([...this.companies, normalized])
      }

      this.currentCompany = normalized
      this.currentCompanyId = String(normalized.id)
      this.persist()
      return true
    },

    clearCurrentCompany() {
      this.currentCompany = null
      this.currentCompanyId = null
      removeStorage(KEYS.currentCompany)
      removeStorage(KEYS.currentCompanyId)
    },

    removeCompany(companyId) {
      this.companies = this.companies.filter(
        (company) => String(company.id) !== String(companyId),
      )
      if (String(this.currentCompany?.id) === String(companyId)) {
        this.clearCurrentCompany()
      }
      this.persist()
    },

    reset() {
      this.companies = []
      this.currentCompany = null
      this.currentCompanyId = null
      Object.values(KEYS).forEach(removeStorage)
    },
  },
})

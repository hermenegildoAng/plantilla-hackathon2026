import { defineStore } from 'pinia'

import { api } from '../api/http'

const KEYS = {
  accessToken: 'contable.access_token',
  refreshToken: 'contable.refresh_token',
  user: 'contable.user',
  memberships: 'contable.memberships',
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

function readToken(key) {
  if (typeof window === 'undefined') return ''
  try {
    return window.localStorage.getItem(key) || ''
  } catch {
    return ''
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

export const useAuthStore = defineStore('auth', {
  state: () => ({
    accessToken: readToken(KEYS.accessToken),
    refreshToken: readToken(KEYS.refreshToken),
    user: readStorage(KEYS.user, null),
    memberships: readStorage(KEYS.memberships, []),
  }),

  getters: {
    isAuthenticated: (state) => Boolean(state.accessToken),
    fullName: (state) => state.user?.full_name || state.user?.email || 'Usuario',
    membershipCount: (state) => state.memberships.length,
  },

  actions: {
    persist() {
      if (this.accessToken) writeStorage(KEYS.accessToken, this.accessToken)
      else removeStorage(KEYS.accessToken)

      if (this.refreshToken) writeStorage(KEYS.refreshToken, this.refreshToken)
      else removeStorage(KEYS.refreshToken)

      if (this.user) writeStorage(KEYS.user, JSON.stringify(this.user))
      else removeStorage(KEYS.user)

      writeStorage(KEYS.memberships, JSON.stringify(this.memberships || []))
    },

    setSession({ tokens, user, memberships }) {
      this.accessToken = tokens?.access || ''
      this.refreshToken = tokens?.refresh || ''
      this.user = user || null
      this.memberships = Array.isArray(memberships) ? memberships : []
      this.persist()
    },

    setTokens({ access, refresh }) {
      if (access) this.accessToken = access
      if (refresh) this.refreshToken = refresh
      this.persist()
    },

    async login({ email, password }) {
      const session = await api.post(
        '/auth/login/',
        { email: email.trim().toLowerCase(), password },
        { skipAuth: true, skipAuthRefresh: true },
      )

      this.setSession({
        tokens: session?.tokens,
        user: session?.user,
        memberships: session?.memberships,
      })
      return session
    },

    async fetchMe() {
      const session = await api.get('/auth/me/')
      if (session?.user) this.user = session.user
      if (Array.isArray(session?.memberships)) this.memberships = session.memberships
      this.persist()
      return session
    },

    async logout({ notifyServer = true } = {}) {
      const refresh = this.refreshToken
      if (notifyServer && refresh) {
        try {
          await api.post('/auth/logout/', { refresh })
        } catch {
          // El cierre local siempre debe completarse, aunque el token ya no
          // exista en la lista negra del backend.
        }
      }
      this.clear()
    },

    clear() {
      this.accessToken = ''
      this.refreshToken = ''
      this.user = null
      this.memberships = []
      Object.values(KEYS).forEach(removeStorage)
    },

    hasMembership(companyId) {
      if (companyId === null || companyId === undefined) return false
      return this.memberships.some(
        (membership) => String(membership.company_id) === String(companyId),
      )
    },

    removeMembership(companyId) {
      this.memberships = this.memberships.filter(
        (membership) => String(membership.company_id) !== String(companyId),
      )
      this.persist()
    },

    membershipFor(companyId) {
      if (companyId === null || companyId === undefined) return null
      return (
        this.memberships.find(
          (membership) => String(membership.company_id) === String(companyId),
        ) || null
      )
    },

    roleFor(companyId) {
      return this.membershipFor(companyId)?.role || null
    },

    hasRole(companyId, roles) {
      if (!Array.isArray(roles) || roles.length === 0) return true
      return roles.includes(this.roleFor(companyId))
    },
  },
})

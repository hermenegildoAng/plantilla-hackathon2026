import axios from 'axios'

/**
 * Cliente HTTP central del frontend.
 *
 * Responsabilidades (05 §1, E-08, E-23):
 *  - Inyectar `Authorization: Bearer` y `X-Company-ID`.
 *  - Desempaquetar el envoltorio estándar de la API.
 *  - Renovar el token una sola vez, encolando las peticiones concurrentes.
 *  - Traducir 401 / 403 / 5xx a acciones de sesión y mensajes en español.
 *
 * La integración con Pinia y el router se hace por inyección (`configureHttp`)
 * para evitar dependencias circulares entre el cliente y los stores.
 */

export const STORAGE_KEYS = {
  accessToken: 'contable.access_token',
  refreshToken: 'contable.refresh_token',
  currentCompanyId: 'contable.current_company_id',
}

const API_BASE_URL = import.meta.env?.VITE_API_BASE_URL || '/api/v1'

export class ApiError extends Error {
  constructor(message, { status = null, code = null, errors = [], errorId = null, cause } = {}) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.errors = errors
    this.errorId = errorId
    this.cause = cause
  }

  /** Errores indexados por campo, útil para formularios. */
  get fieldErrors() {
    return this.errors.reduce((accumulator, item) => {
      if (!item?.field) return accumulator
      accumulator[item.field] = item.message
      return accumulator
    }, {})
  }
}

const STATUS_MESSAGES = {
  400: 'La solicitud contiene datos inválidos.',
  401: 'Tu sesión expiró o no es válida.',
  403: 'No tienes permisos para realizar esta acción.',
  404: 'El recurso solicitado no existe.',
  405: 'La operación no está permitida.',
  409: 'La operación entra en conflicto con el estado actual.',
  429: 'Demasiados intentos. Espera un momento e inténtalo de nuevo.',
  500: 'Ocurrió un error inesperado. Contacta a soporte técnico.',
}

function safeStorageGet(key) {
  if (typeof window === 'undefined') return null
  try {
    return window.localStorage.getItem(key)
  } catch {
    return null
  }
}

function safeStorageSet(key, value) {
  if (typeof window === 'undefined') return
  try {
    window.localStorage.setItem(key, value)
  } catch {
    /* El almacenamiento puede estar bloqueado por el navegador. */
  }
}

function safeStorageRemove(key) {
  if (typeof window === 'undefined') return
  try {
    window.localStorage.removeItem(key)
  } catch {
    /* noop */
  }
}

function defaultNavigate(path) {
  if (typeof window === 'undefined') return
  if (window.location.pathname === path) return
  window.location.assign(path)
}

const defaultHandlers = {
  getAccessToken: () => safeStorageGet(STORAGE_KEYS.accessToken),
  getRefreshToken: () => safeStorageGet(STORAGE_KEYS.refreshToken),
  getCompanyId: () => safeStorageGet(STORAGE_KEYS.currentCompanyId),
  onTokensRefreshed: ({ access, refresh }) => {
    safeStorageSet(STORAGE_KEYS.accessToken, access)
    if (refresh) safeStorageSet(STORAGE_KEYS.refreshToken, refresh)
  },
  onAuthFailure: () => {
    safeStorageRemove(STORAGE_KEYS.accessToken)
    safeStorageRemove(STORAGE_KEYS.refreshToken)
    defaultNavigate('/login')
  },
  onTenantAccessDenied: () => {
    safeStorageRemove(STORAGE_KEYS.currentCompanyId)
    defaultNavigate('/select-company')
  },
  onRolePermissionDenied: () => {},
  onServerError: () => {},
}

let handlers = { ...defaultHandlers }
let refreshPromise = null
let authFailureNotified = false

/** Permite que `main.js` conecte los stores y el router al cliente HTTP. */
export function configureHttp(overrides = {}) {
  handlers = { ...handlers, ...overrides }
}

/** Restablece la configuración por defecto. Pensado para pruebas. */
export function resetHttpConfig() {
  handlers = { ...defaultHandlers }
  refreshPromise = null
  authFailureNotified = false
}

export const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: { Accept: 'application/json' },
})

function setHeader(config, name, value) {
  if (config.headers?.set) {
    config.headers.set(name, value)
    return
  }
  config.headers = { ...(config.headers || {}), [name]: value }
}

function isAuthEndpoint(url = '') {
  return url.includes('/auth/')
}

function isRefreshExempt(url = '') {
  return (
    url.includes('/auth/login/') ||
    url.includes('/auth/refresh/') ||
    url.includes('/auth/logout/')
  )
}

function isEnvelope(payload) {
  return (
    payload !== null &&
    typeof payload === 'object' &&
    !Array.isArray(payload) &&
    'success' in payload &&
    'data' in payload
  )
}

function extractErrors(body) {
  if (Array.isArray(body?.errors)) {
    return body.errors.map((item) => ({
      field: item?.field ?? null,
      code: item?.code ?? 'error',
      message: String(item?.message ?? ''),
    }))
  }

  // Compatibilidad defensiva: la errata E-02 exige arreglo, pero nunca se
  // muestra un objeto crudo al usuario si un backend antiguo responde así.
  if (body?.errors && typeof body.errors === 'object') {
    return Object.entries(body.errors).flatMap(([field, value]) => {
      const messages = Array.isArray(value) ? value : [value]
      return messages.map((message) => ({
        field: field === 'non_field_errors' ? null : field,
        code: 'validation_error',
        message: String(message),
      }))
    })
  }

  return []
}

function primaryCode(body, errors, status) {
  return (
    body?.code ||
    errors.find((item) => item.code)?.code ||
    (status === 401 ? 'authentication_failed' : null) ||
    (status === 403 ? 'role_permission_denied' : null) ||
    (status === 404 ? 'not_found' : null) ||
    (status === 429 ? 'throttled' : null) ||
    (status >= 500 ? 'internal_server_error' : 'error')
  )
}

function buildApiError(error) {
  const response = error?.response
  if (!response) {
    return new ApiError(
      'No se pudo conectar con el servidor. Verifica tu conexión e inténtalo de nuevo.',
      { code: 'network_error', cause: error },
    )
  }

  const body = response.data && typeof response.data === 'object' ? response.data : {}
  const errors = extractErrors(body)
  const status = response.status
  const firstErrorMessage = errors.find((item) => item.message)?.message
  const message =
    (status >= 500 ? body.message || firstErrorMessage : firstErrorMessage || body.message) ||
    STATUS_MESSAGES[status] ||
    'No se pudo completar la solicitud.'

  return new ApiError(message, {
    status,
    code: primaryCode(body, errors, status),
    errors,
    errorId: body.error_id ?? null,
    cause: error,
  })
}

function notifyAuthFailure() {
  if (authFailureNotified) return
  authFailureNotified = true
  handlers.onAuthFailure()
}

function handleServerError(error) {
  const apiError = buildApiError(error)
  handlers.onServerError({
    message: apiError.message,
    errorId: apiError.errorId,
    error: apiError,
  })
  return apiError
}

async function performRefresh() {
  const refresh = handlers.getRefreshToken()
  if (!refresh) {
    throw new ApiError('No hay una sesión que renovar.', {
      status: 401,
      code: 'authentication_failed',
    })
  }

  // Se usa la misma instancia con `skipAuthRefresh` para no entrar en un ciclo
  // si el refresh token también expiró. La respuesta llega ya desempaquetada.
  const tokens = await api.post(
    '/auth/refresh/',
    { refresh },
    { skipAuth: true, skipAuthRefresh: true },
  )

  if (!tokens?.access) {
    throw new ApiError('No fue posible renovar la sesión.', {
      status: 401,
      code: 'authentication_failed',
    })
  }

  handlers.onTokensRefreshed({
    access: tokens.access,
    refresh: tokens.refresh || refresh,
  })
  authFailureNotified = false
  return tokens.access
}

/**
 * Una sola promesa compartida: las peticiones concurrentes que reciben 401 se
 * encolan esperando el mismo refresh en lugar de disparar N renovaciones.
 */
function refreshAccessToken() {
  if (!refreshPromise) {
    refreshPromise = performRefresh().finally(() => {
      refreshPromise = null
    })
  }
  return refreshPromise
}

api.interceptors.request.use((config) => {
  const token = handlers.getAccessToken()
  const alreadyHasAuth =
    config._retry &&
    Boolean(
      (typeof config.headers?.get === 'function'
        ? config.headers.get('Authorization')
        : config.headers?.Authorization) || null,
    )

  if (token && !config.skipAuth && !alreadyHasAuth) {
    setHeader(config, 'Authorization', `Bearer ${token}`)
  }

  const companyId = handlers.getCompanyId()
  if (companyId && !config.skipCompanyHeader && !isAuthEndpoint(config.url)) {
    setHeader(config, 'X-Company-ID', String(companyId))
  }

  return config
})

api.interceptors.response.use(
  (response) => {
    authFailureNotified = false
    if (response.status === 204 || response.data == null) return null
    if (isEnvelope(response.data)) return response.data.data
    return response.data
  },
  async (error) => {
    const status = error?.response?.status
    const original = error?.config || {}
    const apiError = buildApiError(error)

    if (status === 401 && !original.skipAuthRefresh && !isRefreshExempt(original.url)) {
      if (original._retry) {
        notifyAuthFailure()
        return Promise.reject(apiError)
      }

      original._retry = true
      try {
        const access = await refreshAccessToken()
        setHeader(original, 'Authorization', `Bearer ${access}`)
        return api(original)
      } catch {
        notifyAuthFailure()
        return Promise.reject(apiError)
      }
    }

    if (status === 403) {
      if (apiError.code === 'tenant_access_denied') {
        handlers.onTenantAccessDenied({ message: apiError.message, error: apiError })
      } else if (apiError.code === 'role_permission_denied') {
        handlers.onRolePermissionDenied({
          message: apiError.message,
          error: apiError,
        })
      }
    }

    if (status >= 500) {
      return Promise.reject(handleServerError(error))
    }

    return Promise.reject(apiError)
  },
)

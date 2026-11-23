import MockAdapter from 'axios-mock-adapter'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { api, configureHttp, resetHttpConfig } from '../http'

function envelope(data, message = 'Consulta exitosa.') {
  return { success: true, message, data, errors: null }
}

function errorEnvelope(code, message = 'Ocurrió un error.', errorId = null) {
  return {
    success: false,
    message,
    error_id: errorId,
    data: null,
    errors: [{ field: null, code, message }],
  }
}

function header(headers, name) {
  if (typeof headers?.get === 'function') return headers.get(name)
  return headers?.[name]
}

describe('api/http.js', () => {
  let mock
  let accessToken
  let handlers

  beforeEach(() => {
    resetHttpConfig()
    accessToken = 'access-1'
    handlers = {
      getAccessToken: () => accessToken,
      getRefreshToken: () => 'refresh-1',
      getCompanyId: () => 42,
      onTokensRefreshed: vi.fn(({ access }) => {
        accessToken = access
      }),
      onAuthFailure: vi.fn(),
      onTenantAccessDenied: vi.fn(),
      onRolePermissionDenied: vi.fn(),
      onServerError: vi.fn(),
    }
    configureHttp(handlers)
    mock = new MockAdapter(api)
  })

  afterEach(() => {
    mock.restore()
    resetHttpConfig()
  })

  it('inyecta Authorization y X-Company-ID y desempaqueta el envoltorio', async () => {
    let captured

    mock.onGet('/secure').reply((config) => {
      captured = config
      return [200, envelope({ ok: true })]
    })

    const result = await api.get('/secure')

    expect(result).toEqual({ ok: true })
    expect(header(captured.headers, 'Authorization')).toBe('Bearer access-1')
    expect(header(captured.headers, 'X-Company-ID')).toBe('42')
  })

  it('no envía X-Company-ID en endpoints de autenticación', async () => {
    let captured

    mock.onPost('/auth/login/').reply((config) => {
      captured = config
      return [200, envelope({ tokens: {} })]
    })

    await api.post('/auth/login/', { email: 'demo@example.com', password: 'x' })

    expect(header(captured.headers, 'X-Company-ID')).toBeUndefined()
  })

  it('en un 401 refresca una sola vez y reintenta con el token nuevo', async () => {
    let calls = 0

    mock.onGet('/secure').reply(() => {
      calls += 1
      if (calls === 1) {
        return [401, errorEnvelope('authentication_failed')]
      }
      return [200, envelope({ ok: true, calls })]
    })
    mock
      .onPost('/auth/refresh/')
      .reply(200, envelope({ access: 'new-access', refresh: 'new-refresh' }))

    const result = await api.get('/secure')

    expect(result).toEqual({ ok: true, calls: 2 })
    expect(handlers.onTokensRefreshed).toHaveBeenCalledWith({
      access: 'new-access',
      refresh: 'new-refresh',
    })
    expect(mock.history.post).toHaveLength(1)
    expect(header(mock.history.get[1].headers, 'Authorization')).toBe(
      'Bearer new-access',
    )
    expect(handlers.onAuthFailure).not.toHaveBeenCalled()
  })

  it('encola peticiones concurrentes y comparte un único refresh', async () => {
    let protectedCalls = 0

    mock.onGet('/secure').reply(() => {
      protectedCalls += 1
      if (protectedCalls <= 2) {
        return [401, errorEnvelope('authentication_failed')]
      }
      return [200, envelope({ ok: true })]
    })

    mock.onPost('/auth/refresh/').reply(async () => {
      await new Promise((resolve) => setTimeout(resolve, 10))
      return [200, envelope({ access: 'new-access', refresh: 'new-refresh' })]
    })

    const [first, second] = await Promise.all([
      api.get('/secure'),
      api.get('/secure'),
    ])

    expect(first).toEqual({ ok: true })
    expect(second).toEqual({ ok: true })
    expect(mock.history.post).toHaveLength(1)
    expect(handlers.onTokensRefreshed).toHaveBeenCalledTimes(1)
  })

  it('si el refresh falla cierra la sesión una sola vez', async () => {
    mock.onGet('/secure').reply(401, errorEnvelope('authentication_failed'))
    mock.onPost('/auth/refresh/').reply(401, errorEnvelope('token_not_valid'))

    await expect(api.get('/secure')).rejects.toMatchObject({ status: 401 })

    expect(handlers.onAuthFailure).toHaveBeenCalledTimes(1)
    expect(handlers.onRolePermissionDenied).not.toHaveBeenCalled()
  })

  it('si el reintento vuelve a responder 401 hace logout sin un segundo refresh', async () => {
    mock.onGet('/secure').reply(401, errorEnvelope('authentication_failed'))
    mock
      .onPost('/auth/refresh/')
      .reply(200, envelope({ access: 'new-access', refresh: 'new-refresh' }))

    await expect(api.get('/secure')).rejects.toMatchObject({ status: 401 })

    expect(mock.history.get).toHaveLength(2)
    expect(mock.history.post).toHaveLength(1)
    expect(handlers.onAuthFailure).toHaveBeenCalledTimes(1)
  })

  it('también refresca el token en /auth/me/', async () => {
    let calls = 0

    mock.onGet('/auth/me/').reply(() => {
      calls += 1
      if (calls === 1) {
        return [401, errorEnvelope('authentication_failed')]
      }
      return [200, envelope({ user: { email: 'demo@despacho.mx' } })]
    })
    mock
      .onPost('/auth/refresh/')
      .reply(200, envelope({ access: 'new-access', refresh: 'new-refresh' }))

    const result = await api.get('/auth/me/')

    expect(result.user.email).toBe('demo@despacho.mx')
    expect(mock.history.post).toHaveLength(1)
  })

  it('en 403 tenant_access_denied limpia el tenant', async () => {
    mock.onGet('/secure').reply(
      403,
      errorEnvelope(
        'tenant_access_denied',
        'No tiene permisos para operar sobre esta empresa.',
      ),
    )

    await expect(api.get('/secure')).rejects.toMatchObject({
      status: 403,
      code: 'tenant_access_denied',
    })

    expect(handlers.onTenantAccessDenied).toHaveBeenCalledTimes(1)
    expect(handlers.onRolePermissionDenied).not.toHaveBeenCalled()
  })

  it('en 403 role_permission_denied solo muestra el aviso de permisos', async () => {
    mock.onGet('/secure').reply(
      403,
      errorEnvelope(
        'role_permission_denied',
        'No tiene permisos para realizar esta acción.',
      ),
    )

    await expect(api.get('/secure')).rejects.toMatchObject({
      status: 403,
      code: 'role_permission_denied',
    })

    expect(handlers.onRolePermissionDenied).toHaveBeenCalledWith(
      expect.objectContaining({
        message: 'No tiene permisos para realizar esta acción.',
      }),
    )
    expect(handlers.onTenantAccessDenied).not.toHaveBeenCalled()
  })

  it('en 500 informa el mensaje junto con el error_id', async () => {
    mock.onGet('/secure').reply(
      500,
      errorEnvelope(
        'internal_server_error',
        'Error interno del servidor.',
        'a1b2c3d4-e5f6-7890-abcd-ef0123456789',
      ),
    )

    await expect(api.get('/secure')).rejects.toMatchObject({
      status: 500,
      code: 'internal_server_error',
      errorId: 'a1b2c3d4-e5f6-7890-abcd-ef0123456789',
    })

    expect(handlers.onServerError).toHaveBeenCalledWith(
      expect.objectContaining({
        message: 'Error interno del servidor.',
        errorId: 'a1b2c3d4-e5f6-7890-abcd-ef0123456789',
      }),
    )
  })
})

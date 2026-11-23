import '@fontsource/inter/latin-400.css'
import '@fontsource/inter/latin-500.css'
import '@fontsource/inter/latin-600.css'
import '@fontsource/inter/latin-700.css'
import './assets/main.css'

import { createApp } from 'vue'
import { createPinia } from 'pinia'

import App from './App.vue'
import { configureHttp } from './api/http'
import { useToast } from './composables/useToast'
import router from './router'
import { useAuthStore } from './stores/auth'
import { useTenantStore } from './stores/tenant'

async function bootstrap() {
  const app = createApp(App)
  const pinia = createPinia()
  app.use(pinia)

  const auth = useAuthStore(pinia)
  const tenant = useTenantStore(pinia)
  const toast = useToast()

  configureHttp({
    getAccessToken: () => auth.accessToken,
    getRefreshToken: () => auth.refreshToken,
    getCompanyId: () => tenant.currentCompanyId,
    onTokensRefreshed: ({ access, refresh }) => {
      auth.setTokens({ access, refresh })
    },
    onAuthFailure: () => {
      const current = router.currentRoute.value
      auth.clear()
      tenant.reset()
      toast.error('Tu sesión expiró. Inicia sesión nuevamente.', {
        title: 'Sesión finalizada',
      })
      if (current.name !== 'login') {
        router.replace({
          name: 'login',
          query:
            current.fullPath && current.fullPath !== '/login'
              ? { redirect: current.fullPath }
              : {},
        })
      }
    },
    onTenantAccessDenied: () => {
      const deniedId = tenant.currentCompanyId
      if (deniedId) {
        tenant.removeCompany(deniedId)
        auth.removeMembership(deniedId)
      }
      tenant.clearCurrentCompany()
      toast.warning(
        'Tu acceso a esta empresa ya no está disponible. Selecciona otra empresa.',
        { title: 'Acceso a la empresa denegado' },
      )
      if (router.currentRoute.value.name !== 'select-company') {
        router.replace({ name: 'select-company' })
      }
    },
    onRolePermissionDenied: ({ message }) => {
      toast.error(message || 'No tienes permisos para realizar esta acción.', {
        title: 'Permisos insuficientes',
      })
    },
    onServerError: ({ message, errorId }) => {
      const suffix = errorId ? ` Folio: ${errorId}` : ''
      toast.error(`${message}${suffix}`, {
        title: 'Error del servidor',
        duration: 8000,
      })
    },
  })

  app.use(router)
  await router.isReady()
  app.mount('#app')
}

bootstrap()

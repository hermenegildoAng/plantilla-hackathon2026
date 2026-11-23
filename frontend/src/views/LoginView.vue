<script setup>
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { AlertCircle, Landmark } from 'lucide-vue-next'

import BaseButton from '../components/ui/BaseButton.vue'
import BaseInput from '../components/ui/BaseInput.vue'
import { useToast } from '../composables/useToast'
import { useAuthStore } from '../stores/auth'
import { useTenantStore } from '../stores/tenant'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const tenant = useTenantStore()
const toast = useToast()

const email = ref('')
const password = ref('')
const loading = ref(false)
const error = ref('')

function safeRedirect() {
  const redirect = route.query.redirect
  if (typeof redirect !== 'string') return null
  if (!redirect.startsWith('/') || redirect.startsWith('//')) return null
  return redirect
}

async function submit() {
  if (loading.value) return
  error.value = ''

  if (!email.value.trim() || !password.value) {
    error.value = 'Ingresa tu correo electrónico y contraseña.'
    return
  }

  loading.value = true
  try {
    await auth.login({ email: email.value, password: password.value })
    tenant.reset()
    tenant.syncFromMemberships(auth.memberships)
    tenant.fetchCompanies().catch(() => {
      // Los datos de las membresías ya permiten continuar; el interceptor
      // muestra el error correspondiente si la consulta falla.
    })

    toast.success('Bienvenido al sistema contable.', {
      title: 'Sesión iniciada',
    })

    const redirect = safeRedirect()
    if (redirect) {
      await router.replace(redirect)
    } else {
      await router.replace({ name: 'select-company' })
    }
  } catch (err) {
    error.value =
      err?.errors?.[0]?.message ||
      err?.message ||
      'No fue posible iniciar sesión. Inténtalo de nuevo.'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="flex min-h-screen items-center justify-center bg-slate-50 px-4 py-8">
    <div class="w-full max-w-sm">
      <div class="mb-5 flex items-center justify-center gap-2.5">
        <div class="flex h-10 w-10 items-center justify-center rounded-lg bg-indigo-600">
          <Landmark class="w-5 h-5 text-white" aria-hidden="true" />
        </div>
        <div>
          <p class="text-sm font-semibold text-slate-900">Contable MX</p>
          <p class="text-[11px] text-slate-500">Sistema contable multiempresa</p>
        </div>
      </div>

      <div class="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
        <h1 class="text-lg font-semibold tracking-tight text-slate-900">
          Iniciar sesión
        </h1>
        <p class="mt-1 text-xs text-slate-600">
          Accede con las credenciales asignadas por tu despacho contable.
        </p>

        <div
          v-if="error"
          class="mt-3 flex items-start gap-2 rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-700"
          role="alert"
        >
          <AlertCircle class="mt-0.5 w-3.5 h-3.5 shrink-0" aria-hidden="true" />
          <p>{{ error }}</p>
        </div>

        <form class="mt-4 space-y-3" @submit.prevent="submit">
          <BaseInput
            v-model="email"
            label="Correo electrónico"
            type="email"
            placeholder="nombre@despacho.mx"
            autocomplete="email"
            required
          />

          <BaseInput
            v-model="password"
            label="Contraseña"
            type="password"
            placeholder="••••••••"
            autocomplete="current-password"
            required
          />

          <BaseButton
            type="submit"
            block
            :loading="loading"
            :disabled="loading"
          >
            Entrar
          </BaseButton>
        </form>

        <p class="mt-4 text-center text-[11px] leading-relaxed text-slate-500">
          Acceso restringido a usuarios registrados. Los usuarios se crean desde
          el administrador o el proceso de carga inicial.
        </p>
      </div>
    </div>
  </div>
</template>

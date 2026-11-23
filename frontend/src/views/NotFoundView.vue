<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { FileQuestion } from 'lucide-vue-next'

import BaseButton from '../components/ui/BaseButton.vue'
import EmptyState from '../components/ui/EmptyState.vue'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const auth = useAuthStore()

const homeRoute = computed(() =>
  auth.isAuthenticated ? { name: 'select-company' } : { name: 'login' },
)
</script>

<template>
  <div class="flex min-h-screen items-center justify-center bg-slate-50 px-4">
    <div class="w-full max-w-lg rounded-lg border border-slate-200 bg-white shadow-sm">
      <EmptyState
        :icon="FileQuestion"
        title="Página no encontrada"
        description="La dirección que intentaste abrir no existe o ya no está disponible."
      >
        <template #action>
          <BaseButton @click="router.push(homeRoute)">
            Ir al inicio
          </BaseButton>
        </template>
      </EmptyState>
    </div>
  </div>
</template>

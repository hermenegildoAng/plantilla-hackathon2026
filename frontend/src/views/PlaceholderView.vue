<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  ArrowLeftRight,
  BarChart3,
  CalendarRange,
  Construction,
  FileCode2,
  FileSpreadsheet,
  FolderTree,
  LayoutDashboard,
  ScrollText,
  Users,
} from 'lucide-vue-next'

import BaseBadge from '../components/ui/BaseBadge.vue'
import BaseButton from '../components/ui/BaseButton.vue'
import EmptyState from '../components/ui/EmptyState.vue'

const route = useRoute()
const router = useRouter()

const ICONS = {
  dashboard: LayoutDashboard,
  documents: FileCode2,
  entries: FileSpreadsheet,
  periods: CalendarRange,
  accounts: FolderTree,
  reconciliation: ArrowLeftRight,
  reports: BarChart3,
  'audit-log': ScrollText,
  members: Users,
}

const icon = computed(() => ICONS[route.name] || Construction)

function goToDashboard() {
  router.push({ name: 'dashboard', params: { id: route.params.id } })
}
</script>

<template>
  <section class="mx-auto max-w-4xl">
    <div class="flex flex-wrap items-start justify-between gap-3">
      <div class="min-w-0">
        <h1 class="text-lg font-semibold tracking-tight text-slate-900">
          {{ route.meta.title }}
        </h1>
        <p class="mt-1 max-w-2xl text-xs text-slate-600">
          {{ route.meta.description }}
        </p>
      </div>
      <BaseBadge variant="info">Módulo en preparación</BaseBadge>
    </div>

    <!-- TODO(bloque 8+): reemplazar este placeholder por la vista de negocio. -->
    <div class="mt-4 rounded-lg border border-slate-200 bg-white shadow-sm">
      <EmptyState
        :icon="icon"
        title="Vista en construcción"
        description="La interfaz de este módulo se habilitará en un bloque posterior. La navegación, el contexto de empresa y los permisos ya están configurados."
      >
        <template #action>
          <BaseButton variant="secondary" @click="goToDashboard">
            Volver al resumen
          </BaseButton>
        </template>
      </EmptyState>
    </div>
  </section>
</template>

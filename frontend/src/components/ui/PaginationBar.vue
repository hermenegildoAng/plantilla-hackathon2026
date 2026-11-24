<script setup>
import { computed } from 'vue'
import { ChevronLeft, ChevronRight } from 'lucide-vue-next'

import BaseButton from './BaseButton.vue'

const props = defineProps({
  page: {
    type: Number,
    default: 1,
  },
  pageSize: {
    type: Number,
    default: 25,
  },
  count: {
    type: Number,
    default: 0,
  },
  loading: Boolean,
})

const emit = defineEmits(['change'])

const totalPages = computed(() =>
  Math.max(1, Math.ceil(Number(props.count || 0) / props.pageSize)),
)

const start = computed(() => {
  if (props.count === 0) return 0
  return (props.page - 1) * props.pageSize + 1
})

const end = computed(() => Math.min(props.page * props.pageSize, props.count))

const canPrevious = computed(() => props.page > 1 && !props.loading)
const canNext = computed(() => props.page < totalPages.value && !props.loading)

function go(page) {
  if (page < 1 || page > totalPages.value) return
  emit('change', page)
}
</script>

<template>
  <nav
    class="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 shadow-sm"
    aria-label="Paginación de documentos"
  >
    <p class="text-[11px] text-slate-600">
      Mostrando
      <span class="font-semibold tabular-nums text-slate-800">
        {{ start }}–{{ end }}
      </span>
      de
      <span class="font-semibold tabular-nums text-slate-800">{{ count }}</span>
      documentos
    </p>

    <div class="flex items-center gap-1.5">
      <BaseButton
        variant="secondary"
        size="sm"
        :disabled="!canPrevious"
        aria-label="Página anterior"
        @click="go(page - 1)"
      >
        <template #icon>
          <ChevronLeft class="w-3.5 h-3.5" aria-hidden="true" />
        </template>
        Anterior
      </BaseButton>

      <span class="px-1 text-[11px] tabular-nums text-slate-600">
        Página {{ page }} de {{ totalPages }}
      </span>

      <BaseButton
        variant="secondary"
        size="sm"
        :disabled="!canNext"
        aria-label="Página siguiente"
        @click="go(page + 1)"
      >
        Siguiente
        <template #icon>
          <ChevronRight class="w-3.5 h-3.5" aria-hidden="true" />
        </template>
      </BaseButton>
    </div>
  </nav>
</template>

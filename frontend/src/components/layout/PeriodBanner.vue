<script setup>
import { Lock } from 'lucide-vue-next'

defineProps({
  periodLabel: {
    type: String,
    default: '',
  },
})
</script>

<template>
  <div
    class="flex items-center gap-2 border-b border-amber-200 bg-amber-50 px-4 py-1.5 text-xs text-amber-900"
    role="status"
  >
    <Lock class="w-3.5 h-3.5 shrink-0 text-amber-600" aria-hidden="true" />
    <p>
      <span class="font-semibold">Periodo contable cerrado</span>
      <span v-if="periodLabel"> · {{ periodLabel }}</span>. Las ediciones están
      bloqueadas; solo se permite consulta.
    </p>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { AlertTriangle, CheckCircle2 } from 'lucide-vue-next'

import { useCurrency } from '../../composables/useCurrency'

const props = defineProps({
  difference: {
    type: [String, Number],
    default: '0.00',
  },
  balanced: Boolean,
})

const { formatMoney } = useCurrency()

const label = computed(() => `Diferencia: ${formatMoney(props.difference)}`)
</script>

<template>
  <div
    class="inline-flex items-center gap-1.5 rounded-md border px-2 py-1 text-xs font-semibold tabular-nums"
    :class="
      balanced
        ? 'border-emerald-200 bg-emerald-50 text-emerald-700'
        : 'border-rose-200 bg-rose-50 text-rose-700'
    "
    role="status"
    data-testid="balance-indicator"
  >
    <CheckCircle2
      v-if="balanced"
      class="w-3.5 h-3.5 shrink-0"
      aria-hidden="true"
      data-testid="balance-ok"
    />
    <AlertTriangle
      v-else
      class="w-3.5 h-3.5 shrink-0"
      aria-hidden="true"
      data-testid="balance-alert"
    />
    <span>{{ label }}</span>
  </div>
</template>

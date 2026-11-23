<script setup>
import { computed } from 'vue'

import { useCurrency } from '../../composables/useCurrency'

const props = defineProps({
  value: {
    type: [String, Number],
    default: '0',
  },
  currency: {
    type: String,
    default: 'MXN',
  },
  showCurrency: {
    type: Boolean,
    default: true,
  },
  parentheses: Boolean,
  signed: Boolean,
  colorNegative: {
    type: Boolean,
    default: true,
  },
})

const { formatMoney, isNegative } = useCurrency()

const formatted = computed(() =>
  formatMoney(props.value, {
    currency: props.currency,
    showCurrency: props.showCurrency,
    parentheses: props.parentheses,
    signed: props.signed,
  }),
)

const negative = computed(() => props.colorNegative && isNegative(props.value))
</script>

<template>
  <span
    class="inline-block tabular-nums"
    :class="negative ? 'font-semibold text-rose-700' : ''"
  >
    {{ formatted }}
  </span>
</template>

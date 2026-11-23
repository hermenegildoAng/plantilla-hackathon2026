<script setup>
import { Inbox } from 'lucide-vue-next'

defineProps({
  title: {
    type: String,
    default: 'Sin información',
  },
  description: {
    type: String,
    default: '',
  },
  icon: {
    type: [Object, Function],
    default: () => Inbox,
  },
  compact: Boolean,
})
</script>

<template>
  <div
    class="flex flex-col items-center justify-center text-center"
    :class="compact ? 'py-6 px-4' : 'py-10 px-6'"
  >
    <div class="rounded-full bg-slate-100 p-3 text-slate-400">
      <component :is="icon" class="w-8 h-8" aria-hidden="true" />
    </div>
    <h3 class="mt-3 text-sm font-semibold text-slate-800">{{ title }}</h3>
    <p v-if="description" class="mt-1 max-w-md text-xs text-slate-600">
      {{ description }}
    </p>
    <div v-if="$slots.action" class="mt-4">
      <slot name="action" />
    </div>
  </div>
</template>

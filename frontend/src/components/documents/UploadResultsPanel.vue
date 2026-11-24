<script setup>
import { computed } from 'vue'
import { AlertTriangle, CheckCircle2, FileWarning, Inbox } from 'lucide-vue-next'

import BaseBadge from '../ui/BaseBadge.vue'
import MoneyCell from '../ui/MoneyCell.vue'

const props = defineProps({
  result: {
    type: Object,
    default: null,
  },
})

const DIRECTION_LABELS = {
  ISSUED: 'Emitido',
  RECEIVED: 'Recibido',
}

const processed = computed(() => props.result?.processed || [])
const failed = computed(() => props.result?.failed || [])
const summary = computed(() => props.result?.summary || {})

const processedCount = computed(
  () => Number(summary.value.processed_count ?? processed.value.length),
)
const failedCount = computed(
  () => Number(summary.value.failed_count ?? failed.value.length),
)

const summaryText = computed(() => {
  if (!props.result) return ''
  return (
    `${processedCount.value} comprobante${processedCount.value === 1 ? '' : 's'} ` +
    `importado${processedCount.value === 1 ? '' : 's'}, ` +
    `${failedCount.value} con error${failedCount.value === 1 ? '' : 'es'}.`
  )
})
</script>

<template>
  <section
    v-if="result"
    class="rounded-lg border border-slate-200 bg-white shadow-sm"
    aria-live="polite"
  >
    <header
      class="flex flex-wrap items-center justify-between gap-2 border-b border-slate-200 px-3 py-2"
    >
      <div class="flex items-center gap-2">
        <CheckCircle2
          v-if="failedCount === 0"
          class="w-4 h-4 text-emerald-600"
          aria-hidden="true"
        />
        <FileWarning
          v-else
          class="w-4 h-4 text-amber-600"
          aria-hidden="true"
        />
        <div>
          <h3 class="text-xs font-semibold text-slate-900">
            Resultado del procesamiento
          </h3>
          <p class="text-[11px] text-slate-500">{{ summaryText }}</p>
        </div>
      </div>

      <div class="flex items-center gap-1.5">
        <BaseBadge variant="success">{{ processedCount }} procesados</BaseBadge>
        <BaseBadge :variant="failedCount > 0 ? 'danger' : 'neutral'">
          {{ failedCount }} con error
        </BaseBadge>
      </div>
    </header>

    <div class="grid gap-0 divide-y divide-slate-100 md:grid-cols-2 md:divide-x md:divide-y-0">
      <div class="min-w-0 p-3">
        <h4 class="mb-2 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide text-slate-600">
          <CheckCircle2 class="w-3.5 h-3.5 text-emerald-600" aria-hidden="true" />
          Procesados
        </h4>

        <ul v-if="processed.length > 0" class="divide-y divide-slate-100">
          <li
            v-for="(item, index) in processed"
            :key="`processed-${item.filename || index}`"
            class="flex items-start justify-between gap-2 py-1.5"
          >
            <div class="min-w-0">
              <p class="truncate text-xs font-medium text-slate-800" :title="item.filename">
                {{ item.filename }}
              </p>
              <p
                v-if="item.uuid"
                class="truncate font-mono text-[10px] text-slate-500"
                :title="item.uuid"
              >
                {{ item.uuid }}
              </p>
              <p v-else class="text-[10px] text-slate-500">
                Comprobante manual sin UUID
              </p>
            </div>
            <div class="flex shrink-0 flex-col items-end gap-0.5">
              <BaseBadge
                :variant="item.direction === 'ISSUED' ? 'brand' : 'info'"
              >
                {{ DIRECTION_LABELS[item.direction] || item.direction || '—' }}
              </BaseBadge>
              <MoneyCell
                v-if="item.total !== undefined && item.total !== null"
                :value="item.total"
                class="text-[11px]"
              />
            </div>
          </li>
        </ul>

        <p v-else class="flex items-center gap-1.5 py-2 text-[11px] text-slate-500">
          <Inbox class="w-3.5 h-3.5" aria-hidden="true" />
          Ningún archivo se importó en este envío.
        </p>
      </div>

      <div class="min-w-0 p-3">
        <h4 class="mb-2 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide text-slate-600">
          <AlertTriangle class="w-3.5 h-3.5 text-rose-600" aria-hidden="true" />
          Con errores
        </h4>

        <ul v-if="failed.length > 0" class="divide-y divide-slate-100">
          <li
            v-for="(item, index) in failed"
            :key="`failed-${item.filename || index}-${item.code || index}`"
            class="py-1.5"
          >
            <div class="flex flex-wrap items-center gap-1.5">
              <p class="min-w-0 flex-1 truncate text-xs font-medium text-slate-800" :title="item.filename">
                {{ item.filename }}
              </p>
              <code
                class="rounded bg-rose-50 px-1 py-0.5 font-mono text-[10px] text-rose-700"
              >
                {{ item.code || 'upload_failed' }}
              </code>
            </div>
            <p class="mt-0.5 text-[11px] leading-relaxed text-slate-600">
              {{ item.message || 'No fue posible procesar el archivo.' }}
            </p>
          </li>
        </ul>

        <p v-else class="flex items-center gap-1.5 py-2 text-[11px] text-slate-500">
          <CheckCircle2 class="w-3.5 h-3.5 text-emerald-600" aria-hidden="true" />
          Sin errores en este envío.
        </p>
      </div>
    </div>
  </section>
</template>

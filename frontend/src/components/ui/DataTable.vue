<script setup>
import { computed } from 'vue'

import BaseBadge from './BaseBadge.vue'
import EmptyState from './EmptyState.vue'
import MoneyCell from './MoneyCell.vue'

const props = defineProps({
  columns: {
    type: Array,
    default: () => [],
  },
  rows: {
    type: Array,
    default: () => [],
  },
  rowKey: {
    type: [String, Function],
    default: 'id',
  },
  loading: Boolean,
  emptyTitle: {
    type: String,
    default: 'Sin registros',
  },
  emptyDescription: {
    type: String,
    default: 'No hay información para mostrar con los filtros actuales.',
  },
  totals: {
    type: Object,
    default: null,
  },
  footerLabel: {
    type: String,
    default: 'Totales',
  },
  balance: {
    type: Object,
    default: null,
  },
  maxHeight: {
    type: String,
    default: 'none',
  },
  stickyHeader: {
    type: Boolean,
    default: true,
  },
  stickyFooter: {
    type: Boolean,
    default: true,
  },
  dense: {
    type: Boolean,
    default: true,
  },
  rowClickable: Boolean,
})

const emit = defineEmits(['row-click'])

const ALIGN_CLASSES = {
  left: 'text-left',
  center: 'text-center',
  right: 'text-right tabular-nums',
}

function alignClass(align) {
  return ALIGN_CLASSES[align] || ALIGN_CLASSES.left
}

function keyFor(row, index) {
  if (typeof props.rowKey === 'function') return props.rowKey(row)
  return row?.[props.rowKey] ?? index
}

function valueFor(row, column) {
  const value = row?.[column.key]
  return typeof column.format === 'function' ? column.format(value, row) : value
}

function totalFor(column) {
  return props.totals?.[column.key] ?? ''
}

const cellPadding = computed(() => (props.dense ? 'px-3 py-1.5' : 'px-3 py-2.5'))
const isBalanced = computed(() => props.balance?.isBalanced !== false)
</script>

<template>
  <div
    class="flex flex-col overflow-hidden rounded-lg border border-slate-200 bg-white"
  >
    <div class="overflow-auto" :style="{ maxHeight }">
      <table class="min-w-full border-collapse">
        <thead
          class="bg-slate-100"
          :class="stickyHeader ? 'sticky top-0 z-10' : ''"
        >
          <tr class="border-b border-slate-200">
            <th
              v-for="column in columns"
              :key="column.key"
              scope="col"
              class="whitespace-nowrap px-3 py-2 text-[11px] font-semibold uppercase tracking-wider text-slate-600"
              :class="alignClass(column.align)"
              :style="column.width ? { width: column.width } : undefined"
            >
              <slot :name="`header-${column.key}`" :column="column">
                {{ column.label }}
              </slot>
            </th>
          </tr>
        </thead>

        <tbody class="divide-y divide-slate-100">
          <template v-if="loading">
            <tr v-for="index in 5" :key="`skeleton-${index}`">
              <td
                v-for="column in columns"
                :key="column.key"
                :class="cellPadding"
              >
                <div class="h-3 animate-pulse rounded bg-slate-100" />
              </td>
            </tr>
          </template>

          <tr v-else-if="rows.length === 0">
            <td :colspan="columns.length || 1" class="p-0">
              <EmptyState
                :title="emptyTitle"
                :description="emptyDescription"
                compact
              />
            </td>
          </tr>

          <template v-else>
            <tr
              v-for="(row, index) in rows"
              :key="keyFor(row, index)"
              class="transition-colors hover:bg-slate-50/90"
              :class="rowClickable ? 'cursor-pointer' : ''"
              @click="rowClickable && emit('row-click', row)"
            >
              <td
                v-for="column in columns"
                :key="column.key"
                class="text-xs text-slate-700"
                :class="[alignClass(column.align), cellPadding, column.class]"
              >
                <slot
                  :name="`cell-${column.key}`"
                  :row="row"
                  :value="row?.[column.key]"
                  :index="index"
                >
                  {{ valueFor(row, column) }}
                </slot>
              </td>
            </tr>
          </template>
        </tbody>

        <tfoot
          v-if="totals || balance || $slots.footer"
          class="border-t-2 border-slate-300 bg-slate-50 text-xs font-semibold tabular-nums"
          :class="stickyFooter ? 'sticky bottom-0 z-10' : ''"
        >
          <slot name="footer">
            <tr v-if="totals">
              <td
                v-for="(column, index) in columns"
                :key="column.key"
                class="px-3 py-2 text-slate-900"
                :class="alignClass(column.align)"
              >
                <template v-if="index === 0">{{ footerLabel }}</template>
                <template v-else>{{ totalFor(column) }}</template>
              </td>
            </tr>

            <tr v-if="balance" class="border-t border-slate-200">
              <td :colspan="columns.length || 1" class="px-3 py-2">
                <div class="flex items-center justify-end gap-2">
                  <span class="text-slate-700">
                    {{ balance.label || 'Diferencia' }}:
                  </span>
                  <MoneyCell :value="balance.value ?? '0'" />
                  <BaseBadge :variant="isBalanced ? 'success' : 'danger'" dot>
                    {{ isBalanced ? 'Cuadrada' : 'Descuadrada' }}
                  </BaseBadge>
                </div>
              </td>
            </tr>
          </slot>
        </tfoot>
      </table>
    </div>
  </div>
</template>

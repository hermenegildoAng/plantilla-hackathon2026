<script setup>
import { computed, onBeforeUnmount, watch } from 'vue'
import {
  FileText,
  Lock,
  Pencil,
  X,
} from 'lucide-vue-next'

import BaseBadge from '../ui/BaseBadge.vue'
import BaseButton from '../ui/BaseButton.vue'
import MoneyCell from '../ui/MoneyCell.vue'
import BalanceIndicator from './BalanceIndicator.vue'

const props = defineProps({
  entry: {
    type: Object,
    default: null,
  },
  canEdit: Boolean,
  periodClosed: Boolean,
})

const emit = defineEmits(['close', 'edit'])

const typeLabels = {
  INCOME: 'Ingreso',
  EXPENSE: 'Egreso',
  JOURNAL: 'Diario',
}

const statusLabels = {
  POSTED: 'Contabilizada',
  DRAFT: 'Borrador',
}

const open = computed(() => Boolean(props.entry))

const items = computed(() => props.entry?.items || [])

const linkedDocuments = computed(() => {
  const byKey = new Map()
  items.value.forEach((item) => {
    if (!item.document && !item.document_uuid) return
    const key = String(item.document || item.document_uuid)
    if (!byKey.has(key)) {
      byKey.set(key, {
        id: item.document,
        uuid: item.document_uuid,
        descriptions: [item.description].filter(Boolean),
      })
    } else if (item.description) {
      byKey.get(key).descriptions.push(item.description)
    }
  })
  return Array.from(byKey.values())
})

function handleKeydown(event) {
  if (event.key === 'Escape') emit('close')
}

watch(
  open,
  (isOpen) => {
    if (typeof document === 'undefined') return
    if (isOpen) {
      document.body.style.overflow = 'hidden'
      document.addEventListener('keydown', handleKeydown)
    } else {
      document.body.style.overflow = ''
      document.removeEventListener('keydown', handleKeydown)
    }
  },
  { immediate: true },
)

onBeforeUnmount(() => {
  if (typeof document === 'undefined') return
  document.body.style.overflow = ''
  document.removeEventListener('keydown', handleKeydown)
})
</script>

<template>
  <Teleport to="body">
    <Transition
      enter-active-class="transition duration-150 ease-out"
      enter-from-class="opacity-0"
      enter-to-class="opacity-100"
      leave-active-class="transition duration-100 ease-in"
      leave-from-class="opacity-100"
      leave-to-class="opacity-0"
    >
      <div
        v-if="entry"
        class="fixed inset-0 z-50 flex justify-end bg-slate-900/50 backdrop-blur-[1px]"
        role="presentation"
        @click.self="emit('close')"
      >
        <div
          class="flex h-full w-full max-w-3xl flex-col overflow-hidden border-l border-slate-200 bg-white shadow-xl"
          role="dialog"
          aria-modal="true"
          aria-labelledby="entry-drawer-title"
        >
          <header class="flex items-start gap-3 border-b border-slate-200 px-4 py-3">
            <div class="min-w-0 flex-1">
              <div class="flex flex-wrap items-center gap-1.5">
                <h2
                  id="entry-drawer-title"
                  class="font-mono text-sm font-semibold text-slate-900"
                >
                  {{ entry.folio }}
                </h2>
                <BaseBadge variant="info">
                  {{ typeLabels[entry.entry_type] || entry.entry_type }}
                </BaseBadge>
                <BaseBadge
                  :variant="entry.status === 'POSTED' ? 'success' : 'warning'"
                  dot
                >
                  {{ statusLabels[entry.status] || entry.status }}
                </BaseBadge>
                <BaseBadge v-if="periodClosed" variant="warning">
                  <template #icon>
                    <Lock class="w-3 h-3" aria-hidden="true" />
                  </template>
                  Periodo cerrado
                </BaseBadge>
              </div>
              <p class="mt-1 text-xs text-slate-700">{{ entry.concept }}</p>
              <p class="mt-0.5 text-[11px] text-slate-500">
                Periodo {{ entry.period_label }} · Fecha {{ entry.entry_date }}
              </p>
            </div>

            <div class="flex shrink-0 items-center gap-1.5">
              <BaseButton
                v-if="canEdit && !periodClosed"
                variant="secondary"
                size="sm"
                @click="emit('edit')"
              >
                <template #icon>
                  <Pencil class="w-3.5 h-3.5" aria-hidden="true" />
                </template>
                Editar
              </BaseButton>
              <button
                type="button"
                class="rounded-md p-1.5 text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-600 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                aria-label="Cerrar detalle"
                @click="emit('close')"
              >
                <X class="w-4 h-4" aria-hidden="true" />
              </button>
            </div>
          </header>

          <div class="flex-1 overflow-y-auto p-4">
            <h3 class="text-xs font-semibold uppercase tracking-wider text-slate-600">
              Renglones
            </h3>
            <div class="mt-1.5 overflow-hidden rounded-lg border border-slate-200">
              <table class="min-w-full border-collapse">
                <thead class="bg-slate-100">
                  <tr class="border-b border-slate-200">
                    <th class="w-8 px-2 py-2 text-center text-[11px] font-semibold text-slate-600">#</th>
                    <th class="px-2 py-2 text-left text-[11px] font-semibold text-slate-600">Cuenta</th>
                    <th class="px-2 py-2 text-left text-[11px] font-semibold text-slate-600">Descripción</th>
                    <th class="px-2 py-2 text-right text-[11px] font-semibold text-slate-600">Cargo</th>
                    <th class="px-2 py-2 text-right text-[11px] font-semibold text-slate-600">Abono</th>
                  </tr>
                </thead>
                <tbody class="divide-y divide-slate-100">
                  <tr v-for="item in items" :key="item.id" class="hover:bg-slate-50/90">
                    <td class="px-2 py-1.5 text-center text-[11px] tabular-nums text-slate-500">
                      {{ item.line_number }}
                    </td>
                    <td class="px-2 py-1.5">
                      <p class="font-mono text-[10px] text-slate-500">{{ item.account_code }}</p>
                      <p class="text-xs text-slate-800">{{ item.account_name }}</p>
                    </td>
                    <td class="px-2 py-1.5 text-xs text-slate-700">
                      {{ item.description || '—' }}
                    </td>
                    <td class="border-l border-slate-100 px-2 py-1.5 text-right text-xs tabular-nums">
                      <MoneyCell :value="item.debit" />
                    </td>
                    <td class="border-l border-slate-100 px-2 py-1.5 text-right text-xs tabular-nums">
                      <MoneyCell :value="item.credit" />
                    </td>
                  </tr>
                </tbody>
                <tfoot class="border-t-2 border-slate-300 bg-slate-50 text-xs font-semibold tabular-nums">
                  <tr>
                    <td colspan="3" class="px-2 py-2 text-slate-700">Totales</td>
                    <td class="border-l border-slate-200 px-2 py-2 text-right">
                      <MoneyCell :value="entry.total_debit" />
                    </td>
                    <td class="border-l border-slate-200 px-2 py-2 text-right">
                      <MoneyCell :value="entry.total_credit" />
                    </td>
                  </tr>
                </tfoot>
              </table>
            </div>

            <div class="mt-2 flex justify-end">
              <BalanceIndicator difference="0.00" :balanced="true" />
            </div>

            <section class="mt-4">
              <h3 class="text-xs font-semibold uppercase tracking-wider text-slate-600">
                Documentos vinculados
              </h3>
              <ul
                v-if="linkedDocuments.length"
                class="mt-1.5 divide-y divide-slate-100 rounded-lg border border-slate-200 bg-white"
              >
                <li
                  v-for="document in linkedDocuments"
                  :key="document.id || document.uuid"
                  class="flex items-start gap-2 px-3 py-2"
                >
                  <FileText class="mt-0.5 w-3.5 h-3.5 shrink-0 text-slate-400" aria-hidden="true" />
                  <div class="min-w-0">
                    <p class="truncate font-mono text-[11px] text-slate-700">
                      {{ document.uuid || `Documento ${document.id}` }}
                    </p>
                    <p v-if="document.descriptions.length" class="truncate text-[11px] text-slate-500">
                      {{ document.descriptions.join(' · ') }}
                    </p>
                  </div>
                </li>
              </ul>
              <p v-else class="mt-1.5 rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-[11px] text-slate-500">
                Esta póliza no tiene documentos vinculados.
              </p>
            </section>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

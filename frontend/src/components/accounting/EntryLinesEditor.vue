<script setup>
import { computed } from 'vue'
import { FileText, Plus, Trash2 } from 'lucide-vue-next'

import AccountSelect from './AccountSelect.vue'
import { createEntryLine } from '../../composables/useEntryForm'
import { useCurrency } from '../../composables/useCurrency'

const props = defineProps({
  modelValue: {
    type: Array,
    default: () => [],
  },
  accounts: {
    type: Array,
    default: () => [],
  },
  documents: {
    type: Array,
    default: () => [],
  },
  readOnly: Boolean,
})

const emit = defineEmits(['update:modelValue', 'add', 'remove'])

const { formatMoney } = useCurrency()

const unaccountedDocuments = computed(() =>
  props.documents.filter((document) => document?.is_accounted === false || document?.is_accounted == null),
)

function updateLine(index, patch) {
  if (props.readOnly) return
  const next = props.modelValue.map((line, lineIndex) =>
    lineIndex === index ? { ...line, ...patch } : line,
  )
  emit('update:modelValue', next)
}

function addLine() {
  if (props.readOnly) return
  emit('add', createEntryLine())
}

function removeLine(index) {
  if (props.readOnly || props.modelValue.length <= 1) return
  emit('remove', index)
}

function documentLabel(document) {
  const reference =
    document?.uuid ||
    document?.original_filename ||
    (document?.folio ? `Folio ${document.folio}` : `Documento ${document?.id}`)
  const total = document?.total ? ` · ${formatMoney(document.total)}` : ''
  return `${reference}${total}`
}

function documentFor(line) {
  if (line.document === '' || line.document === null || line.document === undefined) {
    return null
  }
  return (
    props.documents.find(
      (document) => String(document.id) === String(line.document),
    ) || null
  )
}

function hasDocumentValue(document, field) {
  if (!document) return false
  const value = document[field]
  return value !== null && value !== undefined && value !== ''
}

function hasDocumentSuggestions(document) {
  return (
    hasDocumentValue(document, 'subtotal') ||
    hasDocumentValue(document, 'iva_transferred') ||
    hasDocumentValue(document, 'total')
  )
}

function applySuggestion(index, line, field) {
  const document = documentFor(line)
  if (!document || props.readOnly) return
  const values = {
    subtotal: document.subtotal,
    iva: document.iva_transferred,
    total: document.total,
  }
  const labels = {
    subtotal: 'Subtotal del comprobante',
    iva: 'IVA trasladado del comprobante',
    total: 'Total del comprobante',
  }
  updateLine(index, {
    amount: String(values[field] ?? '0.00'),
    description: line.description || labels[field],
  })
}

function onDocumentChange(index, value) {
  updateLine(index, { document: value })
}
</script>

<template>
  <div class="space-y-2">
    <div class="flex flex-wrap items-center justify-between gap-2">
      <div>
        <h2 class="text-sm font-semibold text-slate-900">Renglones de la póliza</h2>
        <p class="mt-0.5 text-[11px] text-slate-600">
          Cada renglón lleva un solo importe: cargo <span aria-hidden="true">o</span> abono.
        </p>
      </div>
      <button
        v-if="!readOnly"
        type="button"
        class="inline-flex h-7 items-center gap-1.5 rounded-md border border-slate-300 bg-white px-2.5 text-[11px] font-medium text-slate-700 transition-colors hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-indigo-500"
        @click="addLine"
      >
        <Plus class="w-3.5 h-3.5" aria-hidden="true" />
        Agregar renglón
      </button>
    </div>

    <div class="overflow-x-auto rounded-lg border border-slate-200 bg-white">
      <table class="min-w-full border-collapse">
        <thead class="bg-slate-100">
          <tr class="border-b border-slate-200">
            <th class="w-8 px-2 py-2 text-center text-[11px] font-semibold uppercase tracking-wider text-slate-600">
              #
            </th>
            <th class="min-w-[230px] px-2 py-2 text-left text-[11px] font-semibold uppercase tracking-wider text-slate-600">
              Cuenta contable
            </th>
            <th class="min-w-[200px] px-2 py-2 text-left text-[11px] font-semibold uppercase tracking-wider text-slate-600">
              Descripción
            </th>
            <th class="w-[132px] px-2 py-2 text-center text-[11px] font-semibold uppercase tracking-wider text-slate-600">
              Movimiento
            </th>
            <th class="w-[132px] px-2 py-2 text-right text-[11px] font-semibold uppercase tracking-wider text-slate-600">
              Importe
            </th>
            <th class="min-w-[230px] px-2 py-2 text-left text-[11px] font-semibold uppercase tracking-wider text-slate-600">
              Documento soporte
            </th>
            <th class="w-10 px-2 py-2" />
          </tr>
        </thead>
        <tbody class="divide-y divide-slate-100">
          <tr v-for="(line, index) in modelValue" :key="line.key || index">
            <td class="px-2 py-2 text-center text-[11px] tabular-nums text-slate-500">
              {{ index + 1 }}
            </td>
            <td class="px-2 py-2">
              <AccountSelect
                :model-value="line.account"
                :accounts="accounts"
                :disabled="readOnly"
                @update:model-value="updateLine(index, { account: $event })"
              />
            </td>
            <td class="px-2 py-2">
              <input
                :value="line.description"
                type="text"
                maxlength="255"
                placeholder="Concepto del renglón"
                :disabled="readOnly"
                class="block h-8 w-full rounded-md border border-slate-300 bg-white px-2.5 text-xs text-slate-700 shadow-sm placeholder:text-slate-400 focus:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-1 disabled:cursor-not-allowed disabled:bg-slate-50"
                @input="updateLine(index, { description: $event.target.value })"
              />
            </td>
            <td class="px-2 py-2">
              <div class="inline-flex overflow-hidden rounded-md border border-slate-300 bg-white shadow-sm">
                <button
                  type="button"
                  class="h-8 px-2.5 text-[11px] font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-inset focus:ring-indigo-500 disabled:cursor-not-allowed"
                  :class="
                    line.direction === 'debit'
                      ? 'bg-indigo-600 text-white'
                      : 'bg-white text-slate-600 hover:bg-slate-50'
                  "
                  :disabled="readOnly"
                  :aria-pressed="line.direction === 'debit'"
                  @click="updateLine(index, { direction: 'debit' })"
                >
                  Cargo
                </button>
                <button
                  type="button"
                  class="h-8 border-l border-slate-300 px-2.5 text-[11px] font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-inset focus:ring-indigo-500 disabled:cursor-not-allowed"
                  :class="
                    line.direction === 'credit'
                      ? 'bg-sky-600 text-white'
                      : 'bg-white text-slate-600 hover:bg-slate-50'
                  "
                  :disabled="readOnly"
                  :aria-pressed="line.direction === 'credit'"
                  @click="updateLine(index, { direction: 'credit' })"
                >
                  Abono
                </button>
              </div>
            </td>
            <td class="px-2 py-2">
              <input
                :value="line.amount"
                type="text"
                inputmode="decimal"
                placeholder="0.00"
                :disabled="readOnly"
                class="block h-8 w-full rounded-md border border-slate-300 bg-white px-2.5 text-right text-xs tabular-nums text-slate-700 shadow-sm placeholder:text-slate-400 focus:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-1 disabled:cursor-not-allowed disabled:bg-slate-50"
                aria-label="Importe del renglón"
                @input="updateLine(index, { amount: $event.target.value })"
              />
            </td>
            <td class="px-2 py-2">
              <select
                :value="line.document === null || line.document === undefined ? '' : String(line.document)"
                :disabled="readOnly"
                class="block h-8 w-full rounded-md border border-slate-300 bg-white px-2 text-xs text-slate-700 shadow-sm focus:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-1 disabled:cursor-not-allowed disabled:bg-slate-50"
                aria-label="Documento soporte del renglón"
                @change="onDocumentChange(index, $event.target.value)"
              >
                <option value="">Sin documento</option>
                <option
                  v-for="document in unaccountedDocuments"
                  :key="document.id"
                  :value="String(document.id)"
                >
                  {{ documentLabel(document) }}
                </option>
              </select>

              <div
                v-if="hasDocumentSuggestions(documentFor(line)) && !readOnly"
                class="mt-1 flex flex-wrap items-center gap-1"
              >
                <span class="inline-flex items-center gap-1 text-[10px] text-slate-500">
                  <FileText class="w-3 h-3" aria-hidden="true" />
                  Sugerir:
                </span>
                <button
                  v-if="hasDocumentValue(documentFor(line), 'subtotal')"
                  type="button"
                  class="rounded border border-slate-200 bg-slate-50 px-1.5 py-0.5 text-[10px] font-medium text-slate-700 transition-colors hover:bg-indigo-50 hover:text-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  @click="applySuggestion(index, line, 'subtotal')"
                >
                  Subtotal {{ formatMoney(documentFor(line).subtotal) }}
                </button>
                <button
                  v-if="hasDocumentValue(documentFor(line), 'iva_transferred')"
                  type="button"
                  class="rounded border border-slate-200 bg-slate-50 px-1.5 py-0.5 text-[10px] font-medium text-slate-700 transition-colors hover:bg-indigo-50 hover:text-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  @click="applySuggestion(index, line, 'iva')"
                >
                  IVA {{ formatMoney(documentFor(line).iva_transferred) }}
                </button>
                <button
                  v-if="hasDocumentValue(documentFor(line), 'total')"
                  type="button"
                  class="rounded border border-slate-200 bg-slate-50 px-1.5 py-0.5 text-[10px] font-medium text-slate-700 transition-colors hover:bg-indigo-50 hover:text-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  @click="applySuggestion(index, line, 'total')"
                >
                  Total {{ formatMoney(documentFor(line).total) }}
                </button>
              </div>
            </td>
            <td class="px-2 py-2 text-center">
              <button
                v-if="!readOnly"
                type="button"
                class="inline-flex h-7 w-7 items-center justify-center rounded-md text-slate-400 transition-colors hover:bg-rose-50 hover:text-rose-700 focus:outline-none focus:ring-2 focus:ring-rose-500 disabled:cursor-not-allowed disabled:opacity-40"
                :disabled="modelValue.length <= 1"
                title="Eliminar renglón"
                aria-label="Eliminar renglón"
                @click="removeLine(index)"
              >
                <Trash2 class="w-3.5 h-3.5" aria-hidden="true" />
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

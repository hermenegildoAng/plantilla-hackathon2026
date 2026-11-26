import { computed, ref } from 'vue'

import { useCurrency } from './useCurrency'

export const ENTRY_TYPE_OPTIONS = [
  { value: 'INCOME', label: 'Ingreso', prefix: 'ING' },
  { value: 'EXPENSE', label: 'Egreso', prefix: 'EGR' },
  { value: 'JOURNAL', label: 'Diario', prefix: 'DIA' },
]

export const ENTRY_STATUS_OPTIONS = [
  { value: 'POSTED', label: 'Contabilizada' },
  { value: 'DRAFT', label: 'Borrador' },
]

let lineSequence = 0

/** Creates an empty journal entry line with a stable client-side key. */
export function createEntryLine(overrides = {}) {
  return {
    key: `entry-line-${++lineSequence}`,
    account: '',
    direction: 'debit',
    amount: '',
    description: '',
    document: '',
    ...overrides,
  }
}

/**
 * Live double-entry calculations for the entry form.
 *
 * E-23: every total and difference is calculated with decimal.js; backend
 * amounts stay as strings in the JSON payload.
 */
export function useEntryForm({ lines, readOnly } = {}) {
  const { Decimal, sum, subtract, equals, formatMoney } = useCurrency()
  const lineList = lines || ref([])
  const readOnlyRef = readOnly || ref(false)

  const debitTotal = computed(() =>
    sum(
      lineList.value
        .filter((line) => line.direction === 'debit')
        .map((line) => line.amount),
    ),
  )

  const creditTotal = computed(() =>
    sum(
      lineList.value
        .filter((line) => line.direction === 'credit')
        .map((line) => line.amount),
    ),
  )

  const difference = computed(() => subtract(debitTotal.value, creditTotal.value))

  const hasAmounts = computed(
    () =>
      new Decimal(debitTotal.value).gt(0) ||
      new Decimal(creditTotal.value).gt(0),
  )

  const isBalanced = computed(
    () => hasAmounts.value && equals(debitTotal.value, creditTotal.value),
  )

  const canSave = computed(
    () =>
      !readOnlyRef.value &&
      lineList.value.length >= 2 &&
      isBalanced.value,
  )

  const differenceLabel = computed(
    () => `Diferencia: ${formatMoney(difference.value)}`,
  )

  return {
    debitTotal,
    creditTotal,
    difference,
    differenceLabel,
    hasAmounts,
    isBalanced,
    canSave,
  }
}

function amountForPayload(value) {
  const { toFixed } = useCurrency()
  return toFixed(value || '0')
}

/**
 * Builds the DRF payload. Only one of debit/credit is filled per line, and
 * amounts are serialized as strings with two decimals.
 */
export function buildEntryPayload({
  entryType,
  entryDate,
  concept,
  status,
  fiscalPeriod,
  lines,
}) {
  const payload = {
    entry_type: entryType,
    entry_date: entryDate,
    concept: (concept || '').trim(),
    status,
    items: (lines || []).map((line) => {
      const item = {
        account: Number(line.account),
        description: (line.description || '').trim(),
        debit: line.direction === 'debit' ? amountForPayload(line.amount) : '0.00',
        credit:
          line.direction === 'credit' ? amountForPayload(line.amount) : '0.00',
      }
      if (line.document !== '' && line.document !== null && line.document !== undefined) {
        item.document = Number(line.document)
      }
      return item
    }),
  }

  if (fiscalPeriod !== '' && fiscalPeriod !== null && fiscalPeriod !== undefined) {
    payload.fiscal_period = Number(fiscalPeriod)
  }

  return payload
}

/** Maps a backend entry payload back to the editable line model. */
export function entryToLines(entry) {
  const items = Array.isArray(entry?.items) ? entry.items : []
  return items.map((item) =>
    createEntryLine({
      account: item.account ?? '',
      direction:
        item.credit && item.credit !== '0.00' && item.credit !== '0'
          ? 'credit'
          : 'debit',
      amount:
        item.credit && item.credit !== '0.00' && item.credit !== '0'
          ? String(item.credit)
          : String(item.debit || ''),
      description: item.description || '',
      document: item.document ?? '',
    }),
  )
}

export function todayIsoDate(value = new Date()) {
  const date = value instanceof Date ? value : new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${date.getFullYear()}-${month}-${day}`
}

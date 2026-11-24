import { computed, ref } from 'vue'

const MONTHS = [
  'Enero',
  'Febrero',
  'Marzo',
  'Abril',
  'Mayo',
  'Junio',
  'Julio',
  'Agosto',
  'Septiembre',
  'Octubre',
  'Noviembre',
  'Diciembre',
]

// Estado compartido del shell. La vista de documentos lo sincroniza con el
// periodo fiscal real que devuelve GET /periods/ (bloque 8).
const isClosed = ref(false)
const referenceDate = ref(new Date())

export function useActivePeriod() {
  const periodLabel = computed(
    () =>
      `${MONTHS[referenceDate.value.getMonth()]} ${referenceDate.value.getFullYear()}`,
  )
  const fiscalYear = computed(() => referenceDate.value.getFullYear())

  function setClosed(value) {
    isClosed.value = Boolean(value)
  }

  function setReferenceDate(value) {
    referenceDate.value = value instanceof Date ? value : new Date(value)
  }

  /** Sincroniza el shell con el periodo fiscal seleccionado. */
  function setFromPeriod(period) {
    if (!period) {
      setClosed(false)
      return
    }
    setReferenceDate(new Date(period.year, period.month - 1, 1))
    setClosed(Boolean(period.is_closed))
  }

  return {
    periodLabel,
    fiscalYear,
    isClosed,
    setClosed,
    setReferenceDate,
    setFromPeriod,
  }
}

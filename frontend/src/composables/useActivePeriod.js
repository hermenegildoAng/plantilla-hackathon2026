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

// Estado compartido del shell. El bloque 8+ lo reemplazará por el periodo
// fiscal real que devuelva la API de periodos.
const isClosed = ref(false)
const referenceDate = ref(new Date())

export function useActivePeriod() {
  const periodLabel = computed(
    () =>
      `${MONTHS[referenceDate.value.getMonth()]} ${referenceDate.value.getFullYear()}`,
  )
  const fiscalYear = computed(() => referenceDate.value.getFullYear())

  // TODO(bloque 8): conectar con GET /periods/ para reflejar cierres reales.
  function setClosed(value) {
    isClosed.value = Boolean(value)
  }

  function setReferenceDate(value) {
    referenceDate.value = value instanceof Date ? value : new Date(value)
  }

  return {
    periodLabel,
    fiscalYear,
    isClosed,
    setClosed,
    setReferenceDate,
  }
}

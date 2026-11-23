import Decimal from 'decimal.js'

// E-23: todo cálculo monetario del cliente pasa por decimal.js.
Decimal.set({ precision: 28, rounding: Decimal.ROUND_HALF_UP })

const DEFAULT_CURRENCY = 'MXN'
const DEFAULT_LOCALE = 'es-MX'

function toDecimal(value) {
  if (value === null || value === undefined || value === '') return new Decimal(0)
  if (value instanceof Decimal) return value
  try {
    return new Decimal(value)
  } catch {
    return new Decimal(0)
  }
}

function toFixed(value, decimals = 2) {
  return toDecimal(value).toFixed(decimals)
}

function sum(values = []) {
  if (!Array.isArray(values)) return '0.00'
  return values
    .reduce((accumulator, value) => accumulator.plus(toDecimal(value)), new Decimal(0))
    .toFixed(2)
}

function subtract(minuend, subtrahend) {
  return toDecimal(minuend).minus(toDecimal(subtrahend)).toFixed(2)
}

function multiply(value, factor) {
  return toDecimal(value).times(toDecimal(factor)).toFixed(2)
}

function divide(value, divisor) {
  const divisorDecimal = toDecimal(divisor)
  if (divisorDecimal.isZero()) return '0.00'
  return toDecimal(value).dividedBy(divisorDecimal).toFixed(2)
}

function equals(left, right) {
  return toDecimal(left).equals(toDecimal(right))
}

function isZero(value) {
  return toDecimal(value).isZero()
}

function isNegative(value) {
  const decimal = toDecimal(value)
  return decimal.isNegative() && !decimal.isZero()
}

function abs(value) {
  return toDecimal(value).abs().toFixed(2)
}

function percent(value, total) {
  const totalDecimal = toDecimal(total)
  if (totalDecimal.isZero()) return '0.00'
  return toDecimal(value).dividedBy(totalDecimal).times(100).toFixed(2)
}

const formatterCache = new Map()

function getFormatter({ locale, currency, showCurrency, decimals }) {
  const key = `${locale}|${currency}|${showCurrency}|${decimals}`
  if (!formatterCache.has(key)) {
    formatterCache.set(
      key,
      new Intl.NumberFormat(locale, {
        style: showCurrency ? 'currency' : 'decimal',
        currency,
        currencyDisplay: 'narrowSymbol',
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals,
      }),
    )
  }
  return formatterCache.get(key)
}

function groupInteger(integer, parts) {
  const separator = parts.find((part) => part.type === 'group')?.value || ','
  return integer.replace(/\B(?=(\d{3})+(?!\d))/g, separator)
}

/**
 * Formatea un importe sin convertir el dinero a `Number`: se toma la cadena
 * exacta de Decimal y solo se usan las partes de Intl para separadores y
 * símbolo de moneda.
 */
function formatMoney(
  value,
  {
    currency = DEFAULT_CURRENCY,
    locale = DEFAULT_LOCALE,
    showCurrency = true,
    parentheses = false,
    signed = false,
    decimals = 2,
  } = {},
) {
  const decimal = toDecimal(value)
  const fixed = decimal.abs().toFixed(decimals)
  const [integerPart, fractionPart = ''] = fixed.split('.')

  const formatter = getFormatter({ locale, currency, showCurrency, decimals })
  // 1234 solo sirve como plantilla de locale; nunca representa el monto.
  const template = formatter.formatToParts(1234)
  const grouped = groupInteger(integerPart, template)

  let integerEmitted = false
  let fractionEmitted = false
  let rendered = ''

  for (const part of template) {
    if (part.type === 'integer') {
      if (!integerEmitted) {
        rendered += grouped
        integerEmitted = true
      }
    } else if (part.type === 'fraction') {
      if (!fractionEmitted) {
        rendered += fractionPart
        fractionEmitted = true
      }
    } else if (part.type === 'group') {
      // Los separadores de miles ya se insertaron en `grouped`.
    } else if (part.type === 'decimal') {
      if (fractionPart) rendered += part.value
    } else {
      rendered += part.value
    }
  }

  if (decimal.isNegative() && !decimal.isZero()) {
    return parentheses ? `(${rendered})` : `-${rendered}`
  }
  if (signed && decimal.gt(0)) return `+${rendered}`
  return rendered
}

/** Igual que formatMoney pero sin símbolo de moneda, para celdas numéricas. */
function formatAmount(value, options = {}) {
  return formatMoney(value, { ...options, showCurrency: false })
}

export function useCurrency() {
  return {
    Decimal,
    toDecimal,
    toFixed,
    sum,
    subtract,
    multiply,
    divide,
    equals,
    isZero,
    isNegative,
    abs,
    percent,
    formatMoney,
    formatAmount,
  }
}

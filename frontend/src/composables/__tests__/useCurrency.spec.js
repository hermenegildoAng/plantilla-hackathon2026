import { describe, expect, it } from 'vitest'

import { useCurrency } from '../useCurrency'

describe('useCurrency', () => {
  const {
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
  } = useCurrency()

  it('suma importes string sin error de punto flotante', () => {
    expect(sum(['0.1', '0.2'])).toBe('0.30')
    expect(sum(['0.1', '0.2', '0.3'])).toBe('0.60')
    expect(sum(['1.005', '2.005'])).toBe('3.01')
    expect(sum(['1000000.10', '0.20', '-0.30'])).toBe('1000000.00')
  })

  it('ignora valores vacíos o inválidos al sumar', () => {
    expect(sum(['10.00', null, '', undefined, '5.50'])).toBe('15.50')
    expect(sum([])).toBe('0.00')
  })

  it('resta, multiplica y divide con Decimal', () => {
    expect(subtract('100.00', '33.33')).toBe('66.67')
    expect(multiply('1234.56', '0.16')).toBe('197.53')
    expect(divide('100.00', '3')).toBe('33.33')
    expect(divide('100.00', '0')).toBe('0.00')
  })

  it('compara saldos sin tolerancia flotante', () => {
    expect(equals('0.30', sum(['0.1', '0.2']))).toBe(true)
    expect(equals('0.1', '0.10')).toBe(true)
    expect(isZero('0.00')).toBe(true)
    expect(isNegative('-0.01')).toBe(true)
    expect(abs('-12.345')).toBe('12.35')
    expect(percent('25.00', '200.00')).toBe('12.50')
  })

  it('formatea montos en es-MX con dos decimales y signo', () => {
    expect(formatMoney('1234.5')).toContain('1,234.50')
    expect(formatAmount('1234.5')).toBe('1,234.50')
    expect(formatMoney('-5')).toContain('5.00')
    expect(formatMoney('-5', { parentheses: true })).toBe('($5.00)')
    expect(formatMoney('5', { signed: true })).toBe('+$5.00')
  })
})

import { ref } from 'vue'
import { describe, expect, it } from 'vitest'

import {
  buildEntryPayload,
  createEntryLine,
  useEntryForm,
} from '../useEntryForm'

function linesFixture(amounts = []) {
  return ref(
    amounts.map(({ direction, amount, account = 1 }, index) =>
      createEntryLine({
        account,
        direction: direction || 'debit',
        amount,
        key: `test-${index}`,
      }),
    ),
  )
}

describe('useEntryForm', () => {
  it('calcula cargos, abonos y diferencia con Decimal (0.1 + 0.2)', () => {
    const lines = linesFixture([
      { direction: 'debit', amount: '0.1', account: 1 },
      { direction: 'debit', amount: '0.2', account: 2 },
      { direction: 'credit', amount: '0.3', account: 3 },
    ])

    const { debitTotal, creditTotal, difference, isBalanced } = useEntryForm({
      lines,
    })

    expect(debitTotal.value).toBe('0.30')
    expect(creditTotal.value).toBe('0.30')
    expect(difference.value).toBe('0.00')
    expect(isBalanced.value).toBe(true)
  })

  it('detecta un descuadre sin tolerancia de punto flotante', () => {
    const lines = linesFixture([
      { direction: 'debit', amount: '0.1' },
      { direction: 'credit', amount: '0.2' },
    ])

    const { difference, isBalanced, canSave } = useEntryForm({ lines })

    expect(difference.value).toBe('-0.10')
    expect(isBalanced.value).toBe(false)
    expect(canSave.value).toBe(false)
  })

  it('deshabilita Guardar con menos de dos renglones o póliza descuadrada', () => {
    const oneLine = linesFixture([{ direction: 'debit', amount: '10.00' }])
    expect(useEntryForm({ lines: oneLine }).canSave.value).toBe(false)

    const unbalanced = linesFixture([
      { direction: 'debit', amount: '10.00' },
      { direction: 'credit', amount: '9.99' },
    ])
    expect(useEntryForm({ lines: unbalanced }).canSave.value).toBe(false)

    const balanced = linesFixture([
      { direction: 'debit', amount: '10.00' },
      { direction: 'credit', amount: '10.00' },
    ])
    expect(useEntryForm({ lines: balanced }).canSave.value).toBe(true)

    const zero = linesFixture([
      { direction: 'debit', amount: '' },
      { direction: 'credit', amount: '' },
    ])
    expect(useEntryForm({ lines: zero }).canSave.value).toBe(false)
  })

  it('deshabilita Guardar cuando el periodo está en solo lectura', () => {
    const lines = linesFixture([
      { direction: 'debit', amount: '10.00' },
      { direction: 'credit', amount: '10.00' },
    ])

    const { canSave } = useEntryForm({ lines, readOnly: ref(true) })

    expect(canSave.value).toBe(false)
  })

  it('construye el payload con un solo importe y montos string', () => {
    const payload = buildEntryPayload({
      entryType: 'INCOME',
      entryDate: '2026-11-15',
      concept: '  Venta de servicios  ',
      status: 'POSTED',
      fiscalPeriod: '',
      lines: [
        createEntryLine({
          account: 10,
          direction: 'debit',
          amount: '1160.5',
          description: 'Cliente',
        }),
        createEntryLine({
          account: 20,
          direction: 'credit',
          amount: '1160.5',
          description: 'Ingreso',
          document: 7,
        }),
      ],
    })

    expect(payload.concept).toBe('Venta de servicios')
    expect(payload).not.toHaveProperty('fiscal_period')
    expect(payload.items[0]).toMatchObject({
      account: 10,
      debit: '1160.50',
      credit: '0.00',
    })
    expect(payload.items[1]).toMatchObject({
      account: 20,
      debit: '0.00',
      credit: '1160.50',
      document: 7,
    })
    expect(typeof payload.items[0].debit).toBe('string')
  })
})

import { describe, expect, it } from 'vitest'

import { mapEntryApiError, mapPeriodApiError } from '../useEntryErrors'

describe('useEntryErrors', () => {
  it('mapea unbalanced_entry a un mensaje de póliza descuadrada', () => {
    const mapped = mapEntryApiError({
      code: 'unbalanced_entry',
      message: 'Póliza descuadrada',
      errors: [
        {
          field: 'items',
          code: 'unbalanced_entry',
          message: 'Cargos != Abonos',
        },
      ],
    })

    expect(mapped.code).toBe('unbalanced_entry')
    expect(mapped.messages[0]).toContain('descuadrada')
    expect(mapped.fieldErrors).not.toHaveProperty('items')
  })

  it('mapea period_closed y errores por campo del backend', () => {
    const mapped = mapEntryApiError({
      code: 'period_closed',
      errors: [
        {
          field: 'fiscal_period',
          code: 'period_closed',
          message: 'El periodo está cerrado.',
        },
        {
          field: 'entry_date',
          code: 'entry_date_out_of_period',
          message: 'La fecha no corresponde al periodo.',
        },
      ],
    })

    expect(mapped.messages[0]).toContain('cerrado')
    expect(mapped.fieldErrors.fiscal_period).toContain('cerrado')
    expect(mapped.fieldErrors.entry_date).toContain('periodo fiscal')
  })

  it('usa un mensaje genérico cuando el error no trae detalle', () => {
    const mapped = mapEntryApiError({ code: 'unexpected', message: '' })

    expect(mapped.message).toBeTruthy()
    expect(mapped.messages).toHaveLength(1)
  })

  it('mapea los errores de cierre y reapertura de periodos', () => {
    const closeError = mapPeriodApiError({
      code: 'draft_entries_pending',
      errors: [
        {
          field: 'detail',
          code: 'draft_entries_pending',
          message: 'Existen borradores',
        },
      ],
    })
    const reopenError = mapPeriodApiError({
      code: 'min_length',
      errors: [
        {
          field: 'justification',
          code: 'min_length',
          message: 'Muy corta',
        },
      ],
    })

    expect(closeError.message).toContain('borrador')
    expect(reopenError.fieldErrors.justification).toContain('15 caracteres')
  })
})

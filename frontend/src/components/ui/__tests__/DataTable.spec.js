import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import DataTable from '../DataTable.vue'

describe('DataTable', () => {
  it('usa cabecera y pie fijos, alinea importes a la derecha y muestra el cuadre', () => {
    const wrapper = mount(DataTable, {
      props: {
        columns: [
          { key: 'concept', label: 'Concepto', align: 'left' },
          { key: 'amount', label: 'Debe', align: 'right' },
        ],
        rows: [{ id: 1, concept: 'IVA trasladado', amount: '100.00' }],
        totals: { amount: '100.00' },
        balance: { value: '0.00', isBalanced: true },
      },
    })

    expect(wrapper.find('thead').classes()).toContain('sticky')
    expect(wrapper.find('tfoot').classes()).toContain('sticky')
    expect(wrapper.find('tbody td:last-child').classes()).toContain('text-right')
    expect(wrapper.find('tbody td:last-child').classes()).toContain('tabular-nums')
    expect(wrapper.text()).toContain('IVA trasladado')
    expect(wrapper.text()).toContain('Totales')
    expect(wrapper.text()).toContain('Cuadrada')
  })

  it('muestra un estado vacío cuando no hay registros', () => {
    const wrapper = mount(DataTable, {
      props: {
        columns: [{ key: 'concept', label: 'Concepto' }],
        rows: [],
      },
    })

    expect(wrapper.text()).toContain('Sin registros')
  })
})

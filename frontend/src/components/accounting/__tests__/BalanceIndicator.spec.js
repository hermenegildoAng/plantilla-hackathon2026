import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import BalanceIndicator from '../BalanceIndicator.vue'

describe('BalanceIndicator', () => {
  it('muestra Diferencia: $0.00 en verde cuando la póliza está cuadrada', () => {
    const wrapper = mount(BalanceIndicator, {
      props: { difference: '0.00', balanced: true },
    })

    const indicator = wrapper.get('[data-testid="balance-indicator"]')
    expect(indicator.text()).toBe('Diferencia: $0.00')
    expect(indicator.classes()).toContain('bg-emerald-50')
    expect(indicator.classes()).toContain('text-emerald-700')
    expect(wrapper.find('[data-testid="balance-ok"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="balance-alert"]').exists()).toBe(false)
  })

  it('muestra el descuadre en rojo con AlertTriangle', () => {
    const wrapper = mount(BalanceIndicator, {
      props: { difference: '0.10', balanced: false },
    })

    const indicator = wrapper.get('[data-testid="balance-indicator"]')
    expect(indicator.text()).toBe('Diferencia: $0.10')
    expect(indicator.classes()).toContain('bg-rose-50')
    expect(indicator.classes()).toContain('text-rose-700')
    expect(wrapper.find('[data-testid="balance-alert"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="balance-ok"]').exists()).toBe(false)
  })
})

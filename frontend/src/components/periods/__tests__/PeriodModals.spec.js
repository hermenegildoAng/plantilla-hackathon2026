import { mount } from '@vue/test-utils'
import { afterEach, describe, expect, it } from 'vitest'

import ClosePeriodModal from '../ClosePeriodModal.vue'
import ReopenPeriodModal from '../ReopenPeriodModal.vue'

const period = { id: 11, year: 2026, month: 11, is_closed: false }

function mountModal(component, props = {}) {
  return mount(component, {
    attachTo: document.body,
    global: { stubs: { teleport: true } },
    props: {
      modelValue: true,
      period,
      ...props,
    },
  })
}

function buttonByText(wrapper, text) {
  return wrapper
    .findAll('button')
    .find((button) => button.text().includes(text))
}

describe('ClosePeriodModal', () => {
  let wrapper

  afterEach(() => {
    wrapper?.unmount()
    wrapper = null
    document.body.style.overflow = ''
  })

  it('bloquea la confirmación mientras haya pólizas en borrador', () => {
    wrapper = mountModal(ClosePeriodModal, {
      drafts: [
        { id: 1, folio: 'DIA-2026-0001', concept: 'Ajuste pendiente' },
      ],
      documents: [],
    })

    expect(wrapper.text()).toContain('Concluye o elimina las pólizas')
    expect(buttonByText(wrapper, 'Confirmar cierre').attributes('disabled')).toBeDefined()
  })

  it('permite cerrar cuando no hay borradores y advierte documentos pendientes', () => {
    wrapper = mountModal(ClosePeriodModal, {
      drafts: [],
      documents: [{ id: 9, uuid: 'doc-9' }],
    })

    expect(wrapper.text()).toContain('Documentos pendientes de contabilizar')
    const confirm = buttonByText(wrapper, 'Confirmar cierre')
    expect(confirm.attributes('disabled')).toBeUndefined()

    confirm.trigger('click')
    expect(wrapper.emitted('confirm')).toHaveLength(1)
  })
})

describe('ReopenPeriodModal', () => {
  let wrapper

  afterEach(() => {
    wrapper?.unmount()
    wrapper = null
    document.body.style.overflow = ''
  })

  it('exige una justificación de al menos 15 caracteres', async () => {
    wrapper = mountModal(ReopenPeriodModal)
    const textarea = wrapper.get('#reopen-justification')
    const confirm = buttonByText(wrapper, 'Confirmar reapertura')

    expect(confirm.attributes('disabled')).toBeDefined()

    await textarea.setValue('Corto')
    expect(wrapper.get('[data-testid="justification-counter"]').text()).toBe(
      '5 / 15 caracteres',
    )
    expect(confirm.attributes('disabled')).toBeDefined()

    await textarea.setValue('  Reapertura por ajuste fiscal autorizado  ')
    expect(confirm.attributes('disabled')).toBeUndefined()

    await confirm.trigger('click')
    expect(wrapper.emitted('confirm')[0]).toEqual([
      'Reapertura por ajuste fiscal autorizado',
    ])
  })
})

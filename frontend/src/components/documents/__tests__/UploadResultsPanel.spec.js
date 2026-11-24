import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import UploadResultsPanel from '../UploadResultsPanel.vue'

describe('UploadResultsPanel', () => {
  it('renderiza resultados parciales con procesados y fallos del backend', () => {
    const wrapper = mount(UploadResultsPanel, {
      props: {
        result: {
          summary: {
            total_received: 3,
            processed_count: 1,
            failed_count: 2,
          },
          processed: [
            {
              filename: 'FAC_A102.xml',
              document_id: 541,
              uuid: '550e8400-e29b-41d4-a716-446655440000',
              direction: 'RECEIVED',
              total: '4640.00',
            },
          ],
          failed: [
            {
              filename: 'FAC_A099.xml',
              uuid: '7c9e6679-7425-40de-944b-e07fc1f90ae7',
              code: 'duplicate_cfdi_uuid',
              message: 'El UUID ya se encuentra registrado en esta empresa.',
            },
            {
              filename: 'FAC_OCT_01.xml',
              uuid: '3fa85f64-5717-4562-b3fc-2c963f66afa6',
              code: 'period_closed',
              message: 'El periodo fiscal 2026-10 se encuentra cerrado.',
            },
          ],
        },
      },
    })

    const text = wrapper.text()
    expect(text).toContain('1 comprobante importado')
    expect(text).toContain('2 con errores')
    expect(text).toContain('FAC_A102.xml')
    expect(text).toContain('550e8400-e29b-41d4-a716-446655440000')
    expect(text).toContain('duplicate_cfdi_uuid')
    expect(text).toContain(
      'El UUID ya se encuentra registrado en esta empresa.',
    )
    expect(text).toContain('period_closed')
    expect(text).toContain('El periodo fiscal 2026-10 se encuentra cerrado.')
  })

  it('no muestra el panel si no hay resultado', () => {
    const wrapper = mount(UploadResultsPanel, { props: { result: null } })
    expect(wrapper.find('section').exists()).toBe(false)
  })
})

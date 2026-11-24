import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import { XML_MAX_BYTES } from '../../../utils/documentFiles'
import DropzoneUploader from '../DropzoneUploader.vue'

describe('DropzoneUploader', () => {
  it('valida el tamaño antes de enviar y lo refleja en el panel de resultados', async () => {
    const wrapper = mount(DropzoneUploader)
    const oversized = {
      name: 'comprobante-grande.xml',
      size: XML_MAX_BYTES + 1,
    }

    await wrapper.vm.handleFiles([oversized])

    const text = wrapper.text()
    expect(text).toContain('file_too_large')
    expect(text).toContain('2 MB')
    expect(text).toContain('0 comprobantes importados')
    expect(text).toContain('1 con error')
  })
})

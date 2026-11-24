import { describe, expect, it } from 'vitest'

import {
  MAX_FILES_PER_REQUEST,
  PDF_MAX_BYTES,
  XML_MAX_BYTES,
  partitionDocumentFiles,
  splitIntoBatches,
  validateDocumentFile,
} from '../documentFiles'

function fakeFile(name, size = 128) {
  return { name, size }
}

describe('splitIntoBatches', () => {
  it('divide 120 archivos en lotes de máximo 50', () => {
    const files = Array.from({ length: 120 }, (_, index) =>
      fakeFile(`comprobante-${index}.xml`),
    )

    const batches = splitIntoBatches(files)

    expect(batches.map((batch) => batch.length)).toEqual([50, 50, 20])
    expect(batches.flat()).toHaveLength(120)
    expect(batches.every((batch) => batch.length <= MAX_FILES_PER_REQUEST)).toBe(
      true,
    )
  })

  it('mantiene juntos el XML y su PDF con el mismo nombre base', () => {
    const files = [
      fakeFile('factura.xml'),
      fakeFile('factura.pdf'),
      ...Array.from({ length: 48 }, (_, index) =>
        fakeFile(`otro-${index}.xml`),
      ),
    ]

    const batches = splitIntoBatches(files)
    const firstBatchNames = batches[0].map((file) => file.name)

    expect(firstBatchNames).toContain('factura.xml')
    expect(firstBatchNames).toContain('factura.pdf')
    expect(batches.every((batch) => batch.length <= 50)).toBe(true)
  })
})

describe('validateDocumentFile', () => {
  it('acepta XML hasta 2 MB y rechaza los que exceden el límite', () => {
    expect(validateDocumentFile(fakeFile('factura.xml', XML_MAX_BYTES)).valid).toBe(
      true,
    )

    const tooLarge = validateDocumentFile(
      fakeFile('factura.xml', XML_MAX_BYTES + 1),
    )
    expect(tooLarge.valid).toBe(false)
    expect(tooLarge.code).toBe('file_too_large')
    expect(tooLarge.message).toContain('2 MB')
  })

  it('acepta PDF hasta 5 MB y rechaza los que exceden el límite', () => {
    expect(validateDocumentFile(fakeFile('respaldo.pdf', PDF_MAX_BYTES)).valid).toBe(
      true,
    )

    const tooLarge = validateDocumentFile(
      fakeFile('respaldo.pdf', PDF_MAX_BYTES + 1),
    )
    expect(tooLarge.valid).toBe(false)
    expect(tooLarge.code).toBe('file_too_large')
    expect(tooLarge.message).toContain('5 MB')
  })

  it('rechaza extensiones no permitidas y archivos vacíos', () => {
    const wrongExtension = validateDocumentFile(fakeFile('nota.txt'))
    expect(wrongExtension.valid).toBe(false)
    expect(wrongExtension.code).toBe('invalid_file_type')

    const empty = validateDocumentFile(fakeFile('vacio.xml', 0))
    expect(empty.valid).toBe(false)
    expect(empty.code).toBe('empty_file')
  })

  it('separa archivos aceptados y rechazados para la cola', () => {
    const { accepted, rejected } = partitionDocumentFiles([
      fakeFile('ok.xml', 1024),
      fakeFile('grande.pdf', PDF_MAX_BYTES + 1),
      fakeFile('malo.txt', 10),
    ])

    expect(accepted.map((file) => file.name)).toEqual(['ok.xml'])
    expect(rejected.map((item) => item.code)).toEqual([
      'file_too_large',
      'invalid_file_type',
    ])
  })
})

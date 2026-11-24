/**
 * Reglas de archivo de la bóveda fiscal (04 §4.4, E-04, E-06).
 *
 * Se mantienen fuera del componente para poder probar la validación y la
 * división de lotes sin montar la interfaz ni tocar el DOM.
 */

export const MAX_FILES_PER_REQUEST = 50
export const XML_MAX_BYTES = 2 * 1024 * 1024
export const PDF_MAX_BYTES = 5 * 1024 * 1024

export const DOCUMENT_FILE_RULES = {
  xml: {
    extension: 'xml',
    maxBytes: XML_MAX_BYTES,
    maxLabel: '2 MB',
    label: 'XML',
  },
  pdf: {
    extension: 'pdf',
    maxBytes: PDF_MAX_BYTES,
    maxLabel: '5 MB',
    label: 'PDF',
  },
}

const ALLOWED_EXTENSIONS = Object.keys(DOCUMENT_FILE_RULES)

export function fileExtension(name = '') {
  const match = String(name).toLowerCase().match(/\.([a-z0-9]+)$/)
  return match ? match[1] : ''
}

export function fileBaseName(name = '') {
  return String(name).replace(/\.[^.]+$/, '')
}

export function isAllowedDocumentFile(file) {
  return ALLOWED_EXTENSIONS.includes(fileExtension(file?.name))
}

/**
 * Valida extensión y tamaño antes de enviar. Devuelve el mismo contrato que
 * usa el backend para que el panel de resultados pueda mostrar código y
 * mensaje en español incluso cuando el archivo nunca salió del navegador.
 */
export function validateDocumentFile(file) {
  const extension = fileExtension(file?.name)
  const rule = DOCUMENT_FILE_RULES[extension]

  if (!rule) {
    return {
      valid: false,
      extension,
      code: 'invalid_file_type',
      message: 'Solo se permiten archivos con extensión .xml o .pdf.',
    }
  }

  if (!file || typeof file.size !== 'number' || file.size <= 0) {
    return {
      valid: false,
      extension,
      code: 'empty_file',
      message: `El archivo ${file?.name || 'seleccionado'} está vacío.`,
    }
  }

  if (file.size > rule.maxBytes) {
    return {
      valid: false,
      extension,
      code: 'file_too_large',
      message:
        `El archivo ${file.name} excede el tamaño máximo de ` +
        `${rule.maxLabel} para ${rule.label}.`,
    }
  }

  return { valid: true, extension, code: null, message: null }
}

export function partitionDocumentFiles(files = []) {
  const accepted = []
  const rejected = []

  Array.from(files || []).forEach((file) => {
    const validation = validateDocumentFile(file)
    if (validation.valid) {
      accepted.push(file)
    } else {
      rejected.push({ file, ...validation })
    }
  })

  return { accepted, rejected }
}

/**
 * Agrupa por nombre base para no separar un XML de su PDF en el mismo lote.
 * Cada lote respeta el máximo de 50 archivos por petición.
 */
export function splitIntoBatches(files = [], maxFiles = MAX_FILES_PER_REQUEST) {
  const list = Array.from(files || [])
  if (list.length === 0) return []

  const size = Math.max(1, Number(maxFiles) || MAX_FILES_PER_REQUEST)
  const groups = new Map()

  list.forEach((file) => {
    const key = fileBaseName(file?.name).toLowerCase()
    if (!groups.has(key)) groups.set(key, [])
    groups.get(key).push(file)
  })

  const batches = []
  let current = []

  function flush() {
    if (current.length > 0) {
      batches.push(current)
      current = []
    }
  }

  groups.forEach((group) => {
    if (group.length > size) {
      flush()
      for (let index = 0; index < group.length; index += size) {
        batches.push(group.slice(index, index + size))
      }
      return
    }

    if (current.length + group.length > size) flush()
    current.push(...group)
  })

  flush()
  return batches
}

export function formatFileSize(bytes = 0) {
  const value = Number(bytes) || 0
  if (value < 1024) return `${value} B`
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`
  return `${(value / (1024 * 1024)).toFixed(2)} MB`
}

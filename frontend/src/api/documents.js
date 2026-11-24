import { api } from './http'

const MAX_PAGE_SIZE = 100
const MAX_PAGES = 200

async function fetchAllPages(path, params = {}) {
  const pageSize = Math.min(
    Number(params.page_size) || MAX_PAGE_SIZE,
    MAX_PAGE_SIZE,
  )
  const results = []
  let page = 1
  let count = 0

  while (page <= MAX_PAGES) {
    const payload = await api.get(path, {
      params: { ...params, page, page_size: pageSize },
    })
    const pageResults = Array.isArray(payload?.results) ? payload.results : []
    results.push(...pageResults)
    count = Number(payload?.count ?? results.length)

    if (!payload?.next || pageResults.length === 0) break
    page += 1
  }

  return { results, count }
}

export function listDocuments(params = {}) {
  return api.get('/documents/', { params })
}

/** Se usa para totalizadores: recorre todas las páginas del filtro activo. */
export function listAllDocuments(params = {}) {
  return fetchAllPages('/documents/', params)
}

export function listAllPeriods(params = {}) {
  return fetchAllPages('/periods/', params)
}

export function bulkUploadDocuments(files, { direction = '', onUploadProgress } = {}) {
  const formData = new FormData()
  Array.from(files).forEach((file) => {
    formData.append('files', file, file.name)
  })
  if (direction) formData.append('direction', direction)

  return api.post('/documents/bulk-upload/', formData, {
    onUploadProgress,
  })
}

export function createManualDocument(payload) {
  const formData = new FormData()
  Object.entries(payload).forEach(([key, value]) => {
    if (value === undefined || value === null || value === '') return
    formData.append(key, value)
  })
  return api.post('/documents/manual/', formData)
}

export function attachDocumentPdf(documentId, file) {
  const formData = new FormData()
  formData.append('pdf_file', file, file.name)
  return api.post(`/documents/${documentId}/pdf/`, formData)
}

export function deleteDocument(documentId) {
  return api.delete(`/documents/${documentId}/`)
}

export function downloadDocumentFile(documentId, kind) {
  return api.get(`/documents/${documentId}/download/`, {
    params: { file: kind },
    responseType: 'blob',
  })
}

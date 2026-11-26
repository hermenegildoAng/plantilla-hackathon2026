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

export function listEntries(params = {}) {
  return api.get('/entries/', { params })
}

export function listAllEntries(params = {}) {
  return fetchAllPages('/entries/', params)
}

export function getEntry(entryId) {
  return api.get(`/entries/${entryId}/`)
}

export function createEntry(payload) {
  return api.post('/entries/', payload)
}

export function updateEntry(entryId, payload) {
  return api.put(`/entries/${entryId}/`, payload)
}

export function deleteEntry(entryId) {
  return api.delete(`/entries/${entryId}/`)
}

export function listPeriods(params = {}) {
  return api.get('/periods/', { params })
}

export function listAllPeriods(params = {}) {
  return fetchAllPages('/periods/', params)
}

export function closePeriod(periodId) {
  return api.post(`/periods/${periodId}/close/`)
}

export function reopenPeriod(periodId, justification) {
  return api.post(`/periods/${periodId}/reopen/`, { justification })
}

export function listAccounts(params = {}) {
  return api.get('/accounts/', { params })
}

export function listAllAccounts(params = {}) {
  return fetchAllPages('/accounts/', params)
}

export function createAccount(payload) {
  return api.post('/accounts/', payload)
}

export function updateAccount(accountId, payload) {
  return api.patch(`/accounts/${accountId}/`, payload)
}

export function deleteAccount(accountId) {
  return api.delete(`/accounts/${accountId}/`)
}

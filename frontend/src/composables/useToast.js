import { reactive } from 'vue'

const DEFAULT_TITLES = {
  success: 'Operación exitosa',
  error: 'Error',
  warning: 'Advertencia',
  info: 'Información',
}

const toasts = reactive([])
let counter = 0

function removeToast(id) {
  const index = toasts.findIndex((toast) => toast.id === id)
  if (index !== -1) toasts.splice(index, 1)
}

function pushToast(input) {
  const options = typeof input === 'string' ? { message: input } : { ...input }
  const type = options.type || 'info'
  const id = ++counter
  const toast = {
    id,
    type,
    title: options.title || DEFAULT_TITLES[type] || DEFAULT_TITLES.info,
    message: options.message || '',
    duration: options.duration ?? 5000,
  }

  toasts.push(toast)

  if (toast.duration > 0 && typeof window !== 'undefined') {
    window.setTimeout(() => removeToast(id), toast.duration)
  }
  return id
}

function success(message, options = {}) {
  return pushToast({ ...options, type: 'success', message })
}

function error(message, options = {}) {
  return pushToast({ ...options, type: 'error', message })
}

function warning(message, options = {}) {
  return pushToast({ ...options, type: 'warning', message })
}

function info(message, options = {}) {
  return pushToast({ ...options, type: 'info', message })
}

function clear() {
  toasts.splice(0, toasts.length)
}

export function useToast() {
  return {
    toasts,
    pushToast,
    removeToast,
    success,
    error,
    warning,
    info,
    clear,
  }
}

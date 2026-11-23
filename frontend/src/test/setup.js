import { afterEach, beforeEach, vi } from 'vitest'

import { useToast } from '../composables/useToast'

beforeEach(() => {
  localStorage.clear()
  document.body.innerHTML = ''
  document.body.style.overflow = ''
  useToast().clear()
  // jsdom no implementa scrollTo; el router lo usa en scrollBehavior.
  window.scrollTo = () => {}
})

afterEach(() => {
  vi.useRealTimers()
})

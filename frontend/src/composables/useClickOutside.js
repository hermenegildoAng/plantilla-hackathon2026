import { onBeforeUnmount, onMounted } from 'vue'

/** Cierra un dropdown al hacer clic fuera del elemento o presionar Escape. */
export function useClickOutside(elementRef, onOutside) {
  function handlePointer(event) {
    const element = elementRef.value
    if (!element) return
    if (element.contains(event.target)) return
    onOutside(event)
  }

  function handleKeydown(event) {
    if (event.key === 'Escape') onOutside(event)
  }

  onMounted(() => {
    document.addEventListener('pointerdown', handlePointer)
    document.addEventListener('keydown', handleKeydown)
  })

  onBeforeUnmount(() => {
    document.removeEventListener('pointerdown', handlePointer)
    document.removeEventListener('keydown', handleKeydown)
  })
}

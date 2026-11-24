<script setup>
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { AlertCircle, FileText, Paperclip, UploadCloud, X } from 'lucide-vue-next'

import { attachDocumentPdf } from '../../api/documents'
import { useToast } from '../../composables/useToast'
import { formatFileSize, validateDocumentFile } from '../../utils/documentFiles'
import BaseButton from '../ui/BaseButton.vue'

const props = defineProps({
  modelValue: Boolean,
  document: {
    type: Object,
    default: null,
  },
})

const emit = defineEmits(['update:modelValue', 'attached'])

const toast = useToast()
const fileInput = ref(null)
const file = ref(null)
const error = ref('')
const submitting = ref(false)

const documentLabel = computed(() => {
  if (!props.document) return 'documento'
  return (
    props.document.uuid ||
    props.document.original_filename ||
    props.document.folio ||
    `documento ${props.document.id}`
  )
})

const hasExistingPdf = computed(() => Boolean(props.document?.pdf_url))

function reset() {
  file.value = null
  error.value = ''
  submitting.value = false
}

function close(force = false) {
  if (submitting.value && !force) return
  emit('update:modelValue', false)
}

function selectFile() {
  if (submitting.value) return
  fileInput.value?.click()
}

function onFileChange(event) {
  const selected = event.target?.files?.[0]
  event.target.value = ''
  if (!selected) return

  const validation = validateDocumentFile(selected)
  if (!validation.valid) {
    file.value = null
    error.value = validation.message
    return
  }

  file.value = selected
  error.value = ''
}

async function submit() {
  if (submitting.value || !props.document) return
  if (!file.value) {
    error.value = 'Selecciona el archivo PDF que deseas adjuntar.'
    return
  }

  const validation = validateDocumentFile(file.value)
  if (!validation.valid) {
    error.value = validation.message
    return
  }

  submitting.value = true
  error.value = ''
  try {
    const updated = await attachDocumentPdf(props.document.id, file.value)
    toast.success('PDF adjuntado correctamente.')
    emit('attached', updated)
    close(true)
  } catch (submitError) {
    error.value =
      submitError?.message || 'No fue posible adjuntar el PDF al documento.'
  } finally {
    submitting.value = false
  }
}

function handleKeydown(event) {
  if (!props.modelValue) return
  if (event.key === 'Escape' && !submitting.value) close()
}

watch(
  () => props.modelValue,
  async (open) => {
    if (typeof document !== 'undefined') {
      document.body.style.overflow = open ? 'hidden' : ''
      if (open) {
        reset()
        document.addEventListener('keydown', handleKeydown)
        await nextTick()
      } else {
        document.removeEventListener('keydown', handleKeydown)
      }
    }
  },
  { immediate: true },
)

onBeforeUnmount(() => {
  if (typeof document !== 'undefined') {
    document.body.style.overflow = ''
    document.removeEventListener('keydown', handleKeydown)
  }
})
</script>

<template>
  <Teleport to="body">
    <Transition
      enter-active-class="transition duration-150 ease-out"
      enter-from-class="opacity-0"
      enter-to-class="opacity-100"
      leave-active-class="transition duration-100 ease-in"
      leave-from-class="opacity-100"
      leave-to-class="opacity-0"
    >
      <div
        v-if="modelValue"
        class="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4 backdrop-blur-[1px]"
        role="presentation"
        @click.self="!submitting && close()"
      >
        <div
          class="w-full max-w-md overflow-hidden rounded-lg border border-slate-200 bg-white shadow-xl"
          role="dialog"
          aria-modal="true"
          aria-labelledby="attach-pdf-title"
        >
          <header class="flex items-start gap-3 border-b border-slate-200 px-4 py-3">
            <div
              class="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-indigo-100 text-indigo-700"
            >
              <Paperclip class="w-4 h-4" aria-hidden="true" />
            </div>
            <div class="min-w-0 flex-1">
              <h2 id="attach-pdf-title" class="text-sm font-semibold text-slate-900">
                {{ hasExistingPdf ? 'Reemplazar PDF' : 'Adjuntar PDF' }}
              </h2>
              <p class="mt-0.5 text-[11px] text-slate-500">
                Documento:
                <span class="font-mono text-slate-700">{{ documentLabel }}</span>
              </p>
            </div>
            <button
              type="button"
              class="rounded-md p-1 text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-600 focus:outline-none focus:ring-2 focus:ring-indigo-500"
              aria-label="Cerrar"
              :disabled="submitting"
              @click="close"
            >
              <X class="w-4 h-4" aria-hidden="true" />
            </button>
          </header>

          <div class="px-4 py-3">
            <div
              v-if="error"
              class="mb-3 flex items-start gap-2 rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-[11px] text-rose-800"
              role="alert"
            >
              <AlertCircle class="mt-0.5 w-3.5 h-3.5 shrink-0" aria-hidden="true" />
              <p>{{ error }}</p>
            </div>

            <div
              class="flex flex-wrap items-center gap-2 rounded-md border border-dashed border-slate-300 bg-slate-50/60 px-3 py-3"
            >
              <div
                class="flex h-8 w-8 items-center justify-center rounded-md bg-white text-rose-500 shadow-sm"
              >
                <FileText v-if="file" class="w-4 h-4" aria-hidden="true" />
                <UploadCloud v-else class="w-4 h-4" aria-hidden="true" />
              </div>
              <div class="min-w-0 flex-1">
                <p v-if="file" class="truncate text-xs font-medium text-slate-800">
                  {{ file.name }}
                </p>
                <p v-else class="text-xs text-slate-600">
                  Selecciona la representación impresa en PDF.
                </p>
                <p class="text-[10px] text-slate-500">
                  PDF ≤ 5 MB
                  <span v-if="file"> · {{ formatFileSize(file.size) }}</span>
                </p>
              </div>
              <BaseButton
                variant="secondary"
                size="sm"
                :disabled="submitting"
                @click="selectFile"
              >
                {{ file ? 'Cambiar PDF' : 'Seleccionar PDF' }}
              </BaseButton>
              <input
                ref="fileInput"
                type="file"
                class="hidden"
                accept=".pdf,application/pdf"
                :disabled="submitting"
                @change="onFileChange"
              />
            </div>

            <p v-if="hasExistingPdf" class="mt-2 text-[11px] text-amber-700">
              Este documento ya tiene un PDF. Al adjuntar uno nuevo se reemplazará
              el anterior.
            </p>
          </div>

          <footer
            class="flex justify-end gap-2 border-t border-slate-200 bg-slate-50 px-4 py-2.5"
          >
            <BaseButton variant="secondary" :disabled="submitting" @click="close">
              Cancelar
            </BaseButton>
            <BaseButton :loading="submitting" :disabled="!file" @click="submit">
              {{ hasExistingPdf ? 'Reemplazar PDF' : 'Adjuntar PDF' }}
            </BaseButton>
          </footer>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

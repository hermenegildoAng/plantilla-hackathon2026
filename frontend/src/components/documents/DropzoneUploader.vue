<script setup>
import { computed, ref } from 'vue'
import {
  AlertCircle,
  CheckCircle2,
  FileCode2,
  FileText,
  Loader2,
  UploadCloud,
  X,
} from 'lucide-vue-next'

import { bulkUploadDocuments } from '../../api/documents'
import {
  fileBaseName,
  fileExtension,
  formatFileSize,
  MAX_FILES_PER_REQUEST,
  partitionDocumentFiles,
  splitIntoBatches,
} from '../../utils/documentFiles'
import BaseBadge from '../ui/BaseBadge.vue'
import BaseButton from '../ui/BaseButton.vue'
import UploadResultsPanel from './UploadResultsPanel.vue'

const props = defineProps({
  disabled: Boolean,
  direction: {
    type: String,
    default: '',
  },
})

const emit = defineEmits(['completed'])

const fileInput = ref(null)
const dragActive = ref(false)
const busy = ref(false)
const queue = ref([])
const batches = ref([])
const result = ref(null)

let itemCounter = 0

const rejectedCount = computed(
  () => queue.value.filter((item) => item.status === 'rejected').length,
)

function nextItemId() {
  itemCounter += 1
  return itemCounter
}

function iconFor(item) {
  return item.extension === 'pdf' ? FileText : FileCode2
}

function statusLabel(item) {
  if (item.status === 'uploading') return 'Subiendo'
  if (item.status === 'processed') {
    return item.paired ? 'PDF emparejado' : 'Procesado'
  }
  if (item.status === 'failed') return 'Error'
  if (item.status === 'rejected') return 'No válido'
  return 'En cola'
}

function statusVariant(item) {
  if (item.status === 'processed') return 'success'
  if (item.status === 'failed' || item.status === 'rejected') return 'danger'
  if (item.status === 'uploading') return 'info'
  return 'neutral'
}

function openPicker() {
  if (props.disabled || busy.value) return
  fileInput.value?.click()
}

function onKeydown(event) {
  if (event.key !== 'Enter' && event.key !== ' ') return
  event.preventDefault()
  openPicker()
}

function onDragOver(event) {
  event.preventDefault()
  if (props.disabled || busy.value) return
  dragActive.value = true
}

function onDragLeave(event) {
  if (event.currentTarget?.contains?.(event.relatedTarget)) return
  dragActive.value = false
}

function onDrop(event) {
  event.preventDefault()
  dragActive.value = false
  if (props.disabled || busy.value) return
  handleFiles(event.dataTransfer?.files)
}

function onFileChange(event) {
  const files = event.target?.files
  event.target.value = ''
  handleFiles(files)
}

function markBatchItems(items, processedItems, failedItems) {
  const pending = [...items]

  function takeByFilename(filename) {
    const index = pending.findIndex((item) => item.name === filename)
    if (index === -1) return null
    return pending.splice(index, 1)[0]
  }

  processedItems.forEach((processed) => {
    const item = takeByFilename(processed.filename)
    if (!item) return
    item.status = 'processed'
    item.progress = 100
    item.document = processed
  })

  failedItems.forEach((failure) => {
    const item = takeByFilename(failure.filename)
    if (!item) return
    item.status = 'failed'
    item.progress = 100
    item.code = failure.code
    item.message = failure.message
  })

  // El backend procesa el XML y adjunta el PDF; no reporta el PDF por
  // separado. Si el XML del mismo nombre base fue procesado, el PDF también
  // se considera exitoso.
  for (let index = pending.length - 1; index >= 0; index -= 1) {
    const item = pending[index]
    if (item.extension !== 'pdf') continue
    const stem = fileBaseName(item.name).toLowerCase()
    const paired = processedItems.some(
      (processed) =>
        fileBaseName(processed.filename).toLowerCase() === stem,
    )
    if (!paired) continue
    item.status = 'processed'
    item.paired = true
    item.progress = 100
    pending.splice(index, 1)
  }

  pending.forEach((item) => {
    item.status = 'failed'
    item.progress = 100
    item.code = 'not_processed'
    item.message = 'El servidor no reportó resultado para este archivo.'
  })
}

async function processQueue(acceptedItems) {
  busy.value = true

  const itemBatches = splitIntoBatches(acceptedItems)
  batches.value = itemBatches.map((items, index) => ({
    index: index + 1,
    total: itemBatches.length,
    items,
    progress: 0,
    status: 'pending',
  }))

  for (const batch of batches.value) {
    batch.status = 'uploading'
    batch.items.forEach((item) => {
      item.status = 'uploading'
      item.progress = 0
      item.batch = batch.index
    })

    try {
      const data = await bulkUploadDocuments(
        batch.items.map((item) => item.file),
        {
          direction: props.direction,
          onUploadProgress: (event) => {
            if (!event?.total) return
            batch.progress = Math.min(
              99,
              Math.round((event.loaded * 100) / event.total),
            )
            batch.items.forEach((item) => {
              item.progress = batch.progress
            })
          },
        },
      )

      batch.progress = 100
      batch.status = 'done'
      markBatchItems(batch.items, data?.processed || [], data?.failed || [])
    } catch (error) {
      batch.status = 'error'
      const code = error?.code || 'upload_failed'
      const message =
        error?.message || 'No fue posible procesar este lote de archivos.'

      batch.items.forEach((item) => {
        item.status = 'failed'
        item.progress = 100
        item.code = code
        item.message = message
      })
    }
  }

  const processed = queue.value
    .filter((item) => item.status === 'processed' && item.document)
    .map((item) => item.document)

  const failed = queue.value
    .filter((item) => item.status === 'failed' || item.status === 'rejected')
    .map((item) => ({
      filename: item.name,
      uuid: item.document?.uuid || null,
      code: item.code || 'upload_failed',
      message: item.message || 'No fue posible procesar el archivo.',
    }))

  result.value = {
    summary: {
      total_received: queue.value.length,
      processed_count: processed.length,
      failed_count: failed.length,
    },
    processed,
    failed,
  }

  busy.value = false
  emit('completed', result.value)
}

async function handleFiles(fileList) {
  if (props.disabled || busy.value) return

  const files = Array.from(fileList || [])
  if (files.length === 0) return

  result.value = null
  batches.value = []

  const { accepted, rejected } = partitionDocumentFiles(files)

  const acceptedItems = accepted.map((file) => ({
    id: nextItemId(),
    file,
    name: file.name,
    size: file.size,
    extension: fileExtension(file.name),
    status: 'pending',
    progress: 0,
    batch: null,
    code: null,
    message: null,
    document: null,
    paired: false,
  }))

  const rejectedItems = rejected.map(({ file, code, message, extension }) => ({
    id: nextItemId(),
    file,
    name: file.name,
    size: file.size,
    extension,
    status: 'rejected',
    progress: 0,
    batch: null,
    code,
    message,
    document: null,
    paired: false,
  }))

  queue.value = [...acceptedItems, ...rejectedItems]

  if (acceptedItems.length === 0) {
    const failed = rejectedItems.map((item) => ({
      filename: item.name,
      uuid: null,
      code: item.code,
      message: item.message,
    }))
    result.value = {
      summary: {
        total_received: files.length,
        processed_count: 0,
        failed_count: failed.length,
      },
      processed: [],
      failed,
    }
    emit('completed', result.value)
    return
  }

  await processQueue(acceptedItems)
}

function reset() {
  if (busy.value) return
  queue.value = []
  batches.value = []
  result.value = null
}

defineExpose({ handleFiles, reset })
</script>

<template>
  <section class="rounded-lg border border-slate-200 bg-white p-3 shadow-sm">
    <div
      role="button"
      tabindex="0"
      class="rounded-lg border-2 border-dashed border-slate-300 bg-slate-50/50 p-6 text-center transition-colors focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-1"
      :class="[
        dragActive
          ? 'border-indigo-600 bg-indigo-50/80 ring-2 ring-indigo-500/20'
          : 'hover:border-indigo-400 hover:bg-indigo-50/30',
        disabled || busy ? 'cursor-not-allowed opacity-60' : 'cursor-pointer',
      ]"
      :aria-disabled="disabled || busy ? 'true' : undefined"
      :aria-busy="busy || undefined"
      @click="openPicker"
      @keydown="onKeydown"
      @dragover="onDragOver"
      @dragenter="onDragOver"
      @dragleave="onDragLeave"
      @drop="onDrop"
    >
      <UploadCloud class="w-8 h-8 mx-auto mb-2 text-indigo-500" aria-hidden="true" />
      <p class="text-xs font-semibold text-slate-700">
        Arrastra tus archivos XML o PDF aquí
      </p>
      <p class="text-[11px] text-slate-500">
        Soporta carga masiva de múltiples CFDI (.xml) y representaciones
        impresas (.pdf)
      </p>
      <p class="mt-1.5 text-[10px] text-slate-500">
        XML ≤ 2 MB · PDF ≤ 5 MB · máximo {{ MAX_FILES_PER_REQUEST }} por petición.
        Los lotes mayores se dividen automáticamente.
      </p>

      <input
        ref="fileInput"
        type="file"
        class="hidden"
        multiple
        accept=".xml,.pdf,application/xml,text/xml,application/pdf"
        :disabled="disabled || busy"
        @click.stop
        @change="onFileChange"
      />
    </div>

    <div
      v-if="queue.length > 0"
      class="mt-3 overflow-hidden rounded-md border border-slate-200 bg-white"
    >
      <header
        class="flex items-center justify-between gap-2 border-b border-slate-200 px-3 py-2"
      >
        <p class="text-[11px] font-semibold text-slate-700">
          Cola de procesamiento
          <span class="font-normal text-slate-500">
            · {{ queue.length }} archivo{{ queue.length === 1 ? '' : 's' }}
            <span v-if="rejectedCount > 0">
              ({{ rejectedCount }} rechazado{{ rejectedCount === 1 ? '' : 's' }}
              en el cliente)
            </span>
          </span>
        </p>
        <div class="flex items-center gap-2">
          <Loader2
            v-if="busy"
            class="w-3.5 h-3.5 animate-spin text-indigo-600"
            aria-hidden="true"
          />
          <BaseButton
            v-else
            variant="ghost"
            size="sm"
            title="Limpiar cola"
            @click="reset"
          >
            <template #icon>
              <X class="w-3.5 h-3.5" aria-hidden="true" />
            </template>
            Limpiar
          </BaseButton>
        </div>
      </header>

      <div
        v-if="batches.length > 0"
        class="space-y-1.5 border-b border-slate-200 px-3 py-2"
      >
        <div v-for="batch in batches" :key="`batch-${batch.index}`">
          <div class="flex items-center justify-between text-[10px] text-slate-500">
            <span>
              Lote {{ batch.index }} de {{ batch.total }}
              <span v-if="batch.status === 'error'" class="text-rose-700">
                · error de envío
              </span>
            </span>
            <span class="tabular-nums">{{ batch.progress }}%</span>
          </div>
          <div class="mt-0.5 h-1 w-full overflow-hidden rounded-full bg-slate-200">
            <div
              class="h-1 rounded-full transition-all"
              :class="batch.status === 'error' ? 'bg-rose-600' : 'bg-indigo-600'"
              :style="{ width: `${batch.progress}%` }"
            />
          </div>
        </div>
      </div>

      <ul class="divide-y divide-slate-100">
        <li
          v-for="item in queue"
          :key="item.id"
          class="flex items-start gap-2 px-3 py-2"
        >
          <component
            :is="iconFor(item)"
            class="mt-0.5 w-4 h-4 shrink-0"
            :class="item.extension === 'pdf' ? 'text-rose-500' : 'text-indigo-500'"
            aria-hidden="true"
          />

          <div class="min-w-0 flex-1">
            <div class="flex items-center justify-between gap-2">
              <p class="truncate text-xs font-medium text-slate-800" :title="item.name">
                {{ item.name }}
              </p>
              <span class="shrink-0 text-[10px] tabular-nums text-slate-500">
                {{ formatFileSize(item.size) }}
              </span>
            </div>

            <div
              v-if="item.status === 'uploading'"
              class="mt-1 flex items-center gap-2"
            >
              <div class="h-1 flex-1 overflow-hidden rounded-full bg-slate-200">
                <div
                  class="h-1 rounded-full bg-indigo-600 transition-all"
                  :style="{ width: `${item.progress}%` }"
                />
              </div>
              <span class="w-8 text-right text-[10px] tabular-nums text-slate-500">
                {{ item.progress }}%
              </span>
            </div>

            <div v-else class="mt-1 flex flex-wrap items-center gap-1.5">
              <BaseBadge :variant="statusVariant(item)" dot>
                <template #icon>
                  <CheckCircle2
                    v-if="item.status === 'processed'"
                    class="w-3 h-3"
                    aria-hidden="true"
                  />
                  <AlertCircle
                    v-else-if="item.status === 'failed' || item.status === 'rejected'"
                    class="w-3 h-3"
                    aria-hidden="true"
                  />
                </template>
                {{ statusLabel(item) }}
              </BaseBadge>
              <code
                v-if="item.code"
                class="font-mono text-[10px] text-rose-700"
              >
                {{ item.code }}
              </code>
            </div>

            <p
              v-if="item.message"
              class="mt-0.5 text-[11px] leading-relaxed text-slate-600"
            >
              {{ item.message }}
            </p>
          </div>
        </li>
      </ul>
    </div>

    <UploadResultsPanel :result="result" class="mt-3" />
  </section>
</template>

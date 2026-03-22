import { ref, onUnmounted } from 'vue'
import { exportForm } from '@/api/forms'
import { getTaskStatus } from '@/api/tasks'
import { getErrorMessage } from '@/utils/error'

/**
 * Validate that a download URL belongs to an allowed origin.
 * Prevents opening arbitrary URLs from potentially tampered API responses.
 */
export function isAllowedDownloadUrl(url: string): boolean {
  try {
    const parsed = new URL(url)
    if (parsed.origin === window.location.origin) return true
    // Dev: allow local MinIO
    if (parsed.origin === 'http://localhost:19000') return true
    return false
  } catch {
    return false
  }
}

export type ExportStatus = 'idle' | 'pending' | 'done' | 'error'

export interface UseFormExportOptions {
  onStatusMessage?: (msg: string) => void
  onError?: (msg: string) => void
  onSuccess?: (downloadUrl: string) => void
  onTimeout?: () => void
  /** Max poll attempts before timing out (default: 60) */
  maxAttempts?: number
  /** Poll interval in ms (default: 3000) */
  pollInterval?: number
}

export interface ExportMessages {
  starting: string
  statusPrefix: string
  timeout: string
  failed: string
  error: string
}

export function useFormExport(options: UseFormExportOptions = {}) {
  const { maxAttempts = 60, pollInterval = 3000 } = options

  const exportStatus = ref<ExportStatus>('idle')
  const exportStatusMessage = ref<string>('')
  const exportUrl = ref<string | null>(null)
  const exportingFormId = ref<string | null>(null)
  const exportElapsed = ref(0)

  let pollTimer: ReturnType<typeof setInterval> | null = null
  let timerInterval: ReturnType<typeof setInterval> | null = null
  let cancelled = false
  let isUnmounted = false

  function stopAll(): void {
    if (pollTimer) {
      clearInterval(pollTimer)
      pollTimer = null
    }
    if (timerInterval) {
      clearInterval(timerInterval)
      timerInterval = null
    }
  }

  function resetExport(): void {
    stopAll()
    cancelled = false
    exportStatus.value = 'idle'
    exportStatusMessage.value = ''
    exportUrl.value = null
    exportingFormId.value = null
    exportElapsed.value = 0
  }

  function cancelExport(): void {
    cancelled = true
    stopAll()
    exportStatus.value = 'idle'
    exportStatusMessage.value = ''
    exportingFormId.value = null
  }

  function pollTaskStatus(taskId: string, messages: ExportMessages): void {
    let attempts = 0
    pollTimer = setInterval(async () => {
      if (isUnmounted || cancelled) {
        stopAll()
        return
      }
      attempts++
      if (attempts > maxAttempts) {
        stopAll()
        exportStatus.value = 'error'
        exportStatusMessage.value = ''
        exportingFormId.value = null
        if (options.onTimeout) {
          options.onTimeout()
        } else {
          options.onError?.(messages.timeout)
        }
        return
      }
      try {
        const data = await getTaskStatus(taskId)
        const msg = `${messages.statusPrefix} ${data.status}`
        exportStatusMessage.value = msg
        options.onStatusMessage?.(msg)
        if (data.status === 'SUCCESS' && data.download_url) {
          stopAll()
          exportStatus.value = 'done'
          exportUrl.value = data.download_url
          exportStatusMessage.value = ''
          exportingFormId.value = null
          options.onSuccess?.(data.download_url)
          if (isAllowedDownloadUrl(data.download_url)) {
            window.open(data.download_url, '_blank')
          } else {
            exportStatus.value = 'error'
            options.onError?.('Invalid download URL origin')
          }
        } else if (data.status === 'FAILURE') {
          stopAll()
          exportStatus.value = 'error'
          exportStatusMessage.value = ''
          exportingFormId.value = null
          options.onError?.(messages.failed)
        }
      } catch {
        /* continue polling */
      }
    }, pollInterval)
  }

  async function startExport(formId: string, messages: ExportMessages): Promise<void> {
    resetExport()
    cancelled = false
    exportingFormId.value = formId
    exportStatus.value = 'pending'
    exportStatusMessage.value = messages.starting
    exportElapsed.value = 0
    options.onStatusMessage?.(messages.starting)

    if (timerInterval) clearInterval(timerInterval)
    timerInterval = setInterval(() => {
      exportElapsed.value++
    }, 1000)

    try {
      const data = await exportForm(formId)
      pollTaskStatus(data.task_id, messages)
    } catch (e: unknown) {
      stopAll()
      exportingFormId.value = null
      exportStatus.value = 'error'
      exportStatusMessage.value = ''
      options.onError?.(getErrorMessage(e, messages.error))
    }
  }

  onUnmounted(() => {
    isUnmounted = true
    stopAll()
  })

  return {
    exportStatus,
    exportStatusMessage,
    exportUrl,
    exportingFormId,
    exportElapsed,
    startExport,
    cancelExport,
    resetExport,
  }
}

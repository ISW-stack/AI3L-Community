import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

// Capture lifecycle callbacks
const onUnmountedCallbacks: (() => void)[] = []
vi.mock('vue', async () => {
  const actual = await vi.importActual<typeof import('vue')>('vue')
  return {
    ...actual,
    onUnmounted: vi.fn((cb: () => void) => {
      onUnmountedCallbacks.push(cb)
    }),
  }
})

// Mock API modules
vi.mock('@/api/forms', () => ({
  exportForm: vi.fn(),
}))

vi.mock('@/api/tasks', () => ({
  getTaskStatus: vi.fn(),
}))

import { useFormExport, type ExportMessages } from '../useFormExport'
import { exportForm } from '@/api/forms'
import { getTaskStatus } from '@/api/tasks'

const mockExportForm = exportForm as ReturnType<typeof vi.fn>
const mockGetTaskStatus = getTaskStatus as ReturnType<typeof vi.fn>

const messages: ExportMessages = {
  starting: 'Starting export...',
  statusPrefix: 'Export status:',
  timeout: 'Export timed out',
  failed: 'Export failed',
  error: 'Export error',
}

describe('useFormExport', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.useFakeTimers()
    onUnmountedCallbacks.length = 0
    // Mock window.open
    vi.spyOn(window, 'open').mockImplementation(() => null)
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.restoreAllMocks()
  })

  // 1. Starting export - calls API correctly
  describe('startExport', () => {
    it('calls exportForm API and sets pending status', async () => {
      mockExportForm.mockResolvedValue({ task_id: 'task-1' })

      const { startExport, exportStatus, exportingFormId } = useFormExport()
      await startExport('form-1', messages)

      expect(mockExportForm).toHaveBeenCalledWith('form-1')
      expect(exportStatus.value).toBe('pending')
      expect(exportingFormId.value).toBe('form-1')
    })

    it('sets starting status message', async () => {
      mockExportForm.mockResolvedValue({ task_id: 'task-1' })
      const onStatusMessage = vi.fn()

      const { startExport } = useFormExport({ onStatusMessage })
      await startExport('form-1', messages)

      expect(onStatusMessage).toHaveBeenCalledWith('Starting export...')
    })

    it('starts elapsed time counter', async () => {
      mockExportForm.mockResolvedValue({ task_id: 'task-1' })

      const { startExport, exportElapsed } = useFormExport()
      await startExport('form-1', messages)

      expect(exportElapsed.value).toBe(0)
      vi.advanceTimersByTime(3000)
      expect(exportElapsed.value).toBe(3)
    })
  })

  // 2. Polling for export status - pending state
  describe('polling - pending', () => {
    it('continues polling when status is PENDING', async () => {
      mockExportForm.mockResolvedValue({ task_id: 'task-1' })
      mockGetTaskStatus.mockResolvedValue({ status: 'PENDING' })
      const onStatusMessage = vi.fn()

      const { startExport, exportStatus } = useFormExport({
        onStatusMessage,
        pollInterval: 1000,
      })
      await startExport('form-1', messages)

      // First poll
      await vi.advanceTimersByTimeAsync(1000)
      expect(mockGetTaskStatus).toHaveBeenCalledWith('task-1')
      expect(exportStatus.value).toBe('pending')
      expect(onStatusMessage).toHaveBeenCalledWith('Export status: PENDING')

      // Second poll
      await vi.advanceTimersByTimeAsync(1000)
      expect(mockGetTaskStatus).toHaveBeenCalledTimes(2)
    })
  })

  // 3. Polling for export status - completed state opens download URL
  describe('polling - success', () => {
    it('opens download URL on SUCCESS', async () => {
      mockExportForm.mockResolvedValue({ task_id: 'task-1' })
      mockGetTaskStatus.mockResolvedValue({
        status: 'SUCCESS',
        download_url: 'http://localhost:19000/bucket/export.csv',
      })
      const onSuccess = vi.fn()

      const { startExport, exportStatus, exportUrl } = useFormExport({
        onSuccess,
        pollInterval: 1000,
      })
      await startExport('form-1', messages)
      await vi.advanceTimersByTimeAsync(1000)

      expect(exportStatus.value).toBe('done')
      expect(exportUrl.value).toBe('http://localhost:19000/bucket/export.csv')
      expect(onSuccess).toHaveBeenCalledWith('http://localhost:19000/bucket/export.csv')
      expect(window.open).toHaveBeenCalledWith('http://localhost:19000/bucket/export.csv', '_blank')
    })

    it('clears exportingFormId on success', async () => {
      mockExportForm.mockResolvedValue({ task_id: 'task-1' })
      mockGetTaskStatus.mockResolvedValue({
        status: 'SUCCESS',
        download_url: 'http://localhost:19000/bucket/export.csv',
      })

      const { startExport, exportingFormId } = useFormExport({ pollInterval: 1000 })
      await startExport('form-1', messages)
      expect(exportingFormId.value).toBe('form-1')

      await vi.advanceTimersByTimeAsync(1000)
      expect(exportingFormId.value).toBeNull()
    })

    it('stops polling after SUCCESS', async () => {
      mockExportForm.mockResolvedValue({ task_id: 'task-1' })
      mockGetTaskStatus.mockResolvedValue({
        status: 'SUCCESS',
        download_url: 'http://localhost:19000/bucket/export.csv',
      })

      const { startExport } = useFormExport({ pollInterval: 1000 })
      await startExport('form-1', messages)
      await vi.advanceTimersByTimeAsync(1000)

      mockGetTaskStatus.mockClear()
      await vi.advanceTimersByTimeAsync(5000)
      expect(mockGetTaskStatus).not.toHaveBeenCalled()
    })
  })

  // 4. Polling for export status - failed state shows error
  describe('polling - failure', () => {
    it('sets error status on FAILURE', async () => {
      mockExportForm.mockResolvedValue({ task_id: 'task-1' })
      mockGetTaskStatus.mockResolvedValue({ status: 'FAILURE' })
      const onError = vi.fn()

      const { startExport, exportStatus } = useFormExport({ onError, pollInterval: 1000 })
      await startExport('form-1', messages)
      await vi.advanceTimersByTimeAsync(1000)

      expect(exportStatus.value).toBe('error')
      expect(onError).toHaveBeenCalledWith('Export failed')
    })

    it('clears exportingFormId on failure', async () => {
      mockExportForm.mockResolvedValue({ task_id: 'task-1' })
      mockGetTaskStatus.mockResolvedValue({ status: 'FAILURE' })

      const { startExport, exportingFormId } = useFormExport({ pollInterval: 1000 })
      await startExport('form-1', messages)
      await vi.advanceTimersByTimeAsync(1000)

      expect(exportingFormId.value).toBeNull()
    })

    it('stops polling after FAILURE', async () => {
      mockExportForm.mockResolvedValue({ task_id: 'task-1' })
      mockGetTaskStatus.mockResolvedValue({ status: 'FAILURE' })

      const { startExport } = useFormExport({ pollInterval: 1000 })
      await startExport('form-1', messages)
      await vi.advanceTimersByTimeAsync(1000)

      mockGetTaskStatus.mockClear()
      await vi.advanceTimersByTimeAsync(5000)
      expect(mockGetTaskStatus).not.toHaveBeenCalled()
    })
  })

  // 5. Polling timeout - shows appropriate error after max retries
  describe('polling - timeout', () => {
    it('times out after maxAttempts', async () => {
      mockExportForm.mockResolvedValue({ task_id: 'task-1' })
      mockGetTaskStatus.mockResolvedValue({ status: 'PENDING' })
      const onTimeout = vi.fn()

      const { startExport, exportStatus } = useFormExport({
        onTimeout,
        maxAttempts: 3,
        pollInterval: 1000,
      })
      await startExport('form-1', messages)

      // Advance through 4 poll intervals (attempts 1, 2, 3, then 4 > maxAttempts)
      for (let i = 0; i < 4; i++) {
        await vi.advanceTimersByTimeAsync(1000)
      }

      expect(exportStatus.value).toBe('error')
      expect(onTimeout).toHaveBeenCalled()
    })

    it('calls onError with timeout message when no onTimeout callback', async () => {
      mockExportForm.mockResolvedValue({ task_id: 'task-1' })
      mockGetTaskStatus.mockResolvedValue({ status: 'PENDING' })
      const onError = vi.fn()

      const { startExport } = useFormExport({ onError, maxAttempts: 2, pollInterval: 1000 })
      await startExport('form-1', messages)

      for (let i = 0; i < 3; i++) {
        await vi.advanceTimersByTimeAsync(1000)
      }

      expect(onError).toHaveBeenCalledWith('Export timed out')
    })

    it('stops polling after timeout', async () => {
      mockExportForm.mockResolvedValue({ task_id: 'task-1' })
      mockGetTaskStatus.mockResolvedValue({ status: 'PENDING' })

      const { startExport } = useFormExport({ maxAttempts: 2, pollInterval: 1000 })
      await startExport('form-1', messages)

      // Advance past timeout
      for (let i = 0; i < 3; i++) {
        await vi.advanceTimersByTimeAsync(1000)
      }

      mockGetTaskStatus.mockClear()
      await vi.advanceTimersByTimeAsync(5000)
      expect(mockGetTaskStatus).not.toHaveBeenCalled()
    })
  })

  // 6. Export error - API call fails
  describe('startExport error', () => {
    it('sets error status when exportForm API fails', async () => {
      mockExportForm.mockRejectedValue({
        response: { data: { detail: 'No responses to export' } },
      })
      const onError = vi.fn()

      const { startExport, exportStatus, exportingFormId } = useFormExport({ onError })
      await startExport('form-1', messages)

      expect(exportStatus.value).toBe('error')
      expect(exportingFormId.value).toBeNull()
      expect(onError).toHaveBeenCalledWith('No responses to export')
    })

    it('uses fallback message when error has no detail', async () => {
      mockExportForm.mockRejectedValue(new Error('Network error'))
      const onError = vi.fn()

      const { startExport } = useFormExport({ onError })
      await startExport('form-1', messages)

      expect(onError).toHaveBeenCalledWith('Export error')
    })
  })

  // 7. Concurrent export prevention
  describe('concurrent export prevention', () => {
    it('resetExport called by startExport clears previous state', async () => {
      mockExportForm.mockResolvedValue({ task_id: 'task-1' })

      const { startExport, exportStatus, exportUrl } = useFormExport({ pollInterval: 1000 })

      // First export that completes
      mockGetTaskStatus.mockResolvedValue({
        status: 'SUCCESS',
        download_url: 'http://localhost:19000/bucket/first.csv',
      })
      await startExport('form-1', messages)
      await vi.advanceTimersByTimeAsync(1000)
      expect(exportStatus.value).toBe('done')
      expect(exportUrl.value).toBe('http://localhost:19000/bucket/first.csv')

      // Starting a new export resets state
      mockExportForm.mockResolvedValue({ task_id: 'task-2' })
      mockGetTaskStatus.mockResolvedValue({ status: 'PENDING' })
      await startExport('form-2', messages)
      expect(exportStatus.value).toBe('pending')
      expect(exportUrl.value).toBeNull()
    })
  })

  // cancelExport
  describe('cancelExport', () => {
    it('cancels an in-progress export', async () => {
      mockExportForm.mockResolvedValue({ task_id: 'task-1' })
      mockGetTaskStatus.mockResolvedValue({ status: 'PENDING' })

      const { startExport, cancelExport, exportStatus, exportingFormId } = useFormExport({
        pollInterval: 1000,
      })
      await startExport('form-1', messages)
      expect(exportStatus.value).toBe('pending')

      cancelExport()
      expect(exportStatus.value).toBe('idle')
      expect(exportingFormId.value).toBeNull()

      // Verify polling has stopped
      mockGetTaskStatus.mockClear()
      await vi.advanceTimersByTimeAsync(5000)
      expect(mockGetTaskStatus).not.toHaveBeenCalled()
    })
  })

  // resetExport
  describe('resetExport', () => {
    it('resets all state to initial values', async () => {
      mockExportForm.mockResolvedValue({ task_id: 'task-1' })
      mockGetTaskStatus.mockResolvedValue({
        status: 'SUCCESS',
        download_url: 'http://localhost:19000/bucket/export.csv',
      })

      const { startExport, resetExport, exportStatus, exportUrl, exportingFormId, exportElapsed } =
        useFormExport({ pollInterval: 1000 })
      await startExport('form-1', messages)
      await vi.advanceTimersByTimeAsync(1000)

      expect(exportStatus.value).toBe('done')

      resetExport()
      expect(exportStatus.value).toBe('idle')
      expect(exportUrl.value).toBeNull()
      expect(exportingFormId.value).toBeNull()
      expect(exportElapsed.value).toBe(0)
    })
  })

  // Polling continues even when getTaskStatus throws (network glitch)
  describe('polling resilience', () => {
    it('continues polling when getTaskStatus throws', async () => {
      mockExportForm.mockResolvedValue({ task_id: 'task-1' })
      mockGetTaskStatus.mockRejectedValueOnce(new Error('Network error')).mockResolvedValueOnce({
        status: 'SUCCESS',
        download_url: 'http://localhost:19000/bucket/export.csv',
      })

      const { startExport, exportStatus } = useFormExport({ pollInterval: 1000 })
      await startExport('form-1', messages)

      // First poll - error, but should continue
      await vi.advanceTimersByTimeAsync(1000)
      expect(exportStatus.value).toBe('pending')

      // Second poll - success
      await vi.advanceTimersByTimeAsync(1000)
      expect(exportStatus.value).toBe('done')
    })
  })

  // Initial state
  describe('initial state', () => {
    it('has idle status by default', () => {
      const { exportStatus, exportStatusMessage, exportUrl, exportingFormId, exportElapsed } =
        useFormExport()
      expect(exportStatus.value).toBe('idle')
      expect(exportStatusMessage.value).toBe('')
      expect(exportUrl.value).toBeNull()
      expect(exportingFormId.value).toBeNull()
      expect(exportElapsed.value).toBe(0)
    })
  })

  // Cleanup on unmount
  describe('cleanup', () => {
    it('stops all timers on unmount', async () => {
      mockExportForm.mockResolvedValue({ task_id: 'task-1' })
      mockGetTaskStatus.mockResolvedValue({ status: 'PENDING' })

      const { startExport } = useFormExport({ pollInterval: 1000 })
      await startExport('form-1', messages)

      // Trigger onUnmounted
      for (const cb of onUnmountedCallbacks) cb()

      mockGetTaskStatus.mockClear()
      await vi.advanceTimersByTimeAsync(5000)
      expect(mockGetTaskStatus).not.toHaveBeenCalled()
    })
  })
})

import { describe, it, expect, vi, beforeEach } from 'vitest'

const mockGet = vi.fn()
const mockPost = vi.fn()

vi.mock('@/composables/api', () => ({
  default: {
    get: (...args: unknown[]) => mockGet(...args),
    post: (...args: unknown[]) => mockPost(...args),
  },
}))

import {
  getTaskStatus,
  uploadEditorFile,
  getFileScanStatus,
  getPresignedUrl,
  getStorageUsage,
} from '../files'

describe('files API', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('getTaskStatus', () => {
    it('calls GET /tasks/:taskId/status and returns task status response', async () => {
      const mockData = {
        task_id: 'task-1',
        status: 'completed',
        result: { status: 'clean', malicious: 0, suspicious: 0 },
      }
      mockGet.mockResolvedValue({ data: mockData })

      const result = await getTaskStatus('task-1')

      expect(mockGet).toHaveBeenCalledWith('/tasks/task-1/status')
      expect(result).toEqual(mockData)
    })

    it('includes the task id in the URL path', async () => {
      mockGet.mockResolvedValue({ data: { task_id: 'abc', status: 'pending', result: null } })

      await getTaskStatus('abc')

      expect(mockGet).toHaveBeenCalledWith('/tasks/abc/status')
    })

    it('returns result as null when pending', async () => {
      const mockData = { task_id: 't1', status: 'pending', result: null }
      mockGet.mockResolvedValue({ data: mockData })

      const result = await getTaskStatus('t1')

      expect(result.result).toBeNull()
    })

    it('returns result with malicious count when scan finds threats', async () => {
      const mockData = {
        task_id: 't2',
        status: 'completed',
        result: { status: 'malicious', malicious: 3, suspicious: 1 },
      }
      mockGet.mockResolvedValue({ data: mockData })

      const result = await getTaskStatus('t2')

      expect(result.result?.malicious).toBe(3)
      expect(result.result?.suspicious).toBe(1)
    })

    it('propagates API errors', async () => {
      mockGet.mockRejectedValue(new Error('Not found'))

      await expect(getTaskStatus('bad')).rejects.toThrow('Not found')
    })
  })

  describe('uploadEditorFile', () => {
    it('calls POST /files/upload/editor with FormData and multipart header', async () => {
      const file = new File(['content'], 'test.txt', { type: 'text/plain' })
      const mockData = { url: 'https://cdn.example.com/test.txt', key: 'uploads/test.txt' }
      mockPost.mockResolvedValue({ data: mockData })

      const result = await uploadEditorFile(file)

      expect(mockPost).toHaveBeenCalledTimes(1)
      const [url, formData, config] = mockPost.mock.calls[0]
      expect(url).toBe('/files/upload/editor')
      expect(formData).toBeInstanceOf(FormData)
      expect(formData.get('file')).toBe(file)
      expect(config).toEqual({ headers: { 'Content-Type': 'multipart/form-data' } })
      expect(result).toEqual(mockData)
    })

    it('returns upload response with scan_task_id', async () => {
      const file = new File(['data'], 'doc.pdf', { type: 'application/pdf' })
      const mockData = {
        url: 'https://cdn.example.com/doc.pdf',
        key: 'uploads/doc.pdf',
        scan_task_id: 'scan-123',
      }
      mockPost.mockResolvedValue({ data: mockData })

      const result = await uploadEditorFile(file)

      expect(result.url).toBe('https://cdn.example.com/doc.pdf')
      expect(result.key).toBe('uploads/doc.pdf')
      expect(result.scan_task_id).toBe('scan-123')
    })

    it('returns upload response with null scan_task_id', async () => {
      const file = new File(['img'], 'photo.png', { type: 'image/png' })
      const mockData = { url: 'https://cdn.example.com/photo.png', scan_task_id: null }
      mockPost.mockResolvedValue({ data: mockData })

      const result = await uploadEditorFile(file)

      expect(result.scan_task_id).toBeNull()
    })

    it('propagates API errors', async () => {
      const file = new File(['x'], 'fail.txt')
      mockPost.mockRejectedValue(new Error('Upload failed'))

      await expect(uploadEditorFile(file)).rejects.toThrow('Upload failed')
    })
  })

  describe('getFileScanStatus', () => {
    it('calls GET /files/scan-status/:fileKey and returns scan status', async () => {
      const mockData = { status: 'clean', positives: 0, total: 72 }
      mockGet.mockResolvedValue({ data: mockData })

      const result = await getFileScanStatus('uploads/test.txt')

      expect(mockGet).toHaveBeenCalledWith('/files/scan-status/uploads/test.txt')
      expect(result).toEqual(mockData)
    })

    it('returns pending status', async () => {
      const mockData = { status: 'pending', positives: null, total: null }
      mockGet.mockResolvedValue({ data: mockData })

      const result = await getFileScanStatus('key123')

      expect(result.status).toBe('pending')
      expect(result.positives).toBeNull()
      expect(result.total).toBeNull()
    })

    it('returns malicious status with positives count', async () => {
      const mockData = { status: 'malicious', positives: 5, total: 70 }
      mockGet.mockResolvedValue({ data: mockData })

      const result = await getFileScanStatus('bad-file')

      expect(result.status).toBe('malicious')
      expect(result.positives).toBe(5)
    })

    it('propagates API errors', async () => {
      mockGet.mockRejectedValue(new Error('Not found'))

      await expect(getFileScanStatus('missing')).rejects.toThrow('Not found')
    })
  })

  describe('getPresignedUrl', () => {
    it('calls GET /files/presigned-url with key param and returns url', async () => {
      const mockData = { url: 'https://minio.example.com/signed-url?token=abc' }
      mockGet.mockResolvedValue({ data: mockData })

      const result = await getPresignedUrl('uploads/file.pdf')

      expect(mockGet).toHaveBeenCalledWith('/files/presigned-url', {
        params: { key: 'uploads/file.pdf' },
      })
      expect(result).toEqual(mockData)
    })

    it('passes the key as a query parameter', async () => {
      mockGet.mockResolvedValue({ data: { url: 'https://example.com/url' } })

      await getPresignedUrl('my/file/key.txt')

      expect(mockGet).toHaveBeenCalledWith('/files/presigned-url', {
        params: { key: 'my/file/key.txt' },
      })
    })

    it('returns object with url string', async () => {
      const expectedUrl = 'https://storage.example.com/presigned?sig=xyz'
      mockGet.mockResolvedValue({ data: { url: expectedUrl } })

      const result = await getPresignedUrl('key')

      expect(result.url).toBe(expectedUrl)
    })

    it('calls GET exactly once', async () => {
      mockGet.mockResolvedValue({ data: { url: 'u' } })

      await getPresignedUrl('k')

      expect(mockGet).toHaveBeenCalledTimes(1)
    })

    it('propagates API errors', async () => {
      mockGet.mockRejectedValue(new Error('Forbidden'))

      await expect(getPresignedUrl('private-key')).rejects.toThrow('Forbidden')
    })
  })

  describe('getStorageUsage', () => {
    it('calls GET /files/storage-usage and returns usage data', async () => {
      const mockData = { used_bytes: 500_000_000, quota_bytes: 1_073_741_824 }
      mockGet.mockResolvedValue({ data: mockData })

      const result = await getStorageUsage()

      expect(mockGet).toHaveBeenCalledWith('/files/storage-usage')
      expect(result).toEqual(mockData)
    })

    it('returns used_bytes and quota_bytes from response', async () => {
      const mockData = { used_bytes: 102_400, quota_bytes: 10_737_418_240 }
      mockGet.mockResolvedValue({ data: mockData })

      const result = await getStorageUsage()

      expect(result.used_bytes).toBe(102_400)
      expect(result.quota_bytes).toBe(10_737_418_240)
    })

    it('returns zero used_bytes when storage is empty', async () => {
      const mockData = { used_bytes: 0, quota_bytes: 1_073_741_824 }
      mockGet.mockResolvedValue({ data: mockData })

      const result = await getStorageUsage()

      expect(result.used_bytes).toBe(0)
    })

    it('calls GET exactly once', async () => {
      mockGet.mockResolvedValue({ data: { used_bytes: 0, quota_bytes: 1_073_741_824 } })

      await getStorageUsage()

      expect(mockGet).toHaveBeenCalledTimes(1)
    })

    it('propagates API errors', async () => {
      mockGet.mockRejectedValue(new Error('Unauthorized'))

      await expect(getStorageUsage()).rejects.toThrow('Unauthorized')
    })
  })
})

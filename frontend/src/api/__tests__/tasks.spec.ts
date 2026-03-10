import { describe, it, expect, vi, beforeEach } from 'vitest'

const mockGet = vi.fn()
const mockPost = vi.fn()

vi.mock('@/composables/api', () => ({
  default: {
    get: (...args: unknown[]) => mockGet(...args),
    post: (...args: unknown[]) => mockPost(...args),
  },
}))

import { getTaskStatus } from '../tasks'

describe('tasks API', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('getTaskStatus', () => {
    it('calls GET /tasks/:taskId/status and returns task status', async () => {
      const mockData = { status: 'completed', download_url: 'https://example.com/file.zip' }
      mockGet.mockResolvedValue({ data: mockData })

      const result = await getTaskStatus('task-1')

      expect(mockGet).toHaveBeenCalledWith('/tasks/task-1/status')
      expect(result).toEqual(mockData)
    })

    it('includes the task id in the URL path', async () => {
      const taskId = 'abc-def-123'
      mockGet.mockResolvedValue({ data: { status: 'pending' } })

      await getTaskStatus(taskId)

      expect(mockGet).toHaveBeenCalledWith(`/tasks/${taskId}/status`)
    })

    it('returns status without download_url when pending', async () => {
      const mockData = { status: 'pending' }
      mockGet.mockResolvedValue({ data: mockData })

      const result = await getTaskStatus('t1')

      expect(result.status).toBe('pending')
      expect(result.download_url).toBeUndefined()
    })

    it('returns status with download_url when completed', async () => {
      const mockData = { status: 'completed', download_url: '/downloads/report.csv' }
      mockGet.mockResolvedValue({ data: mockData })

      const result = await getTaskStatus('t2')

      expect(result.status).toBe('completed')
      expect(result.download_url).toBe('/downloads/report.csv')
    })

    it('calls GET exactly once', async () => {
      mockGet.mockResolvedValue({ data: { status: 'running' } })

      await getTaskStatus('t1')

      expect(mockGet).toHaveBeenCalledTimes(1)
    })

    it('does not use POST', async () => {
      mockGet.mockResolvedValue({ data: { status: 'done' } })

      await getTaskStatus('t1')

      expect(mockPost).not.toHaveBeenCalled()
    })

    it('propagates API errors', async () => {
      mockGet.mockRejectedValue(new Error('Not found'))

      await expect(getTaskStatus('bad-id')).rejects.toThrow('Not found')
    })
  })
})

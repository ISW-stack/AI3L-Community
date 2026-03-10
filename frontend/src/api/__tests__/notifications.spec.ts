import { describe, it, expect, vi, beforeEach } from 'vitest'

const mockGet = vi.fn()
const mockPost = vi.fn()
const mockPut = vi.fn()
const mockDelete = vi.fn()

vi.mock('@/composables/api', () => ({
  default: {
    get: (...args: unknown[]) => mockGet(...args),
    post: (...args: unknown[]) => mockPost(...args),
    put: (...args: unknown[]) => mockPut(...args),
    delete: (...args: unknown[]) => mockDelete(...args),
  },
}))

import {
  listNotifications,
  markRead,
  markAllRead,
  deleteNotification,
  bulkDeleteNotifications,
} from '../notifications'

describe('notifications API', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('listNotifications', () => {
    it('calls GET /notifications with params and returns response', async () => {
      const params = { page: 1, page_size: 10, unread: true }
      const mockData = {
        notifications: [{ id: 'n1', message: 'Hello' }],
        total: 1,
        unread_count: 1,
      }
      mockGet.mockResolvedValue({ data: mockData })

      const result = await listNotifications(params)

      expect(mockGet).toHaveBeenCalledWith('/notifications', { params })
      expect(result).toEqual(mockData)
    })

    it('passes empty params object', async () => {
      mockGet.mockResolvedValue({ data: { notifications: [], total: 0, unread_count: 0 } })

      await listNotifications({})

      expect(mockGet).toHaveBeenCalledWith('/notifications', { params: {} })
    })

    it('passes partial params', async () => {
      mockGet.mockResolvedValue({ data: { notifications: [], total: 0, unread_count: 0 } })

      await listNotifications({ page: 2 })

      expect(mockGet).toHaveBeenCalledWith('/notifications', { params: { page: 2 } })
    })

    it('returns notifications list with total and unread_count', async () => {
      const mockData = {
        notifications: [
          { id: 'n1', message: 'A' },
          { id: 'n2', message: 'B' },
        ],
        total: 5,
        unread_count: 3,
      }
      mockGet.mockResolvedValue({ data: mockData })

      const result = await listNotifications({ page: 1, page_size: 2 })

      expect(result.notifications).toHaveLength(2)
      expect(result.total).toBe(5)
      expect(result.unread_count).toBe(3)
    })

    it('propagates API errors', async () => {
      mockGet.mockRejectedValue(new Error('Server error'))

      await expect(listNotifications({})).rejects.toThrow('Server error')
    })
  })

  describe('markRead', () => {
    it('calls PUT /notifications/:id/read', async () => {
      mockPut.mockResolvedValue({})

      await markRead('notif-1')

      expect(mockPut).toHaveBeenCalledWith('/notifications/notif-1/read')
    })

    it('includes the notification id in the URL', async () => {
      const id = 'abc-456'
      mockPut.mockResolvedValue({})

      await markRead(id)

      expect(mockPut).toHaveBeenCalledWith(`/notifications/${id}/read`)
    })

    it('calls PUT exactly once', async () => {
      mockPut.mockResolvedValue({})

      await markRead('n1')

      expect(mockPut).toHaveBeenCalledTimes(1)
    })

    it('propagates API errors', async () => {
      mockPut.mockRejectedValue(new Error('Not found'))

      await expect(markRead('bad-id')).rejects.toThrow('Not found')
    })
  })

  describe('markAllRead', () => {
    it('calls PUT /notifications/read-all', async () => {
      mockPut.mockResolvedValue({})

      await markAllRead()

      expect(mockPut).toHaveBeenCalledWith('/notifications/read-all')
    })

    it('calls PUT exactly once', async () => {
      mockPut.mockResolvedValue({})

      await markAllRead()

      expect(mockPut).toHaveBeenCalledTimes(1)
    })

    it('does not use GET or POST', async () => {
      mockPut.mockResolvedValue({})

      await markAllRead()

      expect(mockGet).not.toHaveBeenCalled()
      expect(mockPost).not.toHaveBeenCalled()
    })

    it('propagates API errors', async () => {
      mockPut.mockRejectedValue(new Error('Unauthorized'))

      await expect(markAllRead()).rejects.toThrow('Unauthorized')
    })
  })

  describe('deleteNotification', () => {
    it('calls DELETE /notifications/:id', async () => {
      mockDelete.mockResolvedValue({})

      await deleteNotification('notif-1')

      expect(mockDelete).toHaveBeenCalledWith('/notifications/notif-1')
    })

    it('includes the notification id in the URL', async () => {
      const id = 'del-789'
      mockDelete.mockResolvedValue({})

      await deleteNotification(id)

      expect(mockDelete).toHaveBeenCalledWith(`/notifications/${id}`)
    })

    it('propagates API errors', async () => {
      mockDelete.mockRejectedValue(new Error('Forbidden'))

      await expect(deleteNotification('x')).rejects.toThrow('Forbidden')
    })
  })

  describe('bulkDeleteNotifications', () => {
    it('calls DELETE /notifications with notification_ids in data', async () => {
      const ids = ['n1', 'n2', 'n3']
      mockDelete.mockResolvedValue({})

      await bulkDeleteNotifications(ids)

      expect(mockDelete).toHaveBeenCalledWith('/notifications', {
        data: { notification_ids: ids },
      })
    })

    it('calls DELETE /notifications with undefined data when no ids provided', async () => {
      mockDelete.mockResolvedValue({})

      await bulkDeleteNotifications(undefined)

      expect(mockDelete).toHaveBeenCalledWith('/notifications', {
        data: undefined,
      })
    })

    it('calls DELETE /notifications with undefined data when called without arguments', async () => {
      mockDelete.mockResolvedValue({})

      await bulkDeleteNotifications()

      expect(mockDelete).toHaveBeenCalledWith('/notifications', {
        data: undefined,
      })
    })

    it('calls DELETE exactly once', async () => {
      mockDelete.mockResolvedValue({})

      await bulkDeleteNotifications(['n1'])

      expect(mockDelete).toHaveBeenCalledTimes(1)
    })

    it('propagates API errors', async () => {
      mockDelete.mockRejectedValue(new Error('Server error'))

      await expect(bulkDeleteNotifications(['n1'])).rejects.toThrow('Server error')
    })
  })
})

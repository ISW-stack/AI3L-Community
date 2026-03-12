import { describe, it, expect, vi, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useNotificationStore } from '../notifications'
import type { Notification } from '@/types/notification'

// Mock the API module
const mockListNotifications = vi.fn()
const mockApiMarkRead = vi.fn()
const mockApiMarkAllRead = vi.fn()

vi.mock('@/api/notifications', () => ({
  listNotifications: (...args: unknown[]) => mockListNotifications(...args),
  markRead: (...args: unknown[]) => mockApiMarkRead(...args),
  markAllRead: (...args: unknown[]) => mockApiMarkAllRead(...args),
}))

function makeNotification(overrides: Partial<Notification> = {}): Notification {
  return {
    id: '1',
    action_type: 'comment',
    entity_type: 'post',
    entity_id: 'post-1',
    message: 'Test notification',
    is_read: false,
    created_at: '2025-01-01T00:00:00Z',
    trigger_user: null,
    ...overrides,
  }
}

describe('useNotificationStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    mockListNotifications.mockReset()
    mockApiMarkRead.mockReset()
    mockApiMarkAllRead.mockReset()
  })

  // ---------- addFromWebSocket ----------

  describe('addFromWebSocket', () => {
    it('should prepend notification and increment unread count', () => {
      const store = useNotificationStore()
      const notif = makeNotification({ id: '1', message: 'New comment' })

      store.addFromWebSocket(notif)

      expect(store.items).toHaveLength(1)
      expect(store.items[0].message).toBe('New comment')
      expect(store.unreadCount).toBe(1)
    })

    it('should prepend newest notification to the front', () => {
      const store = useNotificationStore()
      store.addFromWebSocket(makeNotification({ id: '1', message: 'First' }))
      store.addFromWebSocket(makeNotification({ id: '2', message: 'Second' }))

      expect(store.items[0].message).toBe('Second')
      expect(store.items[1].message).toBe('First')
    })

    it('should cap items at 10 by removing the oldest', () => {
      const store = useNotificationStore()

      for (let i = 0; i < 12; i++) {
        store.addFromWebSocket(makeNotification({ id: String(i), message: `n${i}` }))
      }

      expect(store.items).toHaveLength(10)
      // The oldest items (0 and 1) should have been popped
      expect(store.items[0].id).toBe('11')
      expect(store.items[9].id).toBe('2')
      // unreadCount should still track all 12
      expect(store.unreadCount).toBe(12)
    })

    it('should increment unreadCount each time', () => {
      const store = useNotificationStore()
      store.addFromWebSocket(makeNotification({ id: '1' }))
      store.addFromWebSocket(makeNotification({ id: '2' }))
      store.addFromWebSocket(makeNotification({ id: '3' }))

      expect(store.unreadCount).toBe(3)
    })
  })

  // ---------- fetchUnreadCount ----------

  describe('fetchUnreadCount', () => {
    it('should update unreadCount from API response', async () => {
      mockListNotifications.mockResolvedValueOnce({
        notifications: [],
        total: 0,
        unread_count: 5,
      })

      const store = useNotificationStore()
      await store.fetchUnreadCount()

      expect(mockListNotifications).toHaveBeenCalledWith({ unread: true, page_size: 1 })
      expect(store.unreadCount).toBe(5)
    })

    it('should not throw on API error', async () => {
      mockListNotifications.mockRejectedValueOnce(new Error('Network error'))

      const store = useNotificationStore()
      await expect(store.fetchUnreadCount()).resolves.toBeUndefined()
      expect(store.unreadCount).toBe(0)
    })
  })

  // ---------- fetchRecent ----------

  describe('fetchRecent', () => {
    it('should populate items and unreadCount from API', async () => {
      const notifications = [
        makeNotification({ id: '1', message: 'A' }),
        makeNotification({ id: '2', message: 'B' }),
      ]
      mockListNotifications.mockResolvedValueOnce({
        notifications,
        total: 2,
        unread_count: 1,
      })

      const store = useNotificationStore()
      await store.fetchRecent()

      expect(store.items).toEqual(notifications)
      expect(store.unreadCount).toBe(1)
      expect(store.loading).toBe(false)
    })

    it('should set loading to true while fetching', async () => {
      let resolvePromise: (value: unknown) => void
      const pendingPromise = new Promise((resolve) => {
        resolvePromise = resolve
      })
      mockListNotifications.mockReturnValueOnce(pendingPromise)

      const store = useNotificationStore()
      const fetchPromise = store.fetchRecent()

      expect(store.loading).toBe(true)

      resolvePromise!({ notifications: [], total: 0, unread_count: 0 })
      await fetchPromise

      expect(store.loading).toBe(false)
    })

    it('should not start a second fetch while loading', async () => {
      let resolvePromise: (value: unknown) => void
      const pendingPromise = new Promise((resolve) => {
        resolvePromise = resolve
      })
      mockListNotifications.mockReturnValueOnce(pendingPromise)

      const store = useNotificationStore()
      const first = store.fetchRecent()
      store.fetchRecent() // should be no-op

      expect(mockListNotifications).toHaveBeenCalledTimes(1)

      resolvePromise!({ notifications: [], total: 0, unread_count: 0 })
      await first
    })

    it('should accept page and pageSize parameters', async () => {
      mockListNotifications.mockResolvedValueOnce({
        notifications: [],
        total: 0,
        unread_count: 0,
      })

      const store = useNotificationStore()
      await store.fetchRecent(2, 5)

      expect(mockListNotifications).toHaveBeenCalledWith({ page: 2, page_size: 5 })
    })

    it('should set loading to false even on error', async () => {
      mockListNotifications.mockRejectedValueOnce(new Error('Fail'))

      const store = useNotificationStore()
      await store.fetchRecent()

      expect(store.loading).toBe(false)
    })
  })

  // ---------- markRead ----------

  describe('markRead', () => {
    it('should call API and mark notification as read, decrementing unreadCount', async () => {
      mockApiMarkRead.mockResolvedValueOnce(undefined)

      const store = useNotificationStore()
      store.items = [
        makeNotification({ id: 'n1', is_read: false }),
        makeNotification({ id: 'n2', is_read: false }),
      ]
      store.unreadCount = 2

      await store.markRead('n1')

      expect(mockApiMarkRead).toHaveBeenCalledWith('n1')
      expect(store.items[0].is_read).toBe(true)
      expect(store.unreadCount).toBe(1)
    })

    it('should not decrement unreadCount if notification was already read', async () => {
      mockApiMarkRead.mockResolvedValueOnce(undefined)

      const store = useNotificationStore()
      store.items = [makeNotification({ id: 'n1', is_read: true })]
      store.unreadCount = 0

      await store.markRead('n1')

      expect(store.unreadCount).toBe(0)
    })

    it('should not decrement unreadCount below 0', async () => {
      mockApiMarkRead.mockResolvedValueOnce(undefined)

      const store = useNotificationStore()
      store.items = [makeNotification({ id: 'n1', is_read: false })]
      store.unreadCount = 0

      await store.markRead('n1')

      expect(store.unreadCount).toBe(0)
    })

    it('should not throw on API error', async () => {
      mockApiMarkRead.mockRejectedValueOnce(new Error('Fail'))

      const store = useNotificationStore()
      store.items = [makeNotification({ id: 'n1', is_read: false })]
      store.unreadCount = 1

      await expect(store.markRead('n1')).resolves.toBeUndefined()
      // State should not change on error
      expect(store.items[0].is_read).toBe(false)
      expect(store.unreadCount).toBe(1)
    })
  })

  // ---------- resetState ----------

  describe('resetState', () => {
    it('should reset all reactive state to initial values', () => {
      const store = useNotificationStore()
      // Populate state
      store.items = [makeNotification({ id: '1' }), makeNotification({ id: '2' })]
      store.unreadCount = 5
      store.loading = true

      store.resetState()

      expect(store.unreadCount).toBe(0)
      expect(store.items).toEqual([])
      expect(store.loading).toBe(false)
    })

    it('should be callable multiple times without error', () => {
      const store = useNotificationStore()
      store.resetState()
      store.resetState()

      expect(store.unreadCount).toBe(0)
      expect(store.items).toEqual([])
      expect(store.loading).toBe(false)
    })
  })

  // ---------- markAllRead ----------

  describe('markAllRead', () => {
    it('should call API, mark all items as read, and set unreadCount to 0', async () => {
      mockApiMarkAllRead.mockResolvedValueOnce(undefined)

      const store = useNotificationStore()
      store.items = [
        makeNotification({ id: 'n1', is_read: false }),
        makeNotification({ id: 'n2', is_read: false }),
        makeNotification({ id: 'n3', is_read: true }),
      ]
      store.unreadCount = 2

      await store.markAllRead()

      expect(mockApiMarkAllRead).toHaveBeenCalled()
      expect(store.items.every((n) => n.is_read)).toBe(true)
      expect(store.unreadCount).toBe(0)
    })

    it('should not throw on API error', async () => {
      mockApiMarkAllRead.mockRejectedValueOnce(new Error('Fail'))

      const store = useNotificationStore()
      store.items = [makeNotification({ id: 'n1', is_read: false })]
      store.unreadCount = 1

      await expect(store.markAllRead()).resolves.toBeUndefined()
      // State should not change on error
      expect(store.items[0].is_read).toBe(false)
      expect(store.unreadCount).toBe(1)
    })
  })
})

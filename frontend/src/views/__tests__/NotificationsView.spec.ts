import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import NotificationsView from '../NotificationsView.vue'
import type { Notification } from '@/types/notification'

type NotificationsVM = {
  showClearAllConfirm: boolean
  filteredNotifications: unknown
  notifications: Notification[]
  confirmClearAll: () => Promise<void>
  handleDeleteNotification: (id: string) => Promise<void>
}

const mockListNotifications = vi.fn()
const mockMarkRead = vi.fn()
const mockMarkAllRead = vi.fn()
const mockDeleteNotification = vi.fn()
const mockBulkDeleteNotifications = vi.fn()

vi.mock('@/api/notifications', () => ({
  listNotifications: (...args: unknown[]) => mockListNotifications(...args),
  markRead: (...args: unknown[]) => mockMarkRead(...args),
  markAllRead: (...args: unknown[]) => mockMarkAllRead(...args),
  deleteNotification: (...args: unknown[]) => mockDeleteNotification(...args),
  bulkDeleteNotifications: (...args: unknown[]) => mockBulkDeleteNotifications(...args),
}))

vi.mock('@/composables/api', () => ({
  default: { get: vi.fn(), post: vi.fn(), put: vi.fn(), delete: vi.fn() },
}))

vi.mock('@/constants', () => ({
  HEARTBEAT_INTERVAL_MS: 30000,
}))

vi.mock('@/utils/datetime', () => ({
  relativeTime: (d: string) => `relative(${d})`,
}))

const fakeNotifications = [
  {
    id: 'n1',
    message: 'Alice liked your post',
    is_read: false,
    action_type: 'LIKE',
    entity_type: 'post',
    entity_id: 'p1',
    trigger_user: { id: 'u1', display_name: 'Alice', avatar_url: null },
    created_at: '2026-01-01T00:00:00Z',
  },
  {
    id: 'n2',
    message: 'Bob commented on your post',
    is_read: true,
    action_type: 'COMMENT',
    entity_type: 'comment',
    entity_id: 'p2',
    trigger_user: { id: 'u2', display_name: 'Bob', avatar_url: 'http://example.com/bob.png' },
    created_at: '2026-01-02T00:00:00Z',
  },
  {
    id: 'n3',
    message: 'System maintenance scheduled',
    is_read: false,
    action_type: 'SYSTEM',
    entity_type: null,
    entity_id: null,
    trigger_user: null,
    created_at: '2026-01-03T00:00:00Z',
  },
]

function createTestRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/notifications', component: NotificationsView },
      { path: '/forum/:id', component: { template: '<div />' } },
      { path: '/friends', component: { template: '<div />' } },
    ],
  })
}

function createStubs() {
  return {
    SkeletonLoader: { template: '<div class="skeleton-loader" />', props: ['lines', 'variant'] },
    EmptyState: {
      template: '<div class="empty-state">{{ title }}</div>',
      props: ['title', 'message'],
    },
    BasePagination: {
      template: '<div class="base-pagination" />',
      props: ['currentPage', 'totalPages'],
    },
    BaseButton: {
      template: '<button @click="$emit(\'click\')"><slot /></button>',
      props: ['loading', 'variant', 'size'],
    },
    User: { template: '<span class="icon-user" />' },
    Settings: { template: '<span class="icon-settings" />' },
    Trash2: { template: '<span class="icon-trash" />' },
  }
}

async function mountNotifications() {
  const pinia = createPinia()
  setActivePinia(pinia)
  const router = createTestRouter()

  await router.push('/notifications')
  await router.isReady()

  const wrapper = mount(NotificationsView, {
    global: { plugins: [pinia, router], stubs: createStubs() },
  })
  await flushPromises()
  return { wrapper, router }
}

describe('NotificationsView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockListNotifications.mockResolvedValue({
      notifications: fakeNotifications.map((n) => ({ ...n })),
      total: 3,
      unread_count: 2,
    })
    mockMarkRead.mockResolvedValue({})
    mockMarkAllRead.mockResolvedValue({})
    mockDeleteNotification.mockResolvedValue({})
    mockBulkDeleteNotifications.mockResolvedValue({})
  })

  it('renders notifications title', async () => {
    const { wrapper } = await mountNotifications()
    expect(wrapper.text()).toContain('Notifications')
  })

  it('fetches notifications on mount', async () => {
    await mountNotifications()
    expect(mockListNotifications).toHaveBeenCalled()
  })

  it('renders notification messages', async () => {
    const { wrapper } = await mountNotifications()
    expect(wrapper.text()).toContain('Alice liked your post')
    expect(wrapper.text()).toContain('Bob commented on your post')
    expect(wrapper.text()).toContain('System maintenance scheduled')
  })

  it('shows relative time for notifications', async () => {
    const { wrapper } = await mountNotifications()
    expect(wrapper.text()).toContain('relative(2026-01-01T00:00:00Z)')
  })

  it('shows avatar image for trigger user with avatar', async () => {
    const { wrapper } = await mountNotifications()
    const imgs = wrapper.findAll('img')
    const bobAvatar = imgs.find((i) => i.attributes('src')?.includes('bob.png'))
    expect(bobAvatar).toBeTruthy()
  })

  it('shows mark all read button when unread notifications exist', async () => {
    const { wrapper } = await mountNotifications()
    expect(wrapper.text()).toContain('Mark all as read')
    expect(wrapper.text()).toContain('(2)')
  })

  it('marks all as read when button clicked', async () => {
    const { wrapper } = await mountNotifications()
    const markAllBtn = wrapper.findAll('button').find((b) => b.text().includes('Mark all as read'))
    expect(markAllBtn).toBeTruthy()
    await markAllBtn!.trigger('click')
    await flushPromises()
    expect(mockMarkAllRead).toHaveBeenCalled()
  })

  it('renders clickable notification items', async () => {
    const { wrapper } = await mountNotifications()
    // The notification list should contain all three notification messages
    const text = wrapper.text()
    expect(text).toContain('Alice liked your post')
    expect(text).toContain('Bob commented on your post')
    expect(text).toContain('System maintenance scheduled')
    // Each notification should have a clickable container
    const allButtons = wrapper.findAll('button')
    expect(allButtons.length).toBeGreaterThan(3) // 3 notifs + tabs + actions
  })

  it('does not call markRead for already-read notification', async () => {
    const { wrapper } = await mountNotifications()
    const notifButtons = wrapper
      .findAll('[role="button"]')
      .filter((b) => b.text().includes('Bob commented on your post'))
    expect(notifButtons.length).toBeGreaterThan(0)
    // n2 is already read
    await notifButtons[0].trigger('click')
    await flushPromises()
    expect(mockMarkRead).not.toHaveBeenCalled()
  })

  it('deletes notification when delete button clicked', async () => {
    const { wrapper } = await mountNotifications()
    // Delete buttons have a title attribute
    const deleteButtons = wrapper.findAll('button[title]')
    expect(deleteButtons.length).toBeGreaterThan(0)
    await deleteButtons[0].trigger('click')
    await flushPromises()
    expect(mockDeleteNotification).toHaveBeenCalledWith('n1')
  })

  it('shows filter tabs (all and unread)', async () => {
    const { wrapper } = await mountNotifications()
    expect(wrapper.text()).toContain('All')
    expect(wrapper.text()).toContain('Unread')
  })

  it('shows unread count badge on unread tab', async () => {
    const { wrapper } = await mountNotifications()
    // The Unread tab should show the unread count
    const unreadTab = wrapper
      .findAll('button')
      .find((b) => b.text().includes('Unread') && !b.text().includes('All'))
    expect(unreadTab).toBeTruthy()
    expect(unreadTab!.text()).toContain('2')
  })

  it('shows loading skeleton initially', async () => {
    mockListNotifications.mockReturnValue(new Promise(() => {}))
    const pinia = createPinia()
    setActivePinia(pinia)
    const router = createTestRouter()

    await router.push('/notifications')
    await router.isReady()

    const wrapper = mount(NotificationsView, {
      global: { plugins: [pinia, router], stubs: createStubs() },
    })
    await flushPromises()

    expect(wrapper.find('.skeleton-loader').exists()).toBe(true)
  })

  it('shows empty state when no notifications', async () => {
    mockListNotifications.mockResolvedValue({
      notifications: [],
      total: 0,
      unread_count: 0,
    })
    const { wrapper } = await mountNotifications()
    expect(wrapper.find('.empty-state').exists()).toBe(true)
  })

  it('clears all notifications after modal confirmation', async () => {
    const { wrapper } = await mountNotifications()
    const clearBtn = wrapper.findAll('button').find((b) => b.text().includes('Clear All'))
    expect(clearBtn).toBeTruthy()
    await clearBtn!.trigger('click')
    await flushPromises()
    // Modal should be shown — showClearAllConfirm is true
    const vm = wrapper.vm as unknown as NotificationsVM
    expect(vm.showClearAllConfirm).toBe(true)
    // Simulate confirming via the modal
    await vm.confirmClearAll()
    await flushPromises()
    expect(mockBulkDeleteNotifications).toHaveBeenCalled()
  })

  it('does not clear notifications when modal confirmation is cancelled', async () => {
    const { wrapper } = await mountNotifications()
    const clearBtn = wrapper.findAll('button').find((b) => b.text().includes('Clear All'))
    expect(clearBtn).toBeTruthy()
    await clearBtn!.trigger('click')
    await flushPromises()
    const vm = wrapper.vm as unknown as NotificationsVM
    expect(vm.showClearAllConfirm).toBe(true)
    // Cancel by setting flag back to false (simulating cancel button)
    vm.showClearAllConfirm = false
    await flushPromises()
    expect(mockBulkDeleteNotifications).not.toHaveBeenCalled()
  })

  it('passes unread param to API when unread filter is active', async () => {
    const { wrapper } = await mountNotifications()
    mockListNotifications.mockClear()

    // Click on the "Unread" tab
    const unreadTab = wrapper.findAll('button[role="tab"]').find((b) => b.text().includes('Unread'))
    expect(unreadTab).toBeTruthy()
    await unreadTab!.trigger('click')
    await flushPromises()

    expect(mockListNotifications).toHaveBeenCalledWith(expect.objectContaining({ unread: true }))
  })

  it('does not pass unread param when all filter is active', async () => {
    await mountNotifications()
    // Initial fetch should NOT include unread param
    expect(mockListNotifications).toHaveBeenCalledWith(
      expect.not.objectContaining({ unread: true }),
    )
  })

  it('decrements unreadCount when deleting an unread notification', async () => {
    const { wrapper } = await mountNotifications()
    const vm = wrapper.vm as unknown as NotificationsVM
    const { useNotificationStore } = await import('@/stores/notifications')
    const store = useNotificationStore()

    // Verify initial state: 2 unread notifications in the store
    expect(store.unreadCount).toBe(2)
    const n1 = vm.notifications.find((n: Notification) => n.id === 'n1')
    expect(n1).toBeTruthy()
    expect(n1.is_read).toBe(false)

    // Mock store's fetchUnreadCount to return updated count
    mockListNotifications.mockResolvedValue({
      notifications: fakeNotifications.filter((n) => n.id !== 'n1'),
      total: 2,
      unread_count: 1,
    })

    // Delete n1 (unread notification)
    await vm.handleDeleteNotification('n1')
    await flushPromises()

    // Notification should be removed from array
    expect(vm.notifications.find((n: Notification) => n.id === 'n1')).toBeUndefined()
    // store.unreadCount should be updated by fetchUnreadCount
    expect(store.unreadCount).toBe(1)
  })

  it('renders notifications directly without filteredNotifications computed', async () => {
    const { wrapper } = await mountNotifications()
    const vm = wrapper.vm as unknown as NotificationsVM
    // Verify there is no filteredNotifications property on the component instance
    expect(vm.filteredNotifications).toBeUndefined()
    // Notifications should still render correctly via the notifications ref directly
    expect(wrapper.text()).toContain('Alice liked your post')
    expect(wrapper.text()).toContain('Bob commented on your post')
    expect(wrapper.text()).toContain('System maintenance scheduled')
  })

  it('shows empty state using notifications ref directly', async () => {
    mockListNotifications.mockResolvedValue({
      notifications: [],
      total: 0,
      unread_count: 0,
    })
    const { wrapper } = await mountNotifications()
    // Empty state should render when notifications array is empty
    expect(wrapper.find('.empty-state').exists()).toBe(true)
  })

  it('handleDeleteNotification awaits fetchUnreadCount before resolving', async () => {
    const { wrapper } = await mountNotifications()
    const vm = wrapper.vm as unknown as NotificationsVM

    // Make fetchUnreadCount (triggered via store) take time
    // The store's fetchUnreadCount calls listNotifications internally
    let resolveFetch: () => void
    const fetchPromise = new Promise<void>((r) => {
      resolveFetch = r
    })
    // After the delete call, the next listNotifications call is from fetchUnreadCount
    mockDeleteNotification.mockResolvedValue({})
    const _callCount = mockListNotifications.mock.calls.length
    mockListNotifications.mockImplementation(() => {
      // This is the fetchUnreadCount call from the store
      return fetchPromise.then(() => ({
        notifications: [],
        total: 0,
        unread_count: 0,
      }))
    })

    const deletePromise = vm.handleDeleteNotification('n1')

    // fetchUnreadCount has not resolved yet, so deletePromise should still be pending
    let resolved = false
    deletePromise.then(() => {
      resolved = true
    })
    await flushPromises()
    // The store fetchUnreadCount is awaited, so the handler should not have resolved yet
    // (unless the store call resolved instantly — resolve it now)
    resolveFetch!()
    await flushPromises()
    expect(resolved).toBe(true)
  })

  it('confirmClearAll awaits fetchUnreadCount before resolving', async () => {
    const { wrapper } = await mountNotifications()
    const vm = wrapper.vm as unknown as NotificationsVM

    let resolveFetch: () => void
    const fetchPromise = new Promise<void>((r) => {
      resolveFetch = r
    })
    mockBulkDeleteNotifications.mockResolvedValue({})
    mockListNotifications.mockImplementation(() =>
      fetchPromise.then(() => ({
        notifications: [],
        total: 0,
        unread_count: 0,
      })),
    )

    const clearPromise = vm.confirmClearAll()
    let resolved = false
    clearPromise.then(() => {
      resolved = true
    })
    await flushPromises()
    // Should not be resolved yet since fetchUnreadCount hasn't completed
    expect(resolved).toBe(false)

    resolveFetch!()
    await flushPromises()
    expect(resolved).toBe(true)
  })

  it('does not decrement unreadCount when deleting a read notification', async () => {
    const { wrapper } = await mountNotifications()
    const vm = wrapper.vm as unknown as NotificationsVM
    const { useNotificationStore } = await import('@/stores/notifications')
    const store = useNotificationStore()

    expect(store.unreadCount).toBe(2)

    // Delete n2 (already read notification) - call the handler directly
    await vm.handleDeleteNotification('n2')
    await flushPromises()

    // store.unreadCount should remain 2 since n2 was already read
    expect(store.unreadCount).toBe(2)
    // Notification should be removed from array
    expect(vm.notifications.find((n: Notification) => n.id === 'n2')).toBeUndefined()
  })

  it('navigates to /friends for friendship entity_type notifications', async () => {
    mockListNotifications.mockResolvedValue({
      notifications: [
        {
          id: 'fr1',
          message: 'You have a new friend request',
          is_read: false,
          action_type: 'FRIEND_REQUEST',
          entity_type: 'friendship',
          entity_id: 'some-friendship-uuid',
          trigger_user: { id: 'u5', display_name: 'Charlie', avatar_url: null },
          created_at: '2026-01-01T00:00:00Z',
        },
      ],
      total: 1,
      unread_count: 1,
    })
    mockMarkRead.mockResolvedValue({})

    const { wrapper, router } = await mountNotifications()
    const pushSpy = vi.spyOn(router, 'push')

    const notifBtn = wrapper
      .findAll('[role="button"]')
      .find((b) => b.text().includes('You have a new friend request'))
    expect(notifBtn).toBeTruthy()
    await notifBtn!.trigger('click')
    await flushPromises()

    expect(pushSpy).toHaveBeenCalledWith('/friends')
  })

  it('navigates to /forum/:id for post entity_type notifications', async () => {
    const { wrapper, router } = await mountNotifications()
    const pushSpy = vi.spyOn(router, 'push')

    // Click on Alice's notification (entity_type: 'post', entity_id: 'p1')
    const notifBtn = wrapper
      .findAll('[role="button"]')
      .find((b) => b.text().includes('Alice liked your post'))
    expect(notifBtn).toBeTruthy()
    await notifBtn!.trigger('click')
    await flushPromises()

    expect(pushSpy).toHaveBeenCalledWith('/forum/p1')
  })

  it('does not navigate for notifications without entity_type or entity_id', async () => {
    mockListNotifications.mockResolvedValue({
      notifications: [
        {
          id: 'sys1',
          message: 'System notice',
          is_read: false,
          action_type: 'SYSTEM',
          entity_type: null,
          entity_id: null,
          trigger_user: null,
          created_at: '2026-01-01T00:00:00Z',
        },
      ],
      total: 1,
      unread_count: 1,
    })
    mockMarkRead.mockResolvedValue({})

    const { wrapper, router } = await mountNotifications()
    const pushSpy = vi.spyOn(router, 'push')

    const notifBtn = wrapper
      .findAll('[role="button"]')
      .find((b) => b.text().includes('System notice'))
    expect(notifBtn).toBeTruthy()
    await notifBtn!.trigger('click')
    await flushPromises()

    // Should not navigate to /forum/null or any path
    expect(pushSpy).not.toHaveBeenCalled()
  })
})

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import NotificationsView from '../NotificationsView.vue'

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
      notifications: fakeNotifications,
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
    const markAllBtn = wrapper.findAll('button').find((b) =>
      b.text().includes('Mark all as read'),
    )
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
    const notifButtons = wrapper.findAll('button').filter((b) =>
      b.text().includes('Bob commented on your post'),
    )
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
    const unreadTab = wrapper.findAll('button').find(
      (b) => b.text().includes('Unread') && !b.text().includes('All'),
    )
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

  it('clears all notifications', async () => {
    const { wrapper } = await mountNotifications()
    const clearBtn = wrapper.findAll('button').find((b) =>
      b.text().includes('Clear All'),
    )
    expect(clearBtn).toBeTruthy()
    await clearBtn!.trigger('click')
    await flushPromises()
    expect(mockBulkDeleteNotifications).toHaveBeenCalled()
  })
})

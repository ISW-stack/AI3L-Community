import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import NotificationsView from '../NotificationsView.vue'

const mockListNotifications = vi.fn()

vi.mock('@/api/notifications', () => ({
  listNotifications: (...args: unknown[]) => mockListNotifications(...args),
  markRead: vi.fn().mockResolvedValue({}),
  markAllRead: vi.fn().mockResolvedValue({}),
  deleteNotification: vi.fn().mockResolvedValue({}),
  bulkDeleteNotifications: vi.fn().mockResolvedValue({}),
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

describe('NotificationsView filter tabs ARIA', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockListNotifications.mockResolvedValue({
      notifications: [
        {
          id: 'n1',
          message: 'Test notification',
          is_read: false,
          action_type: 'LIKE',
          entity_type: 'post',
          entity_id: 'p1',
          trigger_user: null,
          created_at: '2026-01-01T00:00:00Z',
        },
      ],
      total: 1,
      unread_count: 1,
    })
  })

  async function mountView() {
    const pinia = createPinia()
    setActivePinia(pinia)
    const router = createTestRouter()
    await router.push('/notifications')
    await router.isReady()

    const wrapper = mount(NotificationsView, {
      global: { plugins: [pinia, router], stubs: createStubs() },
    })
    await flushPromises()
    return wrapper
  }

  it('has role="tablist" on the filter container', async () => {
    const wrapper = await mountView()
    const tablist = wrapper.find('[role="tablist"]')
    expect(tablist.exists()).toBe(true)
  })

  it('has role="tab" on each filter button', async () => {
    const wrapper = await mountView()
    const tabs = wrapper.findAll('[role="tab"]')
    expect(tabs.length).toBe(2)
  })

  it('has aria-selected="true" on the active tab', async () => {
    const wrapper = await mountView()
    const tabs = wrapper.findAll('[role="tab"]')
    // "All" tab is active by default
    const allTab = tabs.find((t) => t.text().includes('All'))
    expect(allTab).toBeTruthy()
    expect(allTab!.attributes('aria-selected')).toBe('true')
  })

  it('has aria-selected="false" on the inactive tab', async () => {
    const wrapper = await mountView()
    const tabs = wrapper.findAll('[role="tab"]')
    const unreadTab = tabs.find((t) => t.text().includes('Unread'))
    expect(unreadTab).toBeTruthy()
    expect(unreadTab!.attributes('aria-selected')).toBe('false')
  })

  it('updates aria-selected when switching tabs', async () => {
    const wrapper = await mountView()
    const tabs = wrapper.findAll('[role="tab"]')
    const unreadTab = tabs.find((t) => t.text().includes('Unread'))
    await unreadTab!.trigger('click')
    await wrapper.vm.$nextTick()

    const updatedTabs = wrapper.findAll('[role="tab"]')
    const allTab = updatedTabs.find((t) => t.text().includes('All') && !t.text().includes('Unread'))
    const newUnreadTab = updatedTabs.find((t) => t.text().includes('Unread'))
    expect(newUnreadTab!.attributes('aria-selected')).toBe('true')
    expect(allTab!.attributes('aria-selected')).toBe('false')
  })
})

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import { nextTick } from 'vue'
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
    BaseModal: {
      template:
        '<div v-if="modelValue" class="base-modal" data-testid="confirm-modal"><slot /><slot name="footer" /></div>',
      props: ['modelValue', 'title', 'size', 'persistent'],
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

describe('Confirmation Modals', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockListNotifications.mockResolvedValue({
      notifications: fakeNotifications.map((n) => ({ ...n })),
      total: 2,
      unread_count: 1,
    })
    mockMarkRead.mockResolvedValue({})
    mockMarkAllRead.mockResolvedValue({})
    mockDeleteNotification.mockResolvedValue({})
    mockBulkDeleteNotifications.mockResolvedValue({})
  })

  it('shows a confirmation modal when Clear All is clicked', async () => {
    const { wrapper } = await mountNotifications()

    // Verify modal is not visible initially
    expect(wrapper.find('[data-testid="confirm-modal"]').exists()).toBe(false)

    // Click Clear All button
    const clearBtn = wrapper.findAll('button').find((b) => b.text().includes('Clear All'))
    expect(clearBtn).toBeTruthy()
    await clearBtn!.trigger('click')
    await nextTick()

    // Modal should now be visible
    const vm = wrapper.vm as unknown as { showClearAllConfirm: boolean; confirmClearAll: () => Promise<void> }
    expect(vm.showClearAllConfirm).toBe(true)
    expect(wrapper.find('[data-testid="confirm-modal"]').exists()).toBe(true)

    // The bulk delete API should NOT have been called yet
    expect(mockBulkDeleteNotifications).not.toHaveBeenCalled()
  })

  it('executes delete action only after modal confirmation', async () => {
    const { wrapper } = await mountNotifications()

    // Click Clear All to show modal
    const clearBtn = wrapper.findAll('button').find((b) => b.text().includes('Clear All'))
    await clearBtn!.trigger('click')
    await nextTick()

    // Verify API not called yet
    expect(mockBulkDeleteNotifications).not.toHaveBeenCalled()

    // Simulate clicking the confirm button in the modal
    const vm = wrapper.vm as unknown as { showClearAllConfirm: boolean; confirmClearAll: () => Promise<void> }
    await vm.confirmClearAll()
    await flushPromises()

    // Now the API should have been called
    expect(mockBulkDeleteNotifications).toHaveBeenCalled()
    // Modal should be closed
    expect(vm.showClearAllConfirm).toBe(false)
  })
})

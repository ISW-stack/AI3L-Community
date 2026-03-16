import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { ref } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'

// ── Mocks ──

vi.mock('@/composables/api', () => ({
  default: { get: vi.fn(), post: vi.fn(), put: vi.fn(), delete: vi.fn() },
}))

vi.mock('@/constants', () => ({
  HEARTBEAT_INTERVAL_MS: 30000,
}))

const mockGetSigPosts = vi.fn()
vi.mock('@/api/sigs', () => ({
  getSigPosts: (...args: unknown[]) => mockGetSigPosts(...args),
}))

const mockListNotifications = vi.fn()
vi.mock('@/api/notifications', () => ({
  listNotifications: (...args: unknown[]) => mockListNotifications(...args),
  markRead: vi.fn(),
  markAllRead: vi.fn(),
  deleteNotification: vi.fn(),
  bulkDeleteNotifications: vi.fn(),
}))

vi.mock('@/stores/toast', () => ({
  useToastStore: vi.fn(() => ({ show: vi.fn() })),
}))

vi.mock('@/stores/notifications', () => ({
  useNotificationStore: vi.fn(() => ({ fetchUnreadCount: vi.fn() })),
}))

vi.mock('@/utils/datetime', () => ({
  relativeTime: (d: string) => `relative(${d})`,
}))

// ── Helpers ──

const fakePosts = [
  {
    id: 'p1',
    title: 'Post One',
    content: '<p>Content</p>',
    author: { id: 'u1', username: 'alice', display_name: 'Alice', avatar_url: null },
    category_id: null,
    category_name: null,
    sig_id: 'sig1',
    sig_name: 'Test SIG',
    keywords: null,
    allow_comments: true,
    version: 1,
    comment_count: 1,
    is_pinned: false,
    view_count: 5,
    last_comment_at: null,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
  },
]

// ── Test: SigPostsView pagination ──

describe('SigPostsView pagination', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders BasePagination when total_pages > 1', async () => {
    mockGetSigPosts.mockResolvedValue({ posts: fakePosts, total: 50, total_pages: 3 })

    const SigPostsView = (await import('../sigs/SigPostsView.vue')).default

    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        {
          path: '/sigs/:id',
          component: { template: '<div />' },
          children: [{ path: 'posts', name: 'sig-posts', component: SigPostsView }],
        },
        { path: '/forum/create', component: { template: '<div />' } },
        { path: '/forum/:id', component: { template: '<div />' } },
        { path: '/users/:id', component: { template: '<div />' } },
        { path: '/', component: { template: '<div />' } },
        { path: '/sigs', component: { template: '<div />' } },
      ],
    })
    const pinia = createPinia()
    setActivePinia(pinia)
    await router.push('/sigs/sig1/posts')
    await router.isReady()

    const wrapper = mount(SigPostsView, {
      global: {
        plugins: [pinia, router],
        provide: {
          sig: ref({
            id: 'sig1',
            name: 'Test SIG',
            description: null,
            created_by: 'u1',
            creator_display_name: null,
            member_count: 2,
            created_at: '2026-01-01T00:00:00Z',
          }),
          userSigRole: ref(null),
        },
        stubs: {
          BaseCard: {
            template: '<div class="base-card"><slot /></div>',
            props: ['hoverable', 'padding'],
          },
          BaseAvatar: { template: '<span />', props: ['src', 'name', 'size'] },
          SkeletonLoader: { template: '<div class="skeleton" />', props: ['variant', 'lines'] },
          EmptyState: { template: '<div />', props: ['title', 'message'] },
          FloatingCreateButton: { template: '<div />', props: ['to'] },
        },
      },
    })
    await flushPromises()

    // BasePagination should be rendered (not stubbed, so it renders as a <nav>)
    const paginationNav = wrapper.find('nav[aria-label]')
    expect(paginationNav.exists()).toBe(true)

    // Verify API was called with pagination params
    expect(mockGetSigPosts).toHaveBeenCalledWith('sig1', { page: 1, page_size: 20 })
  })
})

// ── Test: NotificationsView breadcrumb ──

describe('NotificationsView breadcrumb', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders BaseBreadcrumb with Home and Notifications items', async () => {
    mockListNotifications.mockResolvedValue({
      notifications: [],
      total: 0,
      unread_count: 0,
    })

    const NotificationsView = (await import('../NotificationsView.vue')).default

    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/notifications', component: NotificationsView },
        { path: '/', component: { template: '<div />' } },
        { path: '/forum/:id', component: { template: '<div />' } },
      ],
    })
    const pinia = createPinia()
    setActivePinia(pinia)
    await router.push('/notifications')
    await router.isReady()

    const wrapper = mount(NotificationsView, {
      global: {
        plugins: [pinia, router],
        stubs: {
          SkeletonLoader: { template: '<div />', props: ['lines', 'variant'] },
          EmptyState: { template: '<div />', props: ['title', 'message'] },
          BaseButton: { template: '<button><slot /></button>' },
          BaseModal: { template: '<div />', props: ['modelValue', 'title', 'size'] },
        },
      },
    })
    await flushPromises()

    // BaseBreadcrumb renders a <nav> with aria-label="Breadcrumb"
    const breadcrumbNav = wrapper.find('nav[aria-label="Breadcrumb"]')
    expect(breadcrumbNav.exists()).toBe(true)
    expect(breadcrumbNav.text()).toContain('Home')
    expect(breadcrumbNav.text()).toContain('Notifications')
  })
})

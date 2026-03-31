import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'

const mockListEvents = vi.fn()

vi.mock('@/api/events', () => ({
  listEvents: (...args: unknown[]) => mockListEvents(...args),
}))

vi.mock('@/composables/api', () => ({
  default: { get: vi.fn(), post: vi.fn(), put: vi.fn(), delete: vi.fn() },
}))

vi.mock('@/utils/date', () => ({
  formatDate: (_d: string) => '2026-03-31',
  formatDateTime: (_d: string) => '2026-03-31 12:00',
}))

import EventsView from '../events/EventsView.vue'
import { useAuthStore } from '@/stores/auth'

function createStubs() {
  return {
    SkeletonLoader: { template: '<div class="skeleton" />', props: ['lines', 'variant'] },
    EmptyState: { template: '<div class="empty-state"><slot /></div>', props: ['title', 'message'] },
    BaseCard: { template: '<div class="base-card"><slot /></div>' },
    BaseBadge: { template: '<span class="badge"><slot /></span>', props: ['variant', 'size'] },
    BaseBreadcrumb: { template: '<nav />', props: ['items'] },
    BasePagination: {
      template: '<div class="pagination" />',
      props: ['currentPage', 'totalPages', 'pageSize', 'total'],
    },
    BaseButton: { template: '<button><slot /></button>', props: ['loading', 'variant', 'size'] },
    FloatingCreateButton: { template: '<div />', props: ['to'] },
    RouterLink: { template: '<a><slot /></a>', props: ['to'] },
  }
}

const fakeEvent = {
  id: '1',
  title: 'Test Event',
  content: '<p>Hi</p>',
  author: { id: 'u1', username: 'admin', display_name: 'Admin', avatar_url: null },
  sig_id: null,
  sig_name: null,
  visibility: ['MEMBER'],
  allow_comments: true,
  comment_count: 5,
  reaction_counts: null,
  user_reactions: null,
  version: 1,
  created_at: '2026-03-31T00:00:00',
  updated_at: '2026-03-31T00:00:00',
}

describe('EventsView', () => {
  let router: ReturnType<typeof createRouter>

  beforeEach(() => {
    vi.clearAllMocks()
    const pinia = createPinia()
    setActivePinia(pinia)
    router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/events', component: EventsView },
        { path: '/events/create', component: { template: '<div />' } },
        { path: '/events/:id', component: { template: '<div />' } },
        { path: '/sigs/:id', component: { template: '<div />' } },
        { path: '/', component: { template: '<div />' } },
      ],
    })
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('renders loading skeleton initially', async () => {
    mockListEvents.mockReturnValue(new Promise(() => {})) // never resolves
    await router.push('/events')
    await router.isReady()

    const wrapper = mount(EventsView, {
      global: { plugins: [createPinia(), router], stubs: createStubs() },
    })

    expect(wrapper.find('.skeleton').exists()).toBe(true)
  })

  it('renders events list', async () => {
    mockListEvents.mockResolvedValue({
      events: [fakeEvent],
      total: 1,
      page: 1,
      total_pages: 1,
    })

    await router.push('/events')
    await router.isReady()

    const wrapper = mount(EventsView, {
      global: { plugins: [createPinia(), router], stubs: createStubs() },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('Test Event')
    expect(wrapper.text()).toContain('Admin')
  })

  it('renders empty state when no events', async () => {
    mockListEvents.mockResolvedValue({
      events: [],
      total: 0,
      page: 1,
      total_pages: 1,
    })

    await router.push('/events')
    await router.isReady()

    const wrapper = mount(EventsView, {
      global: { plugins: [createPinia(), router], stubs: createStubs() },
    })
    await flushPromises()

    expect(wrapper.find('.empty-state').exists()).toBe(true)
  })

  it('shows create button for admin users', async () => {
    mockListEvents.mockResolvedValue({ events: [], total: 0, page: 1, total_pages: 1 })

    const pinia = createPinia()
    setActivePinia(pinia)
    const auth = useAuthStore()
    auth.role = 'ADMIN'
    auth.expiresAt = Date.now() + 3600000

    await router.push('/events')
    await router.isReady()

    const wrapper = mount(EventsView, {
      global: { plugins: [pinia, router], stubs: createStubs() },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('Create Event')
  })

  it('does not show create button for non-admin users', async () => {
    mockListEvents.mockResolvedValue({ events: [], total: 0, page: 1, total_pages: 1 })

    const pinia = createPinia()
    setActivePinia(pinia)
    const auth = useAuthStore()
    auth.role = 'MEMBER'
    auth.expiresAt = Date.now() + 3600000

    await router.push('/events')
    await router.isReady()

    const wrapper = mount(EventsView, {
      global: { plugins: [pinia, router], stubs: createStubs() },
    })
    await flushPromises()

    // The create button links to /events/create — should not be present for non-admin
    const links = wrapper.findAll('a')
    const createLink = links.filter((l) => l.attributes('to') === '/events/create')
    expect(createLink.length).toBe(0)
  })

  it('renders visibility badges', async () => {
    mockListEvents.mockResolvedValue({
      events: [{ ...fakeEvent, visibility: ['GUEST', 'MEMBER'] }],
      total: 1,
      page: 1,
      total_pages: 1,
    })

    await router.push('/events')
    await router.isReady()

    const wrapper = mount(EventsView, {
      global: { plugins: [createPinia(), router], stubs: createStubs() },
    })
    await flushPromises()

    const badges = wrapper.findAll('.badge')
    expect(badges.length).toBeGreaterThanOrEqual(2)
  })

  it('calls listEvents with correct params', async () => {
    mockListEvents.mockResolvedValue({ events: [], total: 0, page: 1, total_pages: 1 })

    await router.push('/events')
    await router.isReady()

    mount(EventsView, {
      global: { plugins: [createPinia(), router], stubs: createStubs() },
    })
    await flushPromises()

    expect(mockListEvents).toHaveBeenCalledWith({ page: 1, page_size: 20 })
  })
})

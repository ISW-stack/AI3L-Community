import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { ref } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import SigPostsView from '../SigPostsView.vue'

// Standard mocks
vi.mock('@/composables/api', () => ({
  default: {
    post: vi.fn(),
    get: vi.fn(),
  },
}))

vi.mock('@/constants', () => ({
  HEARTBEAT_INTERVAL_MS: 30000,
}))

const mockGetSigPosts = vi.fn()

vi.mock('@/api/sigs', () => ({
  getSigPosts: (...args: unknown[]) => mockGetSigPosts(...args),
}))

vi.mock('@/stores/toast', () => ({
  useToastStore: vi.fn(() => ({
    show: vi.fn(),
  })),
}))

const fakePosts = [
  {
    id: 'p1',
    title: 'First Post',
    content: '<p>Hello</p>',
    author: {
      id: 'u1',
      username: 'alice',
      display_name: 'Alice Smith',
      avatar_url: null,
    },
    category_id: null,
    category_name: null,
    sig_id: 'sig1',
    sig_name: 'Test SIG',
    keywords: null,
    allow_comments: true,
    version: 1,
    comment_count: 3,
    is_pinned: false,
    view_count: 10,
    last_comment_at: null,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
  },
  {
    id: 'p2',
    title: 'Second Post',
    content: '<p>World</p>',
    author: {
      id: 'u2',
      username: 'bob',
      display_name: 'Bob Jones',
      avatar_url: null,
    },
    category_id: null,
    category_name: null,
    sig_id: 'sig1',
    sig_name: 'Test SIG',
    keywords: null,
    allow_comments: true,
    version: 1,
    comment_count: 0,
    is_pinned: false,
    view_count: 5,
    last_comment_at: null,
    created_at: '2026-01-02T00:00:00Z',
    updated_at: '2026-01-02T00:00:00Z',
  },
]

function createTestRouter() {
  return createRouter({
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
    ],
  })
}

async function mountComponent(options?: { userSigRole?: ReturnType<typeof ref> | undefined }) {
  const router = createTestRouter()
  const pinia = createPinia()
  setActivePinia(pinia)
  await router.push('/sigs/sig1/posts')
  await router.isReady()

  const provide: Record<string, unknown> = {}
  if (options?.userSigRole !== undefined) {
    provide.userSigRole = options.userSigRole
  }

  const wrapper = mount(SigPostsView, {
    global: {
      plugins: [pinia, router],
      provide,
      stubs: {
        BaseCard: {
          template: '<div class="base-card"><slot /></div>',
          props: ['hoverable', 'padding'],
        },
        BaseButton: { template: '<button><slot /></button>' },
        BaseAvatar: { template: '<span class="avatar" />', props: ['src', 'name', 'size'] },
        SkeletonLoader: {
          template: '<div class="skeleton-loader" />',
          props: ['variant', 'lines'],
        },
        EmptyState: {
          template: '<div class="empty-state" v-bind="$props" />',
          props: ['title', 'message'],
        },
        FloatingCreateButton: {
          template: '<div class="fab" v-bind="$props" />',
          props: ['to'],
        },
      },
    },
  })

  return { wrapper, router }
}

describe('SigPostsView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('shows loading skeleton initially', async () => {
    // Never resolve so loading stays true
    mockGetSigPosts.mockReturnValue(new Promise(() => { }))

    const { wrapper } = await mountComponent({ userSigRole: ref(null) })

    const skeletons = wrapper.findAll('.skeleton-loader')
    expect(skeletons.length).toBe(3)
  })

  it('renders posts after loading', async () => {
    mockGetSigPosts.mockResolvedValue({ posts: fakePosts, total: 2 })

    const { wrapper } = await mountComponent({ userSigRole: ref(null) })
    await flushPromises()

    expect(wrapper.text()).toContain('Posts (2)')
    expect(wrapper.findAll('.base-card').length).toBe(2)
    expect(wrapper.findAll('.skeleton-loader').length).toBe(0)
  })

  it('shows floating create button when user is a SIG member', async () => {
    mockGetSigPosts.mockResolvedValue({ posts: fakePosts, total: 2 })

    const { wrapper } = await mountComponent({ userSigRole: ref('MEMBER') })
    await flushPromises()

    const fab = wrapper.find('.fab')
    expect(fab.exists()).toBe(true)
    expect(fab.attributes('to')).toContain('sig_id=sig1')
  })

  it('hides floating create button when user is not a member', async () => {
    mockGetSigPosts.mockResolvedValue({ posts: fakePosts, total: 2 })

    const { wrapper } = await mountComponent({ userSigRole: ref(null) })
    await flushPromises()

    expect(wrapper.find('.fab').exists()).toBe(false)
  })

  it('hides floating create button when userSigRole inject is missing (undefined)', async () => {
    mockGetSigPosts.mockResolvedValue({ posts: fakePosts, total: 2 })

    // Do not provide userSigRole at all — simulates inject returning undefined
    const { wrapper } = await mountComponent()
    await flushPromises()

    expect(wrapper.find('.fab').exists()).toBe(false)
  })

  it('shows EmptyState with correct message when no posts', async () => {
    mockGetSigPosts.mockResolvedValue({ posts: [], total: 0 })

    const { wrapper } = await mountComponent({ userSigRole: ref(null) })
    await flushPromises()

    const emptyState = wrapper.find('.empty-state')
    expect(emptyState.exists()).toBe(true)
    expect(emptyState.attributes('title')).toBe('No posts yet')
    expect(emptyState.attributes('message')).toBe(
      'Start a discussion by creating the first post in this SIG.',
    )
  })

  it('renders post title and author display name', async () => {
    mockGetSigPosts.mockResolvedValue({ posts: fakePosts, total: 2 })

    const { wrapper } = await mountComponent({ userSigRole: ref(null) })
    await flushPromises()

    expect(wrapper.text()).toContain('First Post')
    expect(wrapper.text()).toContain('Alice Smith')
    expect(wrapper.text()).toContain('Second Post')
    expect(wrapper.text()).toContain('Bob Jones')
  })
})

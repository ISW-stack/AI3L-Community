import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import ForumView from '../ForumView.vue'

const mockListPosts = vi.fn()
const mockSearchPosts = vi.fn()
const mockGetTrendingPosts = vi.fn()
const mockListCategories = vi.fn()

vi.mock('@/api/posts', () => ({
  listPosts: (...args: unknown[]) => mockListPosts(...args),
  searchPosts: (...args: unknown[]) => mockSearchPosts(...args),
  getTrendingPosts: (...args: unknown[]) => mockGetTrendingPosts(...args),
}))

vi.mock('@/api/categories', () => ({
  listCategories: (...args: unknown[]) => mockListCategories(...args),
}))

vi.mock('@/composables/api', () => ({
  default: { get: vi.fn(), post: vi.fn() },
}))

vi.mock('@/constants', () => ({
  HEARTBEAT_INTERVAL_MS: 30000,
}))

const fakeCategories = [
  { id: 'cat1', name: 'AI Research', post_count: 10 },
  { id: 'cat2', name: 'Language Learning', post_count: 5 },
]

const fakePosts = [
  {
    id: 'p1',
    title: 'Test Post 1',
    content: '<p>Hello</p>',
    created_at: '2026-01-01T00:00:00Z',
    comment_count: 3,
    view_count: 20,
    is_pinned: false,
    author: { id: 'u1', display_name: 'Alice', avatar_url: null },
    category_name: 'AI Research',
  },
  {
    id: 'p2',
    title: 'Test Post 2',
    content: '<p>World</p>',
    created_at: '2026-01-02T00:00:00Z',
    comment_count: 1,
    view_count: 5,
    is_pinned: true,
    author: { id: 'u2', display_name: 'Bob', avatar_url: null },
    category_name: null,
  },
]

const fakeTrending = [
  {
    id: 't1',
    title: 'Trending Post',
    content: 'Hot topic',
    created_at: '2026-01-01T00:00:00Z',
    comment_count: 50,
    view_count: 500,
    author: { id: 'u1', display_name: 'Alice', avatar_url: null },
  },
]

function createTestRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/forum', component: ForumView },
      { path: '/forum/create', component: { template: '<div />' } },
      { path: '/forum/:id', component: { template: '<div />' } },
    ],
  })
}

function createStubs() {
  return {
    BaseCard: { template: '<div class="base-card"><slot /></div>', props: ['hoverable'] },
    BaseButton: {
      template: '<button :disabled="$attrs.disabled" @click="$emit(\'click\')"><slot /></button>',
      props: ['loading', 'variant', 'size'],
    },
    BasePagination: {
      template: '<div class="base-pagination" />',
      props: ['currentPage', 'totalPages'],
    },
    SkeletonLoader: { template: '<div class="skeleton-loader" />', props: ['lines', 'variant'] },
    EmptyState: {
      template: '<div class="empty-state">{{ title }}</div>',
      props: ['title', 'message', 'actionLabel', 'actionTo'],
    },
    PostCard: {
      template: '<div class="post-card">{{ post.title }}</div>',
      props: ['post'],
    },
    FloatingCreateButton: { template: '<div class="fab" />', props: ['to'] },
  }
}

async function mountForum(query?: Record<string, string>) {
  const pinia = createPinia()
  setActivePinia(pinia)
  const router = createTestRouter()

  const path = '/forum' + (query ? '?' + new URLSearchParams(query).toString() : '')
  await router.push(path)
  await router.isReady()

  const wrapper = mount(ForumView, {
    global: { plugins: [pinia, router], stubs: createStubs() },
  })
  await flushPromises()
  return { wrapper, router }
}

describe('ForumView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockListPosts.mockResolvedValue({ posts: fakePosts, total: 2, total_pages: 1 })
    mockListCategories.mockResolvedValue(fakeCategories)
    mockGetTrendingPosts.mockResolvedValue(fakeTrending)
    mockSearchPosts.mockResolvedValue({ posts: [], total: 0, total_pages: 0 })
  })

  it('renders forum title', async () => {
    const { wrapper } = await mountForum()
    expect(wrapper.text()).toContain('Forum')
  })

  it('fetches posts, categories, and trending on mount', async () => {
    await mountForum()
    expect(mockListPosts).toHaveBeenCalled()
    expect(mockListCategories).toHaveBeenCalled()
    expect(mockGetTrendingPosts).toHaveBeenCalled()
  })

  it('renders post cards', async () => {
    const { wrapper } = await mountForum()
    const postCards = wrapper.findAll('.post-card')
    expect(postCards.length).toBe(2)
    expect(postCards[0].text()).toContain('Test Post 1')
    expect(postCards[1].text()).toContain('Test Post 2')
  })

  it('renders category sidebar buttons', async () => {
    const { wrapper } = await mountForum()
    expect(wrapper.text()).toContain('AI Research')
    expect(wrapper.text()).toContain('Language Learning')
  })

  it('renders trending posts sidebar', async () => {
    const { wrapper } = await mountForum()
    expect(wrapper.text()).toContain('Trending Post')
  })

  it('shows sort buttons (newest, oldest, most discussed)', async () => {
    const { wrapper } = await mountForum()
    expect(wrapper.text()).toContain('Newest')
    expect(wrapper.text()).toContain('Oldest')
    expect(wrapper.text()).toContain('Most Discussed')
  })

  it('shows total posts count', async () => {
    const { wrapper } = await mountForum()
    expect(wrapper.text()).toContain('2')
  })

  it('shows search input', async () => {
    const { wrapper } = await mountForum()
    const searchInput = wrapper.find('input[type="text"]')
    expect(searchInput.exists()).toBe(true)
  })

  it('triggers search on enter key', async () => {
    const { wrapper } = await mountForum()
    const searchInput = wrapper.find('input[type="text"]')
    await searchInput.setValue('machine learning')
    await searchInput.trigger('keyup.enter')
    await flushPromises()
    // With a keyword, should call searchPosts
    expect(mockSearchPosts).toHaveBeenCalledWith(
      expect.objectContaining({ keyword: 'machine learning' }),
    )
  })

  it('toggles advanced search panel', async () => {
    const { wrapper } = await mountForum()
    // Find the advanced toggle button
    const advancedBtn = wrapper.findAll('button').find((b) => b.text().includes('Advanced'))
    expect(advancedBtn).toBeTruthy()
    await advancedBtn!.trigger('click')
    await nextTick()
    // Date inputs should be visible
    const dateInputs = wrapper.findAll('input[type="date"]')
    expect(dateInputs.length).toBe(2)
  })

  it('shows empty state when no posts', async () => {
    mockListPosts.mockResolvedValue({ posts: [], total: 0, total_pages: 0 })
    const { wrapper } = await mountForum()
    expect(wrapper.find('.empty-state').exists()).toBe(true)
  })

  it('shows loading skeleton initially', async () => {
    mockListPosts.mockReturnValue(new Promise(() => {}))
    mockListCategories.mockResolvedValue([])
    mockGetTrendingPosts.mockResolvedValue([])

    const pinia = createPinia()
    setActivePinia(pinia)
    const router = createTestRouter()

    await router.push('/forum')
    await router.isReady()

    const wrapper = mount(ForumView, {
      global: { plugins: [pinia, router], stubs: createStubs() },
    })
    await flushPromises()

    expect(wrapper.find('.skeleton-loader').exists()).toBe(true)
  })

  it('renders floating create button', async () => {
    const { wrapper } = await mountForum()
    expect(wrapper.find('.fab').exists()).toBe(true)
  })

  it('selects category filter', async () => {
    const { wrapper } = await mountForum()
    // Find category button (in sidebar)
    const catButtons = wrapper.findAll('button').filter((b) => b.text().includes('AI Research'))
    expect(catButtons.length).toBeGreaterThan(0)
    await catButtons[0].trigger('click')
    await flushPromises()
    // Should refetch with category filter
    expect(mockListPosts).toHaveBeenCalledTimes(2) // initial + filter change
  })

  it('restores search query from URL', async () => {
    mockSearchPosts.mockResolvedValue({ posts: fakePosts, total: 2, total_pages: 1 })
    const { wrapper } = await mountForum({ q: 'AI' })
    expect(mockSearchPosts).toHaveBeenCalledWith(expect.objectContaining({ keyword: 'AI' }))
  })
})

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

// ---------------------------------------------------------------------------
// Stub IntersectionObserver (not available in jsdom)
// ---------------------------------------------------------------------------
const mockIOObserve = vi.fn()
const mockIODisconnect = vi.fn()

class MockIntersectionObserver {
  observe = mockIOObserve
  disconnect = mockIODisconnect
  unobserve = vi.fn()
  constructor() {}
}

vi.stubGlobal('IntersectionObserver', MockIntersectionObserver)

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

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

// Cursor-based page-1 response
const fakePageOneResponse = {
  posts: fakePosts,
  next_cursor: 'cursor-abc',
  has_more: true,
}

// Cursor-based page-2 response (end of feed)
const fakePageTwoResponse = {
  posts: [
    {
      id: 'p3',
      title: 'Test Post 3',
      content: '<p>More</p>',
      created_at: '2026-01-03T00:00:00Z',
      comment_count: 0,
      view_count: 1,
      is_pinned: false,
      author: { id: 'u3', display_name: 'Carol', avatar_url: null },
      category_name: null,
    },
  ],
  next_cursor: null,
  has_more: false,
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

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
    ForumLeftSidebar: { template: '<div class="forum-left-sidebar" />' },
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

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('ForumView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockListPosts.mockResolvedValue(fakePageOneResponse)
    mockListCategories.mockResolvedValue(fakeCategories)
    mockGetTrendingPosts.mockResolvedValue(fakeTrending)
    mockSearchPosts.mockResolvedValue({ posts: [], next_cursor: null, has_more: false })
    mockIOObserve.mockClear()
    mockIODisconnect.mockClear()
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

  it('initial load renders post cards', async () => {
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
    expect(mockSearchPosts).toHaveBeenCalledWith(
      expect.objectContaining({ keyword: 'machine learning' }),
    )
  })

  it('toggles advanced search panel', async () => {
    const { wrapper } = await mountForum()
    const advancedBtn = wrapper.findAll('button').find((b) => b.text().includes('Advanced'))
    expect(advancedBtn).toBeTruthy()
    await advancedBtn!.trigger('click')
    await nextTick()
    const dateInputs = wrapper.findAll('input[type="date"]')
    expect(dateInputs.length).toBe(2)
  })

  it('shows empty state when no posts returned', async () => {
    mockListPosts.mockResolvedValue({ posts: [], next_cursor: null, has_more: false })
    const { wrapper } = await mountForum()
    expect(wrapper.find('.empty-state').exists()).toBe(true)
  })

  it('shows loading skeleton while fetch is pending', async () => {
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

  it('selects category filter and resets + refetches', async () => {
    const { wrapper } = await mountForum()
    vi.clearAllMocks()
    mockListPosts.mockResolvedValue(fakePageOneResponse)

    const catButtons = wrapper.findAll('button').filter((b) => b.text().includes('AI Research'))
    expect(catButtons.length).toBeGreaterThan(0)
    await catButtons[0].trigger('click')
    await flushPromises()
    expect(mockListPosts).toHaveBeenCalledTimes(1)
    expect(mockListPosts).toHaveBeenCalledWith(expect.objectContaining({ category_id: 'cat1' }))
  })

  it('restores search query from URL and calls searchPosts', async () => {
    mockSearchPosts.mockResolvedValue({ posts: fakePosts, next_cursor: null, has_more: false })
    await mountForum({ q: 'AI' })
    expect(mockSearchPosts).toHaveBeenCalledWith(expect.objectContaining({ keyword: 'AI' }))
  })

  it('does NOT include page in query params (infinite scroll)', async () => {
    const { router } = await mountForum()
    expect(router.currentRoute.value.query).not.toHaveProperty('page')
  })

  it('appends posts when loadMore is called (cursor-based)', async () => {
    const { wrapper } = await mountForum()
    // Initial load: 2 posts
    expect(wrapper.findAll('.post-card').length).toBe(2)

    // Simulate loadMore (next cursor page)
    mockListPosts.mockResolvedValue(fakePageTwoResponse)
    const vm = wrapper.vm as {
      loadMore: () => void
      isLoadingMore: { value: boolean }
      hasMore: { value: boolean }
    }
    vm.loadMore()
    await flushPromises()

    // Should now have 3 posts total (2 + 1 appended)
    expect(wrapper.findAll('.post-card').length).toBe(3)
    expect(wrapper.text()).toContain('Test Post 3')
  })

  it('shows "no more posts" text when has_more is false and posts exist', async () => {
    mockListPosts.mockResolvedValue({ posts: fakePosts, next_cursor: null, has_more: false })
    const { wrapper } = await mountForum()
    expect(wrapper.text()).toContain('No more posts')
  })

  it('does NOT show "no more posts" when there are no posts', async () => {
    mockListPosts.mockResolvedValue({ posts: [], next_cursor: null, has_more: false })
    const { wrapper } = await mountForum()
    expect(wrapper.text()).not.toContain('No more posts')
  })

  it('shows loading spinner while isLoadingMore is true', async () => {
    const { wrapper } = await mountForum()

    // Start a slow loadMore
    let resolveLoad!: (v: unknown) => void
    const slowPromise = new Promise((res) => {
      resolveLoad = res
    })
    mockListPosts.mockReturnValue(slowPromise)

    const vm = wrapper.vm as {
      loadMore: () => void
    }
    vm.loadMore()
    await nextTick()

    // Spinner should be visible
    expect(wrapper.find('svg.animate-spin').exists()).toBe(true)

    // Resolve the load
    resolveLoad({ posts: [], next_cursor: null, has_more: false })
    await flushPromises()
    expect(wrapper.find('svg.animate-spin').exists()).toBe(false)
  })

  it('loadMore guard: does not call API when isLoadingMore is true', async () => {
    const { wrapper } = await mountForum()
    vi.clearAllMocks()

    // Force a loading state with a never-resolving promise
    mockListPosts.mockReturnValue(new Promise(() => {}))
    const vm = wrapper.vm as {
      loadMore: () => void
      isLoadingMore: { value: boolean }
    }

    // First call sets isLoadingMore = true
    vm.loadMore()
    await nextTick()

    // Second call should be guarded
    vm.loadMore()
    await nextTick()

    // API should have been called only once
    expect(mockListPosts).toHaveBeenCalledTimes(1)
  })

  it('loadMore guard: does not call API when hasMore is false', async () => {
    mockListPosts.mockResolvedValue({ posts: fakePosts, next_cursor: null, has_more: false })
    const { wrapper } = await mountForum()
    vi.clearAllMocks()

    const vm = wrapper.vm as { loadMore: () => void }
    vm.loadMore()
    await flushPromises()

    expect(mockListPosts).not.toHaveBeenCalled()
  })

  it('filter change resets posts list to fresh data', async () => {
    const { wrapper } = await mountForum()
    // Initial: 2 posts
    expect(wrapper.findAll('.post-card').length).toBe(2)

    // Change sort — should reset posts and fetch fresh
    const freshResponse = {
      posts: [fakePosts[0]],
      next_cursor: null,
      has_more: false,
    }
    mockListPosts.mockResolvedValue(freshResponse)

    const vm = wrapper.vm as { sortBy: string }
    vm.sortBy = 'oldest'
    await flushPromises()

    // After reset + fresh fetch, posts replaced (not appended)
    expect(wrapper.findAll('.post-card').length).toBe(1)
  })

  it('sort param is included in search API call', async () => {
    mockSearchPosts.mockResolvedValue({ posts: fakePosts, next_cursor: null, has_more: false })
    const { wrapper } = await mountForum({ q: 'AI' })
    vi.clearAllMocks()
    mockSearchPosts.mockResolvedValue({ posts: [], next_cursor: null, has_more: false })

    const vm = wrapper.vm as { sortBy: string }
    vm.sortBy = 'oldest'
    await flushPromises()

    expect(mockSearchPosts).toHaveBeenCalledWith(expect.objectContaining({ sort: 'oldest' }))
  })

  it('changing sort in search mode calls searchPosts not listPosts', async () => {
    mockSearchPosts.mockResolvedValue({ posts: fakePosts, next_cursor: null, has_more: false })
    const { wrapper } = await mountForum({ q: 'AI' })
    vi.clearAllMocks()
    mockSearchPosts.mockResolvedValue({ posts: [], next_cursor: null, has_more: false })

    const vm = wrapper.vm as { sortBy: string }
    vm.sortBy = 'most_comments'
    await flushPromises()

    expect(mockSearchPosts).toHaveBeenCalled()
    expect(mockListPosts).not.toHaveBeenCalled()
  })

  it('IntersectionObserver is observed on the sentinel element', async () => {
    await mountForum()
    expect(mockIOObserve).toHaveBeenCalledTimes(1)
  })

  it('BasePagination is not rendered (removed)', async () => {
    const { wrapper } = await mountForum()
    expect(wrapper.find('.base-pagination').exists()).toBe(false)
  })

  it('listPosts is called without page param on initial load', async () => {
    await mountForum()
    const callArgs = mockListPosts.mock.calls[0][0] as Record<string, unknown>
    expect(callArgs).not.toHaveProperty('page')
  })

  it('listPosts is called with cursor on loadMore', async () => {
    const { wrapper } = await mountForum()
    vi.clearAllMocks()
    mockListPosts.mockResolvedValue(fakePageTwoResponse)

    const vm = wrapper.vm as { loadMore: () => void }
    vm.loadMore()
    await flushPromises()

    expect(mockListPosts).toHaveBeenCalledWith(expect.objectContaining({ cursor: 'cursor-abc' }))
  })

  it('isLoadingMore is reset to false after fetchMorePosts error', async () => {
    const { wrapper } = await mountForum()
    // Initial load has nextCursor set
    vi.clearAllMocks()
    mockListPosts.mockRejectedValue(new Error('Network error'))

    const vm = wrapper.vm as {
      loadMore: () => void
      isLoadingMore: boolean
    }
    vm.loadMore()
    await flushPromises()

    // isLoadingMore must be false after the error (finally block)
    expect(vm.isLoadingMore).toBe(false)
  })

  it('isLoadingMore is reset to false after fetchMoreSearchResults error', async () => {
    mockSearchPosts.mockResolvedValue({
      posts: fakePosts,
      next_cursor: 'cursor-s1',
      has_more: true,
    })
    const { wrapper } = await mountForum({ q: 'AI' })
    vi.clearAllMocks()
    mockSearchPosts.mockRejectedValue(new Error('Search error'))

    const vm = wrapper.vm as {
      loadMore: () => void
      isLoadingMore: boolean
    }
    vm.loadMore()
    await flushPromises()

    expect(vm.isLoadingMore).toBe(false)
  })

  it('loadMore is blocked while initial fetch (loading) is in progress', async () => {
    // Mount with a never-resolving initial fetch
    let resolveInitial!: (v: unknown) => void
    mockListPosts.mockReturnValue(
      new Promise((res) => {
        resolveInitial = res
      }),
    )
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
    await nextTick()

    const vm = wrapper.vm as { loadMore: () => void }
    const callsBefore = mockListPosts.mock.calls.length

    // loadMore during initial load should be blocked
    vm.loadMore()
    await nextTick()

    // No extra API call should have been made
    expect(mockListPosts.mock.calls.length).toBe(callsBefore)

    // Clean up
    resolveInitial({ posts: [], next_cursor: null, has_more: false })
    await flushPromises()
    wrapper.unmount()
  })

  it('cursor is reset to null before filter-change fetch', async () => {
    const { wrapper } = await mountForum()
    // After initial load, nextCursor should be 'cursor-abc'
    const vmBefore = wrapper.vm as { nextCursor: string | null }
    expect(vmBefore.nextCursor).toBe('cursor-abc')

    // Set up new fetch that returns no more pages
    mockListPosts.mockResolvedValue({ posts: [fakePosts[0]], next_cursor: null, has_more: false })

    const vm = wrapper.vm as { sortBy: string; nextCursor: string | null }
    vm.sortBy = 'oldest'
    // After the watch triggers resetScrollState, cursor should be null
    await nextTick()
    expect(vm.nextCursor).toBeNull()

    await flushPromises()
    // After fresh fetch, cursor is still null (no more pages)
    expect(vm.nextCursor).toBeNull()
  })

  it('clearSearch resets isSearching before fetching', async () => {
    mockSearchPosts.mockResolvedValue({ posts: fakePosts, next_cursor: null, has_more: false })
    const { wrapper } = await mountForum({ q: 'AI' })
    // After mount, isSearching should be true
    const vm = wrapper.vm as {
      clearSearch: () => void
      isSearching: boolean
      loadMore: () => void
    }
    expect(vm.isSearching).toBe(true)

    vi.clearAllMocks()
    mockListPosts.mockReturnValue(new Promise(() => {}))

    vm.clearSearch()
    await nextTick()

    // isSearching must be false immediately so loadMore uses the posts branch
    expect(vm.isSearching).toBe(false)

    // loadMore during this pending fetch should not call searchPosts
    vm.loadMore()
    await nextTick()
    expect(mockSearchPosts).not.toHaveBeenCalled()
  })

  describe('3-column layout', () => {
    it('renders the left sidebar component', async () => {
      const { wrapper } = await mountForum()
      expect(wrapper.find('.forum-left-sidebar').exists()).toBe(true)
    })

    it('left sidebar is hidden below xl breakpoint (has hidden xl:block classes)', async () => {
      const { wrapper } = await mountForum()
      // The aside wrapping the left sidebar should have responsive hiding classes
      const asides = wrapper.findAll('aside')
      const leftSidebar = asides.find((a) => a.find('.forum-left-sidebar').exists())
      expect(leftSidebar).toBeTruthy()
      expect(leftSidebar!.classes()).toContain('hidden')
      expect(leftSidebar!.classes()).toContain('xl:block')
    })

    it('right sidebar is hidden below lg breakpoint (has hidden lg:block classes)', async () => {
      const { wrapper } = await mountForum()
      const asides = wrapper.findAll('aside')
      // Right sidebar has categories/trending, not the ForumLeftSidebar
      const rightSidebar = asides.find((a) => !a.find('.forum-left-sidebar').exists())
      expect(rightSidebar).toBeTruthy()
      expect(rightSidebar!.classes()).toContain('hidden')
      expect(rightSidebar!.classes()).toContain('lg:block')
    })

    it('uses self-managed padding (fullWidth mode)', async () => {
      const { wrapper } = await mountForum()
      // The root div should have its own px padding classes
      const root = wrapper.find('div')
      expect(root.classes()).toContain('px-4')
    })
  })
})

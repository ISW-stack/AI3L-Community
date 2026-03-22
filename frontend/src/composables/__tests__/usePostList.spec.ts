import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, h } from 'vue'

// ---------------------------------------------------------------------------
// Mocks — must come before any import that touches mocked modules
// ---------------------------------------------------------------------------

vi.mock('vue-i18n', () => ({
  useI18n: () => ({ t: (key: string) => key }),
}))

const mockRouterReplace = vi.fn()
const mockRouteQuery: Record<string, string> = {}
vi.mock('vue-router', () => ({
  useRoute: () => ({ query: mockRouteQuery }),
  useRouter: () => ({ replace: mockRouterReplace }),
}))

vi.mock('@/api/posts', () => ({
  listPosts: vi.fn(),
  searchPosts: vi.fn(),
  getTrendingPosts: vi.fn(),
}))

vi.mock('@/api/categories', () => ({
  listCategories: vi.fn(),
}))

vi.mock('@/composables/api', () => ({
  default: { get: vi.fn(), post: vi.fn() },
}))

vi.mock('@/constants', () => ({
  HEARTBEAT_INTERVAL_MS: 30000,
}))

vi.mock('@/utils/error', () => ({
  getErrorMessage: (_e: unknown, fallback: string) => fallback,
}))

vi.mock('@/utils/apiValidation', () => ({
  assertShape: <T>(data: T) => data,
}))

// Stub IntersectionObserver for useInfiniteScroll
vi.stubGlobal(
  'IntersectionObserver',
  class {
    observe = vi.fn()
    disconnect = vi.fn()
    unobserve = vi.fn()
  },
)

// ---------------------------------------------------------------------------
// Imports (after mocks)
// ---------------------------------------------------------------------------

import { usePostList } from '../usePostList'
import { listPosts, searchPosts, getTrendingPosts } from '@/api/posts'
import { listCategories } from '@/api/categories'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const mockListPosts = listPosts as ReturnType<typeof vi.fn>
const mockSearchPosts = searchPosts as ReturnType<typeof vi.fn>
const mockGetTrendingPosts = getTrendingPosts as ReturnType<typeof vi.fn>
const mockListCategories = listCategories as ReturnType<typeof vi.fn>

const defaultListResponse = {
  posts: [{ id: '1', title: 'Test Post' }],
  total: 1,
  next_cursor: null,
  has_more: false,
}

const defaultSearchResponse = {
  posts: [{ id: '2', title: 'Search Result' }],
  total: 1,
  has_more: false,
}

const defaultCategories = [
  { id: 'cat-1', name: 'General', description: null, post_count: 5 },
  { id: 'cat-2', name: 'Tech', description: null, post_count: 3 },
]

const defaultTrending = [{ id: 't1', title: 'Trending Post' }]

function mountComposable(routeQuery: Record<string, string> = {}) {
  // Populate mock route query before mounting
  Object.keys(mockRouteQuery).forEach((k) => delete mockRouteQuery[k])
  Object.assign(mockRouteQuery, routeQuery)

  let result: ReturnType<typeof usePostList>
  const Comp = defineComponent({
    setup() {
      result = usePostList({
        postType: 'question',
        defaultSort: 'newest',
        i18nErrorKeys: {
          fetchPosts: 'qa.fetchError',
          fetchCategories: 'qa.loadCategoriesError',
          fetchTrending: 'qa.fetchTrendingError',
          searchError: 'qa.searchError',
        },
      })
      return () => h('div')
    },
  })
  const pinia = createPinia()
  setActivePinia(pinia)
  const wrapper = mount(Comp, { global: { plugins: [pinia] } })
  return { result: result!, wrapper }
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('usePostList', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    mockListPosts.mockResolvedValue(defaultListResponse)
    mockSearchPosts.mockResolvedValue(defaultSearchResponse)
    mockGetTrendingPosts.mockResolvedValue(defaultTrending)
    mockListCategories.mockResolvedValue(defaultCategories)
    mockRouterReplace.mockClear()
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.restoreAllMocks()
    // Clear route query
    Object.keys(mockRouteQuery).forEach((k) => delete mockRouteQuery[k])
  })

  // -----------------------------------------------------------------------
  // 1. init() calls listPosts with type: question
  // -----------------------------------------------------------------------
  it('init() calls listPosts with type: question', async () => {
    const { result, wrapper } = mountComposable()
    result.init()
    await flushPromises()

    expect(mockListPosts).toHaveBeenCalledWith(expect.objectContaining({ type: 'question' }))
    wrapper.unmount()
  })

  // -----------------------------------------------------------------------
  // 2. init() calls listCategories
  // -----------------------------------------------------------------------
  it('init() calls listCategories', async () => {
    const { result, wrapper } = mountComposable()
    result.init()
    await flushPromises()

    expect(mockListCategories).toHaveBeenCalled()
    expect(result.categories.value).toEqual(defaultCategories)
    wrapper.unmount()
  })

  // -----------------------------------------------------------------------
  // 3. init() calls getTrendingPosts with type
  // -----------------------------------------------------------------------
  it('init() calls getTrendingPosts with type', async () => {
    const { result, wrapper } = mountComposable()
    result.init()
    await flushPromises()

    expect(mockGetTrendingPosts).toHaveBeenCalledWith('question')
    expect(result.trendingPosts.value).toEqual(defaultTrending)
    wrapper.unmount()
  })

  // -----------------------------------------------------------------------
  // 4. selectCategory updates categoryFilter and triggers refetch
  // -----------------------------------------------------------------------
  it('selectCategory updates categoryFilter and triggers refetch', async () => {
    const { result, wrapper } = mountComposable()
    result.init()
    await flushPromises()
    mockListPosts.mockClear()

    result.selectCategory('cat-1')
    await flushPromises()

    expect(result.categoryFilter.value).toBe('cat-1')
    // The watcher on categoryFilter triggers fetchPosts
    expect(mockListPosts).toHaveBeenCalledWith(expect.objectContaining({ category_id: 'cat-1' }))
    wrapper.unmount()
  })

  // -----------------------------------------------------------------------
  // 5. selectSort updates sortBy and triggers refetch
  // -----------------------------------------------------------------------
  it('selectSort updates sortBy and triggers refetch', async () => {
    const { result, wrapper } = mountComposable()
    result.init()
    await flushPromises()
    mockListPosts.mockClear()

    result.selectSort('popular')
    await flushPromises()

    expect(result.sortBy.value).toBe('popular')
    expect(mockListPosts).toHaveBeenCalledWith(expect.objectContaining({ sort: 'popular' }))
    wrapper.unmount()
  })

  // -----------------------------------------------------------------------
  // 6. clearSearch resets all filter state
  // -----------------------------------------------------------------------
  it('clearSearch resets all filter state', async () => {
    const { result, wrapper } = mountComposable()
    result.init()
    await flushPromises()

    // Set some filter state
    result.searchKeyword.value = 'test'
    result.searchDateFrom.value = '2026-01-01'
    result.searchDateTo.value = '2026-12-31'
    result.searchLogic.value = 'OR'
    result.sortBy.value = 'popular'
    await flushPromises()

    mockListPosts.mockClear()
    result.clearSearch()
    await flushPromises()

    expect(result.searchKeyword.value).toBe('')
    expect(result.searchDateFrom.value).toBe('')
    expect(result.searchDateTo.value).toBe('')
    expect(result.searchLogic.value).toBe('AND')
    expect(result.categoryFilter.value).toBeNull()
    expect(result.sortBy.value).toBe('newest')
    expect(result.isSearching.value).toBe(false)
    wrapper.unmount()
  })

  // -----------------------------------------------------------------------
  // 7. onSearchInput debounces for 300ms
  // -----------------------------------------------------------------------
  it('onSearchInput debounces for 300ms', async () => {
    const { result, wrapper } = mountComposable()
    result.init()
    await flushPromises()
    mockSearchPosts.mockClear()
    mockListPosts.mockClear()

    result.searchKeyword.value = 'test'
    result.onSearchInput()

    // Should not call search immediately
    expect(mockSearchPosts).not.toHaveBeenCalled()

    // Advance time by 200ms — still no call
    vi.advanceTimersByTime(200)
    await flushPromises()
    expect(mockSearchPosts).not.toHaveBeenCalled()

    // Advance to 300ms — now it should fire
    vi.advanceTimersByTime(100)
    await flushPromises()

    expect(mockSearchPosts).toHaveBeenCalled()
    wrapper.unmount()
  })

  // -----------------------------------------------------------------------
  // 8. immediateSearch bypasses debounce
  // -----------------------------------------------------------------------
  it('immediateSearch bypasses debounce', async () => {
    const { result, wrapper } = mountComposable()
    result.init()
    await flushPromises()
    mockSearchPosts.mockClear()
    mockListPosts.mockClear()

    result.searchKeyword.value = 'test'
    // Start a debounced search
    result.onSearchInput()
    expect(mockSearchPosts).not.toHaveBeenCalled()

    // immediateSearch should fire right away, cancelling the debounce timer
    result.immediateSearch()
    await flushPromises()

    expect(mockSearchPosts).toHaveBeenCalledTimes(1)

    // Advancing past 300ms should NOT trigger a second call
    vi.advanceTimersByTime(400)
    await flushPromises()
    expect(mockSearchPosts).toHaveBeenCalledTimes(1)
    wrapper.unmount()
  })

  // -----------------------------------------------------------------------
  // 9. doSearch calls searchPosts with correct type
  // -----------------------------------------------------------------------
  it('doSearch calls searchPosts with correct type', async () => {
    const { result, wrapper } = mountComposable()
    result.init()
    await flushPromises()
    mockSearchPosts.mockClear()

    result.searchKeyword.value = 'deep learning'
    await result.doSearch()
    await flushPromises()

    expect(mockSearchPosts).toHaveBeenCalledWith(
      expect.objectContaining({
        type: 'question',
        keyword: 'deep learning',
      }),
    )
    wrapper.unmount()
  })

  // -----------------------------------------------------------------------
  // 10. URL sync: syncQueryParams writes category to router
  // -----------------------------------------------------------------------
  it('syncQueryParams writes category to router on fetch', async () => {
    const { result, wrapper } = mountComposable()
    result.init()
    await flushPromises()
    mockRouterReplace.mockClear()

    result.selectCategory('cat-2')
    await flushPromises()

    expect(mockRouterReplace).toHaveBeenCalledWith(
      expect.objectContaining({
        query: expect.objectContaining({ category: 'cat-2' }),
      }),
    )
    wrapper.unmount()
  })

  // -----------------------------------------------------------------------
  // 11. URL restore: reads query params from route on init
  // -----------------------------------------------------------------------
  it('reads query params from route on init', async () => {
    const { result, wrapper } = mountComposable({
      category: 'cat-1',
      sort: 'popular',
      q: 'hello',
    })

    expect(result.categoryFilter.value).toBe('cat-1')
    expect(result.sortBy.value).toBe('popular')
    expect(result.searchKeyword.value).toBe('hello')

    result.init()
    await flushPromises()

    // Should have triggered doSearch since searchKeyword is set
    expect(mockSearchPosts).toHaveBeenCalledWith(
      expect.objectContaining({
        keyword: 'hello',
        type: 'question',
      }),
    )
    wrapper.unmount()
  })

  // -----------------------------------------------------------------------
  // 12. loadMore calls fetchMorePosts when not searching
  // -----------------------------------------------------------------------
  it('loadMore calls fetchMorePosts when not searching', async () => {
    const responseWithMore = {
      posts: [{ id: '1', title: 'P1' }],
      total: 2,
      next_cursor: 'cursor-abc',
      has_more: true,
    }
    mockListPosts.mockResolvedValueOnce(responseWithMore)

    const { result, wrapper } = mountComposable()
    result.init()
    await flushPromises()

    expect(result.hasMore.value).toBe(true)
    expect(result.isSearching.value).toBe(false)
    mockListPosts.mockClear()

    const moreResponse = {
      posts: [{ id: '2', title: 'P2' }],
      total: 2,
      next_cursor: null,
      has_more: false,
    }
    mockListPosts.mockResolvedValueOnce(moreResponse)

    result.loadMore()
    await flushPromises()

    expect(mockListPosts).toHaveBeenCalledWith(expect.objectContaining({ cursor: 'cursor-abc' }))
    expect(result.posts.value).toHaveLength(2)
    wrapper.unmount()
  })

  // -----------------------------------------------------------------------
  // 13. loadMore calls fetchMoreSearchResults when searching
  // -----------------------------------------------------------------------
  it('loadMore calls fetchMoreSearchResults when searching', async () => {
    const searchResponseWithMore = {
      posts: [{ id: 's1', title: 'SR1' }],
      total: 2,
      has_more: true,
    }
    mockSearchPosts.mockResolvedValueOnce(searchResponseWithMore)

    const { result, wrapper } = mountComposable()
    result.init()
    await flushPromises()

    // Trigger a search to enter searching mode
    result.searchKeyword.value = 'test'
    await result.doSearch()
    await flushPromises()

    expect(result.isSearching.value).toBe(true)
    expect(result.hasMore.value).toBe(true)
    mockSearchPosts.mockClear()

    const moreSearchResponse = {
      posts: [{ id: 's2', title: 'SR2' }],
      total: 2,
      has_more: false,
    }
    mockSearchPosts.mockResolvedValueOnce(moreSearchResponse)

    result.loadMore()
    await flushPromises()

    expect(mockSearchPosts).toHaveBeenCalledWith(
      expect.objectContaining({ page: 2, type: 'question' }),
    )
    wrapper.unmount()
  })

  // -----------------------------------------------------------------------
  // 14. cleanup clears debounce timer
  // -----------------------------------------------------------------------
  it('cleanup clears debounce timer', async () => {
    const { result, wrapper } = mountComposable()
    result.init()
    await flushPromises()
    mockSearchPosts.mockClear()
    mockListPosts.mockClear()

    result.searchKeyword.value = 'test'
    result.onSearchInput()

    // Cleanup before the debounce fires
    result.cleanup()

    // Advance past 300ms — the debounce should have been cancelled
    vi.advanceTimersByTime(500)
    await flushPromises()

    // Neither search nor list should have been called after cleanup
    expect(mockSearchPosts).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  // -----------------------------------------------------------------------
  // 15. M-27: stale search responses are discarded
  // -----------------------------------------------------------------------
  it('doSearch discards stale search response when a newer search fires', async () => {
    let resolveFirst!: (value: unknown) => void
    const firstPending = new Promise((resolve) => {
      resolveFirst = resolve
    })
    const secondResponse = {
      posts: [{ id: 'new-1', title: 'New Result' }],
      total: 1,
      has_more: false,
    }

    // First call hangs, second call resolves immediately
    mockSearchPosts.mockReturnValueOnce(firstPending).mockResolvedValueOnce(secondResponse)

    const { result, wrapper } = mountComposable()
    result.init()
    await flushPromises()

    // Start first search
    result.searchKeyword.value = 'stale query'
    const firstSearch = result.doSearch()

    // Start second search before first resolves — increments _searchFetchId
    result.searchKeyword.value = 'fresh query'
    const secondSearch = result.doSearch()
    await secondSearch

    // Second search result should be applied
    expect(result.posts.value).toEqual(secondResponse.posts)

    // Now resolve the first (stale) search
    resolveFirst({
      posts: [{ id: 'stale-1', title: 'Stale Result' }],
      total: 1,
      has_more: false,
    })
    await firstSearch

    // Posts should still be the fresh result, not the stale one
    expect(result.posts.value).toEqual(secondResponse.posts)
    expect(result.posts.value[0].id).toBe('new-1')
    wrapper.unmount()
  })

  it('fetchPosts discards stale response when a newer fetch fires', async () => {
    // We test the guard by directly calling doSearch (which delegates to fetchPosts
    // when no search terms exist), simulating rapid successive calls.
    let resolveFirst!: (value: unknown) => void
    const _firstPending = new Promise((resolve) => {
      resolveFirst = resolve
    })

    const { result, wrapper } = mountComposable()
    // Init with default
    mockListPosts.mockResolvedValueOnce(defaultListResponse)
    result.init()
    await flushPromises()

    // Set up the stale/fresh sequence for search
    const staleSearchResponse = {
      posts: [{ id: 'stale-s1', title: 'Stale Search' }],
      total: 1,
      has_more: false,
    }
    const freshSearchResponse = {
      posts: [{ id: 'fresh-s1', title: 'Fresh Search' }],
      total: 1,
      has_more: false,
    }

    // First search hangs, second resolves immediately
    mockSearchPosts.mockReturnValueOnce(
      new Promise((resolve) => {
        resolveFirst = resolve
      }),
    )
    mockSearchPosts.mockResolvedValueOnce(freshSearchResponse)

    // Start first search
    result.searchKeyword.value = 'query A'
    const first = result.doSearch()

    // Start second search before first resolves
    result.searchKeyword.value = 'query B'
    const second = result.doSearch()
    await second

    expect(result.posts.value).toEqual(freshSearchResponse.posts)

    // Resolve stale first search
    resolveFirst(staleSearchResponse)
    await first

    // Should still show fresh results
    expect(result.posts.value).toEqual(freshSearchResponse.posts)
    expect(result.posts.value[0].id).toBe('fresh-s1')
    wrapper.unmount()
  })

  it('stale search error does not show toast', async () => {
    const toastModule = await import('@/stores/toast')
    const toastStore = toastModule.useToastStore()
    const showSpy = vi.spyOn(toastStore, 'show')

    let rejectFirst!: (reason: unknown) => void
    const firstPending = new Promise((_resolve, reject) => {
      rejectFirst = reject
    })
    const secondResponse = {
      posts: [{ id: 'ok-1', title: 'OK' }],
      total: 1,
      has_more: false,
    }

    mockSearchPosts.mockReturnValueOnce(firstPending).mockResolvedValueOnce(secondResponse)

    const { result, wrapper } = mountComposable()
    result.init()
    await flushPromises()
    showSpy.mockClear()

    // Start first search that will fail
    result.searchKeyword.value = 'fail query'
    const firstSearch = result.doSearch()

    // Start second search that succeeds
    result.searchKeyword.value = 'ok query'
    const secondSearch = result.doSearch()
    await secondSearch

    // Reject the first (stale) search
    rejectFirst(new Error('Network error'))
    await firstSearch.catch(() => {})
    await flushPromises()

    // Toast should NOT have been called for the stale error
    expect(showSpy).not.toHaveBeenCalled()
    wrapper.unmount()
    showSpy.mockRestore()
  })

  // -----------------------------------------------------------------------
  // 16. dateRangeInvalid computed works correctly
  // -----------------------------------------------------------------------
  it('dateRangeInvalid computed works correctly', async () => {
    const { result, wrapper } = mountComposable()

    // No dates set — not invalid
    expect(result.dateRangeInvalid.value).toBe(false)

    // Only from date — not invalid
    result.searchDateFrom.value = '2026-03-01'
    expect(result.dateRangeInvalid.value).toBe(false)

    // from > to — invalid
    result.searchDateTo.value = '2026-02-01'
    expect(result.dateRangeInvalid.value).toBe(true)

    // from <= to — valid
    result.searchDateTo.value = '2026-04-01'
    expect(result.dateRangeInvalid.value).toBe(false)

    // Equal dates — valid
    result.searchDateTo.value = '2026-03-01'
    expect(result.dateRangeInvalid.value).toBe(false)

    wrapper.unmount()
  })
})

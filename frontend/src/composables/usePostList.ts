import { ref, computed, watch, type Ref, type ComputedRef } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import type { Post, Category } from '@/types'
import { listPosts, searchPosts, getTrendingPosts } from '@/api/posts'
import { listCategories } from '@/api/categories'
import { getErrorMessage } from '@/utils/error'
import { useToastStore } from '@/stores/toast'
import { useInfiniteScroll } from '@/composables/useInfiniteScroll'

const MAX_ACCUMULATED_POSTS = 200

export interface UsePostListOptions {
  postType: 'post' | 'question'
  defaultSort: string
  pageSize?: number
  i18nErrorKeys: {
    fetchPosts: string
    fetchCategories: string
    fetchTrending: string
    searchError: string
  }
}

export interface UsePostListReturn {
  posts: Ref<Post[]>
  categories: Ref<Category[]>
  trendingPosts: Ref<Post[]>
  loading: Ref<boolean>
  isLoadingMore: Ref<boolean>
  hasMore: Ref<boolean>
  isSearching: Ref<boolean>
  isSearchLoading: Ref<boolean>
  showAdvanced: Ref<boolean>
  categoryFilter: Ref<string | null>
  searchKeyword: Ref<string>
  searchDateFrom: Ref<string>
  searchDateTo: Ref<string>
  searchLogic: Ref<string>
  sortBy: Ref<string>
  dateRangeInvalid: ComputedRef<boolean>
  activeCategoryName: ComputedRef<string | null>
  sentinelRef: Ref<HTMLElement | null>
  selectCategory: (catId: string | null) => void
  selectSort: (sort: string) => void
  onSearchInput: () => void
  immediateSearch: () => void
  doSearch: (opts?: { resetBeforeSearch?: boolean }) => Promise<void>
  clearSearch: () => void
  toggleAdvanced: () => void
  loadMore: () => void
  init: () => void
  cleanup: () => void
}

export function usePostList(options: UsePostListOptions): UsePostListReturn {
  const { postType, defaultSort, pageSize = 20, i18nErrorKeys } = options

  const { t } = useI18n()
  const toast = useToastStore()
  const route = useRoute()
  const router = useRouter()

  // Accumulated posts list (infinite scroll appends here)
  const posts = ref<Post[]>([])
  const categories = ref<Category[]>([])
  const trendingPosts = ref<Post[]>([])

  // Cursor pagination state
  const nextCursor = ref<string | null>(null)
  const hasMore = ref(true)

  // Loading states
  const loading = ref(false)
  const isLoadingMore = ref(false)

  // Filters (restored from URL query params)
  const categoryFilter = ref<string | null>((route.query.category as string) || null)
  const searchKeyword = ref((route.query.q as string) || '')
  const searchDateFrom = ref((route.query.from as string) || '')
  const searchDateTo = ref((route.query.to as string) || '')
  const searchLogic = ref((route.query.logic as string) || 'AND')
  const sortBy = ref((route.query.sort as string) || defaultSort)
  const isSearching = ref(false)
  const isSearchLoading = ref(false)
  const showAdvanced = ref(false)
  const searchPage = ref(1)

  // Debounce timer for search-as-you-type
  let searchDebounceTimer: ReturnType<typeof setTimeout> | null = null

  // Stale-response guard counters
  let _searchFetchId = 0
  let _fetchPostsId = 0

  // Sentinel element for IntersectionObserver
  const sentinelRef = ref<HTMLElement | null>(null)

  const dateRangeInvalid = computed(
    () =>
      !!searchDateFrom.value && !!searchDateTo.value && searchDateFrom.value > searchDateTo.value,
  )

  const activeCategoryName = computed(() => {
    if (!categoryFilter.value) return null
    const cat = categories.value.find((c) => c.id === categoryFilter.value)
    return cat ? cat.name : null
  })

  async function fetchCategories() {
    try {
      categories.value = await listCategories()
    } catch (e: unknown) {
      toast.show(getErrorMessage(e, t(i18nErrorKeys.fetchCategories)), 'error')
    }
  }

  async function fetchTrending() {
    try {
      trendingPosts.value = await getTrendingPosts(postType)
    } catch (e: unknown) {
      toast.show(getErrorMessage(e, t(i18nErrorKeys.fetchTrending)), 'error')
    }
  }

  function syncQueryParams() {
    const query: Record<string, string> = {}
    if (categoryFilter.value) query.category = categoryFilter.value
    if (searchKeyword.value) query.q = searchKeyword.value
    if (searchDateFrom.value) query.from = searchDateFrom.value
    if (searchDateTo.value) query.to = searchDateTo.value
    if (searchLogic.value !== 'AND') query.logic = searchLogic.value
    if (sortBy.value !== defaultSort) query.sort = sortBy.value
    router.replace({ query })
  }

  function resetScrollState() {
    posts.value = []
    nextCursor.value = null
    hasMore.value = true
  }

  // Initial fetch or filter-reset fetch (no cursor, replaces posts)
  async function fetchPosts() {
    const fetchId = ++_fetchPostsId
    loading.value = true
    try {
      const params: {
        cursor?: string
        page_size?: number
        category_id?: string
        sort?: string
        type?: 'post' | 'question'
      } = {
        page_size: pageSize,
        sort: sortBy.value,
        type: postType,
      }
      if (categoryFilter.value) params.category_id = categoryFilter.value
      const data = await listPosts(params)
      if (fetchId !== _fetchPostsId) return // stale response
      posts.value = data.posts
      nextCursor.value = data.next_cursor ?? null
      hasMore.value = data.has_more ?? false
      isSearching.value = false
      syncQueryParams()
    } catch (e: unknown) {
      if (fetchId !== _fetchPostsId) return // stale response
      toast.show(getErrorMessage(e, t(i18nErrorKeys.fetchPosts)), 'error')
    } finally {
      if (fetchId === _fetchPostsId) loading.value = false
    }
  }

  // Append next page via cursor
  async function fetchMorePosts() {
    if (isLoadingMore.value || !hasMore.value || !nextCursor.value) return
    isLoadingMore.value = true
    try {
      const params: {
        cursor?: string
        page_size?: number
        category_id?: string
        sort?: string
        type?: 'post' | 'question'
      } = {
        cursor: nextCursor.value,
        page_size: pageSize,
        sort: sortBy.value,
        type: postType,
      }
      if (categoryFilter.value) params.category_id = categoryFilter.value
      const data = await listPosts(params)
      posts.value = [...posts.value, ...data.posts].slice(-MAX_ACCUMULATED_POSTS)
      nextCursor.value = data.next_cursor ?? null
      hasMore.value = data.has_more ?? false
    } catch (e: unknown) {
      toast.show(getErrorMessage(e, t(i18nErrorKeys.fetchPosts)), 'error')
    } finally {
      isLoadingMore.value = false
    }
  }

  // Initial search or filter-reset search (page-based pagination)
  async function doSearch({ resetBeforeSearch = true }: { resetBeforeSearch?: boolean } = {}) {
    const fetchId = ++_searchFetchId
    searchPage.value = 1
    if (resetBeforeSearch) resetScrollState()
    if (!searchKeyword.value && !searchDateFrom.value && !searchDateTo.value) {
      await fetchPosts()
      return
    }
    loading.value = true
    isSearching.value = true
    try {
      const body: Parameters<typeof searchPosts>[0] = {
        page: 1,
        page_size: pageSize,
        logic: searchLogic.value,
        sort: sortBy.value,
        type: postType,
      }
      if (searchKeyword.value) body.keyword = searchKeyword.value
      if (categoryFilter.value) body.category_id = categoryFilter.value
      if (searchDateFrom.value && !dateRangeInvalid.value) body.date_from = searchDateFrom.value
      if (searchDateTo.value && !dateRangeInvalid.value) body.date_to = searchDateTo.value
      const data = await searchPosts(body)
      if (fetchId !== _searchFetchId) return // stale response
      posts.value = data.posts
      nextCursor.value = null
      hasMore.value = data.has_more ?? false
      syncQueryParams()
    } catch (e: unknown) {
      if (fetchId !== _searchFetchId) return // stale response
      toast.show(getErrorMessage(e, t(i18nErrorKeys.searchError)), 'error')
    } finally {
      if (fetchId === _searchFetchId) loading.value = false
    }
  }

  // Append next page of search results via page number
  async function fetchMoreSearchResults() {
    if (isLoadingMore.value || !hasMore.value) return
    const fetchId = _searchFetchId // capture current search context
    isLoadingMore.value = true
    try {
      const nextPage = searchPage.value + 1
      const body: Parameters<typeof searchPosts>[0] = {
        page: nextPage,
        page_size: pageSize,
        logic: searchLogic.value,
        sort: sortBy.value,
        type: postType,
      }
      if (searchKeyword.value) body.keyword = searchKeyword.value
      if (categoryFilter.value) body.category_id = categoryFilter.value
      if (searchDateFrom.value && !dateRangeInvalid.value) body.date_from = searchDateFrom.value
      if (searchDateTo.value && !dateRangeInvalid.value) body.date_to = searchDateTo.value
      const data = await searchPosts(body)
      if (fetchId !== _searchFetchId) return // stale response
      posts.value = [...posts.value, ...data.posts].slice(-MAX_ACCUMULATED_POSTS)
      hasMore.value = data.has_more ?? false
      if (data.posts.length > 0) searchPage.value = nextPage
    } catch (e: unknown) {
      if (fetchId !== _searchFetchId) return // stale response
      toast.show(getErrorMessage(e, t(i18nErrorKeys.searchError)), 'error')
    } finally {
      if (fetchId === _searchFetchId) isLoadingMore.value = false
    }
  }

  // Called by IntersectionObserver when sentinel enters viewport
  function loadMore() {
    if (loading.value || isLoadingMore.value || !hasMore.value) return
    if (isSearching.value) {
      fetchMoreSearchResults()
    } else {
      fetchMorePosts()
    }
  }

  function clearSearch() {
    searchKeyword.value = ''
    searchDateFrom.value = ''
    searchDateTo.value = ''
    searchLogic.value = 'AND'
    categoryFilter.value = null
    sortBy.value = defaultSort
    isSearching.value = false
    resetScrollState()
    fetchPosts()
  }

  async function performSearch() {
    isSearchLoading.value = true
    try {
      await doSearch()
    } finally {
      isSearchLoading.value = false
    }
  }

  function immediateSearch() {
    if (searchDebounceTimer) {
      clearTimeout(searchDebounceTimer)
      searchDebounceTimer = null
    }
    isSearchLoading.value = false
    performSearch()
  }

  function onSearchInput() {
    if (searchDebounceTimer) clearTimeout(searchDebounceTimer)
    isSearchLoading.value = true
    searchDebounceTimer = setTimeout(() => {
      searchDebounceTimer = null
      performSearch()
    }, 300)
  }

  function selectCategory(catId: string | null) {
    categoryFilter.value = catId
  }

  function selectSort(sort: string) {
    sortBy.value = sort
  }

  function toggleAdvanced() {
    showAdvanced.value = !showAdvanced.value
  }

  watch(categoryFilter, () => {
    resetScrollState()
    if (!isSearching.value) {
      fetchPosts()
    } else {
      doSearch({ resetBeforeSearch: false })
    }
  })

  watch(sortBy, () => {
    resetScrollState()
    if (isSearching.value) {
      doSearch({ resetBeforeSearch: false })
    } else {
      fetchPosts()
    }
  })

  // Wire up IntersectionObserver on the sentinel element
  useInfiniteScroll(sentinelRef, loadMore)

  function init() {
    fetchCategories()
    fetchTrending()
    if (searchKeyword.value || searchDateFrom.value || searchDateTo.value) {
      doSearch()
    } else {
      fetchPosts()
    }
  }

  function cleanup() {
    if (searchDebounceTimer) {
      clearTimeout(searchDebounceTimer)
      searchDebounceTimer = null
    }
  }

  return {
    posts,
    categories,
    trendingPosts,
    loading,
    isLoadingMore,
    hasMore,
    isSearching,
    isSearchLoading,
    showAdvanced,
    categoryFilter,
    searchKeyword,
    searchDateFrom,
    searchDateTo,
    searchLogic,
    sortBy,
    dateRangeInvalid,
    activeCategoryName,
    sentinelRef,
    selectCategory,
    selectSort,
    onSearchInput,
    immediateSearch,
    doSearch,
    clearSearch,
    toggleAdvanced,
    loadMore,
    init,
    cleanup,
  }
}

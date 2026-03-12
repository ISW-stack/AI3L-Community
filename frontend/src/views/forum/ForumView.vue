<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import type { Post, Category } from '@/types'
import { listPosts, searchPosts, getTrendingPosts } from '@/api/posts'
import { listCategories } from '@/api/categories'
import { getErrorMessage } from '@/utils/error'
import { useToastStore } from '@/stores/toast'
import { useInfiniteScroll } from '@/composables/useInfiniteScroll'
import SkeletonLoader from '@/components/SkeletonLoader.vue'
import EmptyState from '@/components/EmptyState.vue'
import PostCard from '@/components/PostCard.vue'
import BaseCard from '@/components/base/BaseCard.vue'
import BaseButton from '@/components/base/BaseButton.vue'
import FloatingCreateButton from '@/components/FloatingCreateButton.vue'
import ForumLeftSidebar from '@/components/forum/ForumLeftSidebar.vue'

const PAGE_SIZE = 20

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
const sortBy = ref((route.query.sort as string) || 'newest')
const isSearching = ref(false)
const showAdvanced = ref(false)

// Sentinel element for IntersectionObserver
const sentinelRef = ref<HTMLElement | null>(null)

const dateRangeInvalid = computed(
  () => !!searchDateFrom.value && !!searchDateTo.value && searchDateFrom.value > searchDateTo.value,
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
    toast.show(getErrorMessage(e, t('forum.fetchCategoriesError')), 'error')
  }
}

async function fetchTrending() {
  try {
    trendingPosts.value = await getTrendingPosts()
  } catch (e: unknown) {
    toast.show(getErrorMessage(e, t('forum.fetchTrendingError')), 'error')
  }
}

function syncQueryParams() {
  const query: Record<string, string> = {}
  if (categoryFilter.value) query.category = categoryFilter.value
  if (searchKeyword.value) query.q = searchKeyword.value
  if (searchDateFrom.value) query.from = searchDateFrom.value
  if (searchDateTo.value) query.to = searchDateTo.value
  if (searchLogic.value !== 'AND') query.logic = searchLogic.value
  if (sortBy.value !== 'newest') query.sort = sortBy.value
  router.replace({ query })
}

function resetScrollState() {
  posts.value = []
  nextCursor.value = null
  hasMore.value = true
}

// Initial fetch or filter-reset fetch (no cursor, replaces posts)
async function fetchPosts() {
  loading.value = true
  try {
    const params: {
      cursor?: string
      page_size?: number
      category_id?: string
      sort?: string
    } = {
      page_size: PAGE_SIZE,
      sort: sortBy.value,
    }
    if (categoryFilter.value) params.category_id = categoryFilter.value
    const data = await listPosts(params)
    posts.value = data.posts
    nextCursor.value = data.next_cursor ?? null
    hasMore.value = data.has_more ?? false
    isSearching.value = false
  } catch (e: unknown) {
    toast.show(getErrorMessage(e, t('forum.fetchPostsError')), 'error')
  } finally {
    loading.value = false
  }
  syncQueryParams()
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
    } = {
      cursor: nextCursor.value,
      page_size: PAGE_SIZE,
      sort: sortBy.value,
    }
    if (categoryFilter.value) params.category_id = categoryFilter.value
    const data = await listPosts(params)
    posts.value = [...posts.value, ...data.posts]
    nextCursor.value = data.next_cursor ?? null
    hasMore.value = data.has_more ?? false
  } catch (e: unknown) {
    toast.show(getErrorMessage(e, t('forum.fetchPostsError')), 'error')
  } finally {
    isLoadingMore.value = false
  }
}

// Initial search or filter-reset search (no cursor, replaces posts)
async function doSearch({ resetBeforeSearch = true }: { resetBeforeSearch?: boolean } = {}) {
  if (resetBeforeSearch) resetScrollState()
  if (
    !searchKeyword.value &&
    !categoryFilter.value &&
    !searchDateFrom.value &&
    !searchDateTo.value
  ) {
    await fetchPosts()
    return
  }
  loading.value = true
  isSearching.value = true
  try {
    const body: Parameters<typeof searchPosts>[0] = {
      page_size: PAGE_SIZE,
      logic: searchLogic.value,
      sort: sortBy.value,
    }
    if (searchKeyword.value) body.keyword = searchKeyword.value
    if (categoryFilter.value) body.category_id = categoryFilter.value
    if (searchDateFrom.value) body.date_from = searchDateFrom.value
    if (searchDateTo.value) body.date_to = searchDateTo.value
    const data = await searchPosts(body)
    posts.value = data.posts
    nextCursor.value = data.next_cursor ?? null
    hasMore.value = data.has_more ?? false
  } catch (e: unknown) {
    toast.show(getErrorMessage(e, t('forum.searchError')), 'error')
  } finally {
    loading.value = false
  }
  syncQueryParams()
}

// Append next page of search results via cursor
async function fetchMoreSearchResults() {
  if (isLoadingMore.value || !hasMore.value || !nextCursor.value) return
  isLoadingMore.value = true
  try {
    const body: Parameters<typeof searchPosts>[0] = {
      cursor: nextCursor.value,
      page_size: PAGE_SIZE,
      logic: searchLogic.value,
      sort: sortBy.value,
    }
    if (searchKeyword.value) body.keyword = searchKeyword.value
    if (categoryFilter.value) body.category_id = categoryFilter.value
    if (searchDateFrom.value) body.date_from = searchDateFrom.value
    if (searchDateTo.value) body.date_to = searchDateTo.value
    const data = await searchPosts(body)
    posts.value = [...posts.value, ...data.posts]
    nextCursor.value = data.next_cursor ?? null
    hasMore.value = data.has_more ?? false
  } catch (e: unknown) {
    toast.show(getErrorMessage(e, t('forum.searchError')), 'error')
  } finally {
    isLoadingMore.value = false
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
  categoryFilter.value = null
  sortBy.value = 'newest'
  isSearching.value = false
  resetScrollState()
  fetchPosts()
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

onMounted(() => {
  fetchCategories()
  fetchTrending()
  if (searchKeyword.value || searchDateFrom.value || searchDateTo.value) {
    doSearch()
  } else {
    fetchPosts()
  }
})
</script>

<template>
  <div class="w-full px-4 sm:px-6 lg:px-8 py-6 sm:py-8">
    <div class="max-w-[1340px] mx-auto">
      <div class="flex justify-between items-center mb-6">
        <h1 class="text-2xl font-bold text-foreground">{{ t('forum.title') }}</h1>
      </div>

      <!-- Mobile Category Pills -->
      <div class="lg:hidden mb-4 overflow-x-auto">
        <div class="flex gap-2 pb-2">
          <button
            class="shrink-0 px-3 py-1.5 rounded-full text-sm font-medium transition"
            :class="
              !categoryFilter
                ? 'bg-brand-600 text-white'
                : 'bg-surface-alt text-muted hover:bg-surface-alt'
            "
            @click="selectCategory(null)"
          >
            {{ t('common.all') }}
          </button>
          <button
            v-for="cat in categories"
            :key="cat.id"
            class="shrink-0 px-3 py-1.5 rounded-full text-sm font-medium transition"
            :class="
              categoryFilter === cat.id
                ? 'bg-brand-600 text-white'
                : 'bg-surface-alt text-muted hover:bg-surface-alt'
            "
            @click="selectCategory(cat.id)"
          >
            {{ cat.name }} ({{ cat.post_count }})
          </button>
        </div>
      </div>

      <!-- 3-column layout -->
      <div class="flex gap-6 justify-center">
        <!-- Left Sidebar (xl+) -->
        <aside class="hidden xl:block w-[240px] 2xl:w-[280px] shrink-0">
          <div class="sticky top-20">
            <ForumLeftSidebar />
          </div>
        </aside>

        <!-- Main Feed Column -->
        <div class="w-full lg:flex-1 xl:w-[640px] xl:flex-none 2xl:w-[680px] min-w-0">
          <!-- Search & Filter Bar -->
          <BaseCard class="mb-6 space-y-3">
            <div class="flex flex-col sm:flex-row gap-3">
              <input
                v-model="searchKeyword"
                type="text"
                :placeholder="t('forum.searchPlaceholder')"
                class="flex-1 px-3 py-2 border border-border rounded-lg focus:ring-2 focus:ring-brand-500 focus:border-transparent outline-none text-sm text-foreground"
                @keyup.enter="() => doSearch()"
              />
              <BaseButton @click="doSearch">{{ t('common.search') }}</BaseButton>
              <button
                class="text-sm text-brand-600 hover:text-brand-700 hover:underline shrink-0"
                @click="toggleAdvanced"
              >
                {{ showAdvanced ? t('forum.hideAdvanced') : t('forum.advanced') }}
              </button>
            </div>

            <!-- Advanced Search (collapsible) -->
            <div v-if="showAdvanced" class="space-y-3 border-t border-border pt-3">
              <div class="flex flex-col sm:flex-row gap-3 items-start sm:items-center">
                <input
                  v-model="searchDateFrom"
                  type="date"
                  class="px-3 py-2 border border-border rounded-lg text-sm focus:ring-2 focus:ring-brand-500 focus:border-transparent outline-none"
                />
                <span class="text-muted text-sm hidden sm:inline">{{ t('common.to') }}</span>
                <input
                  v-model="searchDateTo"
                  type="date"
                  class="px-3 py-2 border border-border rounded-lg text-sm focus:ring-2 focus:ring-brand-500 focus:border-transparent outline-none"
                />
                <select
                  v-model="searchLogic"
                  class="px-3 py-2 border border-border rounded-lg text-sm w-20 focus:ring-2 focus:ring-brand-500 focus:border-transparent outline-none"
                >
                  <option value="AND">{{ t('forum.searchLogic.and') }}</option>
                  <option value="OR">{{ t('forum.searchLogic.or') }}</option>
                </select>
              </div>
              <p v-if="dateRangeInvalid" class="text-sm text-danger-600">
                {{ t('forum.dateRangeError') }}
              </p>
              <div class="flex gap-2">
                <BaseButton :disabled="dateRangeInvalid" @click="doSearch">
                  {{ t('forum.applyFilters') }}
                </BaseButton>
                <BaseButton v-if="isSearching" variant="secondary" @click="clearSearch">
                  {{ t('forum.clearFilters') }}
                </BaseButton>
              </div>
            </div>
          </BaseCard>

          <!-- Sort Button Group -->
          <div class="flex items-center gap-1 mb-4">
            <span class="text-sm text-muted mr-2">{{ t('forum.sortLabel') }}</span>
            <button
              class="px-3 py-1.5 text-sm font-medium rounded-l-lg border transition"
              :class="
                sortBy === 'newest'
                  ? 'bg-brand-600 text-white border-brand-600'
                  : 'bg-surface text-foreground border-border hover:bg-surface-alt'
              "
              @click="selectSort('newest')"
            >
              {{ t('forum.sort.newest') }}
            </button>
            <button
              class="px-3 py-1.5 text-sm font-medium border-y transition"
              :class="
                sortBy === 'oldest'
                  ? 'bg-brand-600 text-white border-brand-600'
                  : 'bg-surface text-foreground border-border hover:bg-surface-alt'
              "
              @click="selectSort('oldest')"
            >
              {{ t('forum.sort.oldest') }}
            </button>
            <button
              class="px-3 py-1.5 text-sm font-medium rounded-r-lg border transition"
              :class="
                sortBy === 'most_comments'
                  ? 'bg-brand-600 text-white border-brand-600'
                  : 'bg-surface text-foreground border-border hover:bg-surface-alt'
              "
              @click="selectSort('most_comments')"
            >
              {{ t('forum.sort.mostDiscussed') }}
            </button>
            <span v-if="activeCategoryName" class="ml-3 text-sm text-muted">
              {{ t('common.in') }}
              <span class="font-medium text-foreground">{{ activeCategoryName }}</span>
            </span>
          </div>

          <SkeletonLoader v-if="loading" :lines="3" variant="card" />
          <EmptyState
            v-else-if="posts.length === 0"
            :message="t('forum.emptyMessage')"
            :title="t('forum.emptyTitle')"
            :action-label="t('forum.createPostAction')"
            action-to="/forum/create"
          />

          <!-- Post Feed -->
          <div class="space-y-4">
            <div v-for="post in posts" :key="post.id">
              <PostCard :post="post" />
            </div>
          </div>

          <!-- Infinite Scroll Sentinel -->
          <div ref="sentinelRef" class="h-4"></div>

          <!-- Loading More Spinner -->
          <div v-if="isLoadingMore" class="flex justify-center py-6">
            <svg
              class="animate-spin h-6 w-6 text-brand-600"
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 24 24"
              role="status"
              aria-label="Loading more posts"
            >
              <circle
                class="opacity-25"
                cx="12"
                cy="12"
                r="10"
                stroke="currentColor"
                stroke-width="4"
              ></circle>
              <path
                class="opacity-75"
                fill="currentColor"
                d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
              ></path>
            </svg>
          </div>

          <!-- No More Posts -->
          <p v-if="!hasMore && posts.length > 0" class="mt-4 text-sm text-muted text-center py-4">
            {{ t('forum.noMorePosts') }}
          </p>
        </div>

        <!-- Right Sidebar (lg+) -->
        <aside class="hidden lg:block w-[240px] 2xl:w-[280px] shrink-0">
          <div class="sticky top-20 space-y-6">
            <!-- About -->
            <BaseCard>
              <h3 class="text-sm font-semibold text-foreground mb-2">
                {{ t('forum.sidebar.aboutTitle') }}
              </h3>
              <p class="text-sm text-muted">
                {{ t('forum.sidebar.aboutDescription') }}
              </p>
            </BaseCard>

            <!-- Categories -->
            <BaseCard>
              <h3 class="text-sm font-semibold text-foreground mb-3">
                {{ t('forum.sidebar.categoriesTitle') }}
              </h3>
              <ul class="space-y-1">
                <li>
                  <button
                    class="w-full text-left px-3 py-2 rounded-lg text-sm transition"
                    :class="
                      !categoryFilter
                        ? 'bg-brand-50 text-brand-700 font-medium'
                        : 'text-foreground hover:bg-surface-alt'
                    "
                    @click="selectCategory(null)"
                  >
                    {{ t('forum.sidebar.allPosts') }}
                  </button>
                </li>
                <li v-for="cat in categories" :key="cat.id">
                  <button
                    class="w-full text-left px-3 py-2 rounded-lg text-sm transition flex justify-between items-center"
                    :class="
                      categoryFilter === cat.id
                        ? 'bg-brand-50 text-brand-700 font-medium'
                        : 'text-foreground hover:bg-surface-alt'
                    "
                    @click="selectCategory(cat.id)"
                  >
                    <span>{{ cat.name }}</span>
                    <span class="text-xs text-muted">{{ cat.post_count }}</span>
                  </button>
                </li>
              </ul>
            </BaseCard>

            <!-- Trending Posts -->
            <BaseCard v-if="trendingPosts.length > 0">
              <h3 class="text-sm font-semibold text-foreground mb-3">
                {{ t('forum.sidebar.trendingTitle') }}
              </h3>
              <ul class="space-y-3">
                <li v-for="tp in trendingPosts" :key="tp.id">
                  <router-link
                    :to="`/forum/${tp.id}`"
                    class="block hover:bg-surface-alt rounded-lg px-2 py-1.5 -mx-2 transition"
                  >
                    <p class="text-sm text-foreground font-medium line-clamp-2">{{ tp.title }}</p>
                    <div class="flex items-center gap-3 mt-1 text-xs text-muted">
                      <span>{{ tp.comment_count }} comments</span>
                      <span>{{ tp.view_count }} views</span>
                    </div>
                  </router-link>
                </li>
              </ul>
            </BaseCard>
          </div>
        </aside>
      </div>

      <FloatingCreateButton to="/forum/create" />
    </div>
  </div>
</template>

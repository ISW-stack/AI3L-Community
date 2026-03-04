<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import type { Post, Category } from '@/types'
import { listPosts, searchPosts, getTrendingPosts } from '@/api/posts'
import { listCategories } from '@/api/categories'
import SkeletonLoader from '@/components/SkeletonLoader.vue'
import EmptyState from '@/components/EmptyState.vue'
import PostCard from '@/components/PostCard.vue'
import BaseCard from '@/components/base/BaseCard.vue'
import BaseButton from '@/components/base/BaseButton.vue'
import BasePagination from '@/components/base/BasePagination.vue'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const posts = ref<Post[]>([])
const categories = ref<Category[]>([])
const trendingPosts = ref<Post[]>([])
const total = ref(0)
const currentPage = ref(parseInt(route.query.page as string) || 1)
const totalPages = ref(1)
const pageSize = 20
const loading = ref(false)
const categoryFilter = ref<string | null>((route.query.category as string) || null)

const searchKeyword = ref((route.query.q as string) || '')
const searchDateFrom = ref((route.query.from as string) || '')
const searchDateTo = ref((route.query.to as string) || '')
const searchLogic = ref((route.query.logic as string) || 'AND')
const sortBy = ref((route.query.sort as string) || 'newest')
const isSearching = ref(false)
const showAdvanced = ref(false)

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
  } catch (e) {
    console.error(e)
  }
}

async function fetchTrending() {
  try {
    trendingPosts.value = await getTrendingPosts()
  } catch (e) {
    console.error(e)
  }
}

function syncQueryParams() {
  const query: Record<string, string> = {}
  if (currentPage.value > 1) query.page = String(currentPage.value)
  if (categoryFilter.value) query.category = categoryFilter.value
  if (searchKeyword.value) query.q = searchKeyword.value
  if (searchDateFrom.value) query.from = searchDateFrom.value
  if (searchDateTo.value) query.to = searchDateTo.value
  if (searchLogic.value !== 'AND') query.logic = searchLogic.value
  if (sortBy.value !== 'newest') query.sort = sortBy.value
  router.replace({ query })
}

async function fetchPosts() {
  loading.value = true
  try {
    const params: { page?: number; page_size?: number; category_id?: string; sort?: string } = {
      page: currentPage.value,
      page_size: pageSize,
      sort: sortBy.value,
    }
    if (categoryFilter.value) params.category_id = categoryFilter.value
    const data = await listPosts(params)
    posts.value = data.posts
    total.value = data.total
    totalPages.value = data.total_pages
    isSearching.value = false
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
  syncQueryParams()
}

async function doSearch() {
  currentPage.value = 1
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
    const body: Record<string, unknown> = {
      page: currentPage.value,
      page_size: pageSize,
      logic: searchLogic.value,
    }
    if (searchKeyword.value) body.keyword = searchKeyword.value
    if (categoryFilter.value) body.category_id = categoryFilter.value
    if (searchDateFrom.value) body.date_from = searchDateFrom.value
    if (searchDateTo.value) body.date_to = searchDateTo.value
    const data = await searchPosts(body as Parameters<typeof searchPosts>[0])
    posts.value = data.posts
    total.value = data.total
    totalPages.value = data.total_pages
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
  syncQueryParams()
}

function clearSearch() {
  searchKeyword.value = ''
  searchDateFrom.value = ''
  searchDateTo.value = ''
  categoryFilter.value = null
  currentPage.value = 1
  sortBy.value = 'newest'
  fetchPosts()
}

function goToPage(page: number) {
  currentPage.value = page
  if (isSearching.value) {
    doSearch()
  } else {
    fetchPosts()
  }
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
  currentPage.value = 1
  if (!isSearching.value) fetchPosts()
})
watch(sortBy, () => {
  currentPage.value = 1
  if (!isSearching.value) fetchPosts()
})
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
  <div class="max-w-6xl mx-auto">
    <div class="flex justify-between items-center mb-6">
      <h1 class="text-2xl font-bold text-foreground">Forum</h1>
      <router-link v-if="auth.isAuthenticated && !auth.isGuest" to="/forum/create">
        <BaseButton>New Post</BaseButton>
      </router-link>
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
          All
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

    <div class="flex gap-6">
      <!-- Main Feed Column -->
      <div class="flex-1 min-w-0">
        <!-- Search & Filter Bar -->
        <BaseCard class="mb-6 space-y-3">
          <div class="flex flex-col sm:flex-row gap-3">
            <input
              v-model="searchKeyword"
              type="text"
              placeholder="Search posts..."
              class="flex-1 px-3 py-2 border border-border rounded-lg focus:ring-2 focus:ring-brand-500 focus:border-transparent outline-none text-sm text-foreground"
              @keyup.enter="doSearch"
            />
            <BaseButton @click="doSearch">Search</BaseButton>
            <button
              class="text-sm text-brand-600 hover:text-brand-700 hover:underline shrink-0"
              @click="toggleAdvanced"
            >
              {{ showAdvanced ? 'Hide Advanced' : 'Advanced' }}
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
              <span class="text-muted text-sm hidden sm:inline">to</span>
              <input
                v-model="searchDateTo"
                type="date"
                class="px-3 py-2 border border-border rounded-lg text-sm focus:ring-2 focus:ring-brand-500 focus:border-transparent outline-none"
              />
              <select
                v-model="searchLogic"
                class="px-3 py-2 border border-border rounded-lg text-sm w-20 focus:ring-2 focus:ring-brand-500 focus:border-transparent outline-none"
              >
                <option value="AND">AND</option>
                <option value="OR">OR</option>
              </select>
            </div>
            <p v-if="dateRangeInvalid" class="text-sm text-danger-600">
              Start date must be before end date.
            </p>
            <div class="flex gap-2">
              <BaseButton :disabled="dateRangeInvalid" @click="doSearch">
                Apply Filters
              </BaseButton>
              <BaseButton v-if="isSearching" variant="secondary" @click="clearSearch">
                Clear
              </BaseButton>
            </div>
          </div>
        </BaseCard>

        <!-- Sort Button Group -->
        <div class="flex items-center gap-1 mb-4">
          <span class="text-sm text-muted mr-2">Sort:</span>
          <button
            class="px-3 py-1.5 text-sm font-medium rounded-l-lg border transition"
            :class="
              sortBy === 'newest'
                ? 'bg-brand-600 text-white border-brand-600'
                : 'bg-surface text-foreground border-border hover:bg-surface-alt'
            "
            @click="selectSort('newest')"
          >
            Newest
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
            Oldest
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
            Most Discussed
          </button>
          <span v-if="activeCategoryName" class="ml-3 text-sm text-muted">
            in <span class="font-medium text-foreground">{{ activeCategoryName }}</span>
          </span>
        </div>

        <SkeletonLoader v-if="loading" :lines="3" variant="card" />
        <EmptyState
          v-else-if="posts.length === 0"
          message="No posts found"
          title="Nothing here yet"
          action-label="Create Post"
          action-to="/forum/create"
        />

        <!-- Post Feed -->
        <div class="space-y-4">
          <div v-for="post in posts" :key="post.id">
            <PostCard :post="post" />
          </div>
        </div>

        <div class="mt-6">
          <BasePagination
            :current-page="currentPage"
            :total-pages="totalPages"
            @update:current-page="goToPage"
          />
        </div>
        <p class="mt-4 text-sm text-muted text-center">{{ total }} posts total</p>
      </div>

      <!-- Right Sidebar (desktop only) -->
      <aside class="hidden lg:block w-[280px] shrink-0 space-y-6">
        <!-- About -->
        <BaseCard>
          <h3 class="text-sm font-semibold text-foreground mb-2">About</h3>
          <p class="text-sm text-muted">
            A community for researchers and educators exploring AI in Language Learning and
            Literacy.
          </p>
        </BaseCard>

        <!-- Categories -->
        <BaseCard>
          <h3 class="text-sm font-semibold text-foreground mb-3">Categories</h3>
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
                All Posts
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
          <h3 class="text-sm font-semibold text-foreground mb-3">Trending (7d)</h3>
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
      </aside>
    </div>
  </div>
</template>

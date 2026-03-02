<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import type { Post, Category } from '@/types'
import { listPosts, searchPosts } from '@/api/posts'
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

async function fetchCategories() {
  try {
    categories.value = await listCategories()
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
    const body: any = { page: currentPage.value, page_size: pageSize, logic: searchLogic.value }
    if (searchKeyword.value) body.keyword = searchKeyword.value
    if (categoryFilter.value) body.category_id = categoryFilter.value
    if (searchDateFrom.value) body.date_from = searchDateFrom.value
    if (searchDateTo.value) body.date_to = searchDateTo.value
    const data = await searchPosts(body)
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
  if (searchKeyword.value || searchDateFrom.value || searchDateTo.value) {
    doSearch()
  } else {
    fetchPosts()
  }
})
</script>

<template>
  <div class="max-w-2xl mx-auto">
    <div class="flex justify-between items-center mb-6">
      <h1 class="text-2xl font-bold text-foreground">Forum</h1>
      <router-link v-if="auth.isAuthenticated && !auth.isGuest" to="/forum/create">
        <BaseButton>New Post</BaseButton>
      </router-link>
    </div>

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
        <select
          v-model="categoryFilter"
          class="px-3 py-2 border border-border rounded-lg text-sm focus:ring-2 focus:ring-brand-500 focus:border-transparent outline-none"
        >
          <option :value="null">All Categories</option>
          <option v-for="cat in categories" :key="cat.id" :value="cat.id">{{ cat.name }}</option>
        </select>
        <select
          v-model="searchLogic"
          class="px-3 py-2 border border-border rounded-lg text-sm w-20 focus:ring-2 focus:ring-brand-500 focus:border-transparent outline-none"
        >
          <option value="AND">AND</option>
          <option value="OR">OR</option>
        </select>
        <select
          v-model="sortBy"
          class="px-3 py-2 border border-border rounded-lg text-sm focus:ring-2 focus:ring-brand-500 focus:border-transparent outline-none"
        >
          <option value="newest">Newest</option>
          <option value="oldest">Oldest</option>
          <option value="most_comments">Most Comments</option>
        </select>
      </div>
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
        <BaseButton @click="doSearch">Search</BaseButton>
        <BaseButton v-if="isSearching" variant="secondary" @click="clearSearch">Clear</BaseButton>
      </div>
    </BaseCard>

    <SkeletonLoader v-if="loading" :lines="3" variant="card" />
    <EmptyState
      v-else-if="posts.length === 0"
      message="No posts found"
      title="Nothing here yet"
      action-label="Create Post"
      action-to="/forum/create"
    />

    <!-- FB-style Feed -->
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
</template>

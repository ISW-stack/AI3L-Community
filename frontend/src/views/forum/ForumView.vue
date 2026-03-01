<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { useAuthStore } from '@/stores/auth'
import type { Post, Category } from '@/types'
import { listPosts, searchPosts } from '@/api/posts'
import { listCategories } from '@/api/categories'
import SkeletonLoader from '@/components/SkeletonLoader.vue'
import EmptyState from '@/components/EmptyState.vue'
import BaseCard from '@/components/base/BaseCard.vue'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseBadge from '@/components/base/BaseBadge.vue'
import BasePagination from '@/components/base/BasePagination.vue'

const auth = useAuthStore()

const posts = ref<Post[]>([])
const categories = ref<Category[]>([])
const total = ref(0)
const currentPage = ref(1)
const totalPages = ref(1)
const pageSize = 20
const loading = ref(false)
const categoryFilter = ref<string | null>(null)

const searchKeyword = ref('')
const searchDateFrom = ref('')
const searchDateTo = ref('')
const searchLogic = ref('AND')
const isSearching = ref(false)

async function fetchCategories() {
  try { categories.value = await listCategories() } catch { /* silent */ }
}

async function fetchPosts() {
  loading.value = true
  try {
    const params: { page?: number; page_size?: number; category_id?: string } = {
      page: currentPage.value, page_size: pageSize,
    }
    if (categoryFilter.value) params.category_id = categoryFilter.value
    const data = await listPosts(params)
    posts.value = data.posts
    total.value = data.total
    totalPages.value = data.total_pages
    isSearching.value = false
  } catch { /* error */ } finally { loading.value = false }
}

async function doSearch() {
  if (!searchKeyword.value && !categoryFilter.value && !searchDateFrom.value && !searchDateTo.value) {
    await fetchPosts(); return
  }
  loading.value = true; isSearching.value = true
  try {
    const body: any = { page: currentPage.value, page_size: pageSize, logic: searchLogic.value }
    if (searchKeyword.value) body.keyword = searchKeyword.value
    if (categoryFilter.value) body.category_id = categoryFilter.value
    if (searchDateFrom.value) body.date_from = searchDateFrom.value
    if (searchDateTo.value) body.date_to = searchDateTo.value
    const data = await searchPosts(body)
    posts.value = data.posts; total.value = data.total; totalPages.value = data.total_pages
  } catch { /* error */ } finally { loading.value = false }
}

function clearSearch() {
  searchKeyword.value = ''; searchDateFrom.value = ''; searchDateTo.value = ''
  categoryFilter.value = null; currentPage.value = 1; fetchPosts()
}

function goToPage(page: number) {
  currentPage.value = page
  isSearching.value ? doSearch() : fetchPosts()
}

function stripHtml(html: string): string {
  const div = document.createElement('div'); div.innerHTML = html; return div.textContent || ''
}

watch(categoryFilter, () => { currentPage.value = 1; if (!isSearching.value) fetchPosts() })
onMounted(() => { fetchCategories(); fetchPosts() })
</script>

<template>
  <div>
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
          v-model="searchKeyword" type="text" placeholder="Search posts..."
          class="flex-1 px-3 py-2 border border-border rounded-lg focus:ring-2 focus:ring-brand-500 focus:border-transparent outline-none text-sm text-foreground"
          @keyup.enter="doSearch"
        />
        <select v-model="categoryFilter" class="px-3 py-2 border border-border rounded-lg text-sm focus:ring-2 focus:ring-brand-500 focus:border-transparent outline-none">
          <option :value="null">All Categories</option>
          <option v-for="cat in categories" :key="cat.id" :value="cat.id">{{ cat.name }}</option>
        </select>
        <select v-model="searchLogic" class="px-3 py-2 border border-border rounded-lg text-sm w-20 focus:ring-2 focus:ring-brand-500 focus:border-transparent outline-none">
          <option value="AND">AND</option>
          <option value="OR">OR</option>
        </select>
      </div>
      <div class="flex flex-col sm:flex-row gap-3 items-start sm:items-center">
        <input v-model="searchDateFrom" type="date" class="px-3 py-2 border border-border rounded-lg text-sm focus:ring-2 focus:ring-brand-500 focus:border-transparent outline-none" />
        <span class="text-muted text-sm hidden sm:inline">to</span>
        <input v-model="searchDateTo" type="date" class="px-3 py-2 border border-border rounded-lg text-sm focus:ring-2 focus:ring-brand-500 focus:border-transparent outline-none" />
        <BaseButton @click="doSearch">Search</BaseButton>
        <BaseButton v-if="isSearching" variant="secondary" @click="clearSearch">Clear</BaseButton>
      </div>
    </BaseCard>

    <SkeletonLoader v-if="loading" :lines="3" variant="card" />
    <EmptyState v-else-if="posts.length === 0" message="No posts found" title="Nothing here yet" action-label="Create Post" action-to="/forum/create" />

    <div class="space-y-3">
      <router-link v-for="post in posts" :key="post.id" :to="`/forum/${post.id}`" class="block">
        <BaseCard hoverable>
          <div class="flex justify-between items-start mb-2">
            <h2 class="text-lg font-semibold text-foreground">{{ post.title }}</h2>
            <BaseBadge v-if="post.category_name" class="shrink-0 ml-3">{{ post.category_name }}</BaseBadge>
          </div>
          <p class="text-sm text-muted mb-3 line-clamp-2">{{ stripHtml(post.content) }}</p>
          <div class="flex items-center justify-between text-xs text-muted">
            <div class="flex items-center gap-3">
              <span>{{ post.author.display_name }}</span>
              <span>{{ new Date(post.created_at).toLocaleDateString() }}</span>
            </div>
            <div class="flex items-center gap-3">
              <span v-if="post.keywords?.length">{{ post.keywords.slice(0, 3).join(', ') }}</span>
              <span>{{ post.comment_count }} comments</span>
            </div>
          </div>
        </BaseCard>
      </router-link>
    </div>

    <div class="mt-6">
      <BasePagination :current-page="currentPage" :total-pages="totalPages" @update:current-page="goToPage" />
    </div>
    <p class="mt-4 text-sm text-muted text-center">{{ total }} posts total</p>
  </div>
</template>

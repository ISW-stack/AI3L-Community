<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import api from '@/composables/api'
import SkeletonLoader from '@/components/SkeletonLoader.vue'
import EmptyState from '@/components/EmptyState.vue'

const auth = useAuthStore()
const router = useRouter()

interface Author {
  id: string
  username: string
  display_name: string
  avatar_url: string | null
}

interface Post {
  id: string
  title: string
  content: string
  author: Author
  category_id: string | null
  category_name: string | null
  keywords: string[] | null
  allow_comments: boolean
  version: number
  comment_count: number
  created_at: string
  updated_at: string
}

interface Category {
  id: string
  name: string
  description: string | null
}

const posts = ref<Post[]>([])
const categories = ref<Category[]>([])
const total = ref(0)
const currentPage = ref(1)
const totalPages = ref(1)
const pageSize = 20
const loading = ref(false)
const categoryFilter = ref<string | null>(null)

// Search
const searchKeyword = ref('')
const searchDateFrom = ref('')
const searchDateTo = ref('')
const searchLogic = ref('AND')
const isSearching = ref(false)

async function fetchCategories() {
  try {
    const { data } = await api.get('/categories')
    categories.value = data.categories
  } catch {
    // silent
  }
}

async function fetchPosts() {
  loading.value = true
  try {
    const params: Record<string, unknown> = {
      page: currentPage.value,
      page_size: pageSize,
    }
    if (categoryFilter.value) params.category_id = categoryFilter.value

    const { data } = await api.get('/posts', { params })
    posts.value = data.posts
    total.value = data.total
    totalPages.value = data.total_pages
    isSearching.value = false
  } catch {
    // error
  } finally {
    loading.value = false
  }
}

async function doSearch() {
  if (!searchKeyword.value && !categoryFilter.value && !searchDateFrom.value && !searchDateTo.value) {
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

    const { data } = await api.post('/posts/search', body)
    posts.value = data.posts
    total.value = data.total
    totalPages.value = data.total_pages
  } catch {
    // error
  } finally {
    loading.value = false
  }
}

function clearSearch() {
  searchKeyword.value = ''
  searchDateFrom.value = ''
  searchDateTo.value = ''
  categoryFilter.value = null
  currentPage.value = 1
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

function stripHtml(html: string): string {
  const div = document.createElement('div')
  div.innerHTML = html
  return div.textContent || ''
}

watch(categoryFilter, () => {
  currentPage.value = 1
  if (!isSearching.value) fetchPosts()
})

onMounted(() => {
  fetchCategories()
  fetchPosts()
})
</script>

<template>
  <div class="max-w-5xl mx-auto py-8 px-4">
    <div class="flex justify-between items-center mb-6">
      <h1 class="text-2xl font-bold text-gray-900">Forum</h1>
      <router-link
        v-if="auth.isAuthenticated && !auth.isGuest"
        to="/forum/create"
        class="bg-blue-600 text-white px-4 py-2 rounded-lg text-sm hover:bg-blue-700 transition"
      >
        New Post
      </router-link>
    </div>

    <!-- Search & Filter Bar -->
    <div class="bg-white rounded-xl shadow p-4 mb-6 space-y-3">
      <div class="flex gap-3">
        <input
          v-model="searchKeyword"
          type="text"
          placeholder="Search posts..."
          class="flex-1 px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none text-sm"
          @keyup.enter="doSearch"
        />
        <select
          v-model="categoryFilter"
          class="px-3 py-2 border border-gray-300 rounded-lg text-sm"
        >
          <option :value="null">All Categories</option>
          <option v-for="cat in categories" :key="cat.id" :value="cat.id">{{ cat.name }}</option>
        </select>
        <select
          v-model="searchLogic"
          class="px-3 py-2 border border-gray-300 rounded-lg text-sm w-20"
        >
          <option value="AND">AND</option>
          <option value="OR">OR</option>
        </select>
      </div>
      <div class="flex gap-3 items-center">
        <input
          v-model="searchDateFrom"
          type="date"
          class="px-3 py-2 border border-gray-300 rounded-lg text-sm"
          placeholder="From"
        />
        <span class="text-gray-400 text-sm">to</span>
        <input
          v-model="searchDateTo"
          type="date"
          class="px-3 py-2 border border-gray-300 rounded-lg text-sm"
          placeholder="To"
        />
        <button
          @click="doSearch"
          class="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700"
        >
          Search
        </button>
        <button
          v-if="isSearching"
          @click="clearSearch"
          class="px-4 py-2 bg-gray-100 text-gray-600 rounded-lg text-sm hover:bg-gray-200"
        >
          Clear
        </button>
      </div>
    </div>

    <!-- Post List -->
    <SkeletonLoader v-if="loading" :lines="3" variant="card" />
    <EmptyState v-else-if="posts.length === 0" message="No posts found" title="Nothing here yet" action-label="Create Post" action-to="/forum/create" />

    <div class="space-y-3">
      <router-link
        v-for="post in posts"
        :key="post.id"
        :to="`/forum/${post.id}`"
        class="block bg-white rounded-xl shadow hover:shadow-md transition p-5"
      >
        <div class="flex justify-between items-start mb-2">
          <h2 class="text-lg font-semibold text-gray-900 hover:text-blue-600">{{ post.title }}</h2>
          <span v-if="post.category_name" class="text-xs px-2 py-0.5 rounded-full bg-blue-50 text-blue-600 shrink-0 ml-3">
            {{ post.category_name }}
          </span>
        </div>
        <p class="text-sm text-gray-600 mb-3 line-clamp-2">{{ stripHtml(post.content) }}</p>
        <div class="flex items-center justify-between text-xs text-gray-400">
          <div class="flex items-center gap-3">
            <span>{{ post.author.display_name }}</span>
            <span>{{ new Date(post.created_at).toLocaleDateString() }}</span>
          </div>
          <div class="flex items-center gap-3">
            <span v-if="post.keywords?.length" class="text-gray-400">
              {{ post.keywords.slice(0, 3).join(', ') }}
            </span>
            <span>{{ post.comment_count }} comments</span>
          </div>
        </div>
      </router-link>
    </div>

    <!-- Pagination -->
    <div v-if="totalPages > 1" class="flex justify-center gap-2 mt-6">
      <button
        v-for="page in totalPages"
        :key="page"
        @click="goToPage(page)"
        class="w-8 h-8 rounded text-sm transition"
        :class="page === currentPage ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'"
      >
        {{ page }}
      </button>
    </div>

    <p class="mt-4 text-sm text-gray-500 text-center">{{ total }} posts total</p>
  </div>
</template>

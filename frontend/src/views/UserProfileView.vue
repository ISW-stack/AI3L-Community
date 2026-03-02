<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import type { PublicUser, Post } from '@/types'
import { getPublicProfile } from '@/api/users'
import { listPosts } from '@/api/posts'
import PostCard from '@/components/PostCard.vue'
import BaseCard from '@/components/base/BaseCard.vue'
import BaseBadge from '@/components/base/BaseBadge.vue'
import BasePagination from '@/components/base/BasePagination.vue'
import BaseAvatar from '@/components/base/BaseAvatar.vue'
import SkeletonLoader from '@/components/SkeletonLoader.vue'
import EmptyState from '@/components/EmptyState.vue'

const route = useRoute()
const auth = useAuthStore()

const userId = computed(() => route.params.id as string)
const user = ref<PublicUser | null>(null)
const posts = ref<Post[]>([])
const postsTotal = ref(0)
const postsPage = ref(1)
const postsTotalPages = ref(1)
const postsPageSize = 20
const loading = ref(true)
const postsLoading = ref(false)

const isOwnProfile = computed(() => auth.user && auth.user.id === userId.value)

const roleBadgeVariant = computed(() => {
  if (!user.value) return 'brand'
  const map: Record<string, string> = {
    SUPER_ADMIN: 'danger',
    ADMIN: 'orange',
    MEMBER: 'brand',
    GUEST: 'neutral',
  }
  return map[user.value.role] || 'brand'
})

async function fetchUser() {
  loading.value = true
  try {
    user.value = await getPublicProfile(userId.value)
  } catch {
    user.value = null
  } finally {
    loading.value = false
  }
}

async function fetchPosts() {
  postsLoading.value = true
  try {
    const data = await listPosts({
      author_id: userId.value,
      page: postsPage.value,
      page_size: postsPageSize,
    })
    posts.value = data.posts
    postsTotal.value = data.total
    postsTotalPages.value = data.total_pages
  } catch (e) {
    console.error(e)
  } finally {
    postsLoading.value = false
  }
}

function goToPage(page: number) {
  postsPage.value = page
  fetchPosts()
}

function toLocaleTime(dateStr: string): string {
  return new Date(dateStr).toLocaleString()
}

watch(userId, () => {
  postsPage.value = 1
  fetchUser()
  fetchPosts()
})

onMounted(() => {
  fetchUser()
  fetchPosts()
})
</script>

<template>
  <div class="max-w-2xl mx-auto">
    <SkeletonLoader v-if="loading" :lines="2" variant="card" />

    <div v-else-if="!user" class="text-center py-12">
      <p class="text-muted mb-4">User not found.</p>
      <router-link to="/forum" class="text-brand-600 hover:underline">Back to Forum</router-link>
    </div>

    <template v-else>
      <!-- Profile Header -->
      <BaseCard padding="lg" class="mb-6">
        <div class="flex items-start gap-4">
          <BaseAvatar :src="user.avatar_url" :name="user.display_name" size="lg" />
          <div class="flex-1 min-w-0">
            <div class="flex items-center gap-2 mb-1">
              <h1 class="text-2xl font-bold text-foreground">{{ user.display_name }}</h1>
              <BaseBadge :variant="roleBadgeVariant as any">{{ user.role }}</BaseBadge>
            </div>
            <p class="text-sm text-muted mb-1">@{{ user.username }}</p>
            <p class="text-xs text-muted">
              Joined {{ new Date(user.created_at).toLocaleDateString() }}
            </p>
          </div>
          <router-link
            v-if="isOwnProfile"
            to="/profile"
            class="text-sm text-brand-600 hover:underline shrink-0"
          >
            Edit Profile
          </router-link>
        </div>

        <!-- Info Cards -->
        <div v-if="user.bio || user.affiliation || user.orcid" class="mt-4 space-y-2">
          <div v-if="user.bio" class="text-sm text-foreground/80">
            <span class="font-medium text-foreground">Bio:</span> {{ user.bio }}
          </div>
          <div v-if="user.affiliation" class="text-sm text-foreground/80">
            <span class="font-medium text-foreground">Affiliation:</span> {{ user.affiliation }}
          </div>
          <div v-if="user.orcid" class="text-sm text-foreground/80">
            <span class="font-medium text-foreground">ORCID:</span> {{ user.orcid }}
          </div>
        </div>
      </BaseCard>

      <!-- Posts Feed -->
      <h2 class="text-lg font-semibold text-foreground mb-4">
        Posts ({{ postsTotal }})
      </h2>

      <SkeletonLoader v-if="postsLoading" :lines="3" variant="card" />
      <EmptyState
        v-else-if="posts.length === 0"
        title="No posts yet"
        message="This user hasn't posted anything."
      />

      <div v-else class="space-y-4">
        <div v-for="p in posts" :key="p.id">
          <PostCard :post="p" :format-time="toLocaleTime" :content-clamp="3" />
        </div>
      </div>

      <div class="mt-6">
        <BasePagination
          v-if="postsTotalPages > 1"
          :current-page="postsPage"
          :total-pages="postsTotalPages"
          @update:current-page="goToPage"
        />
      </div>
    </template>
  </div>
</template>

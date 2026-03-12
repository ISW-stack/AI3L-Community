<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@/stores/auth'
import { useToastStore } from '@/stores/toast'
import { usePagination } from '@/composables/usePagination'
import { getErrorMessage } from '@/utils/error'
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
import BaseBreadcrumb from '@/components/base/BaseBreadcrumb.vue'

const { t } = useI18n()
const route = useRoute()
const auth = useAuthStore()
const toast = useToastStore()

const userId = computed(() => route.params.id as string)
const user = ref<PublicUser | null>(null)
const posts = ref<Post[]>([])
const {
  page: postsPage,
  total: postsTotal,
  totalPages: postsTotalPages,
  pageSize: postsPageSize,
  setPage,
  resetPage,
  updateFromResponse,
} = usePagination()
const loading = ref(true)
const postsLoading = ref(false)
let userFetchId = 0
let postsFetchId = 0

const isOwnProfile = computed(() => auth.user && auth.user.id === userId.value)

type BadgeVariant = 'brand' | 'success' | 'warning' | 'danger' | 'neutral' | 'orange' | 'purple'

const roleBadgeVariant = computed((): BadgeVariant => {
  if (!user.value) return 'brand'
  const map: Record<string, BadgeVariant> = {
    SUPER_ADMIN: 'danger',
    ADMIN: 'orange',
    MEMBER: 'brand',
    GUEST: 'neutral',
  }
  return map[user.value.role] || 'brand'
})

async function fetchUser() {
  const localId = ++userFetchId
  loading.value = true
  try {
    const data = await getPublicProfile(userId.value)
    if (localId !== userFetchId) return
    user.value = data
  } catch (e: unknown) {
    toast.show(getErrorMessage(e, t('userProfile.fetchError')), 'error')
    if (localId === userFetchId) user.value = null
  } finally {
    if (localId === userFetchId) loading.value = false
  }
}

async function fetchPosts() {
  const localId = ++postsFetchId
  postsLoading.value = true
  try {
    const data = await listPosts({
      author_id: userId.value,
      page: postsPage.value,
      page_size: postsPageSize,
    })
    if (localId !== postsFetchId) return
    posts.value = data.posts
    updateFromResponse(data.total ?? 0, data.total_pages ?? 1)
  } catch (e: unknown) {
    toast.show(getErrorMessage(e, t('userProfile.fetchPostsError')), 'error')
  } finally {
    if (localId === postsFetchId) postsLoading.value = false
  }
}

function goToPage(page: number) {
  setPage(page)
  fetchPosts()
}

function toLocaleTime(dateStr: string): string {
  return new Date(dateStr).toLocaleString()
}

watch(userId, () => {
  resetPage()
  fetchUser()
  fetchPosts()
})

onMounted(() => {
  fetchUser()
  fetchPosts()
})
</script>

<template>
  <div class="w-full lg:px-layout px-4 py-6 sm:py-8 min-h-screen">
    <div class="max-w-4xl mx-auto">
      <BaseBreadcrumb
        :items="[
          { label: t('breadcrumb.home'), to: '/' },
          { label: t('breadcrumb.users'), to: '/forum' },
          { label: user?.display_name || '...' },
        ]"
      />

      <SkeletonLoader v-if="loading" :lines="2" variant="card" />

      <div v-else-if="!user" class="text-center py-12">
        <p class="text-muted mb-4">{{ t('userProfile.notFound') }}</p>
        <router-link to="/forum" class="text-brand-600 hover:underline">{{
          t('userProfile.backToForum')
        }}</router-link>
      </div>

      <template v-else>
        <!-- Profile Header -->
        <BaseCard padding="lg" class="mb-6">
          <div class="flex items-start gap-4">
            <BaseAvatar :src="user.avatar_url" :name="user.display_name" size="lg" />
            <div class="flex-1 min-w-0">
              <div class="flex items-center gap-2 mb-1">
                <h1 class="text-2xl font-bold text-foreground">{{ user.display_name }}</h1>
                <BaseBadge :variant="roleBadgeVariant">{{ user.role }}</BaseBadge>
              </div>
              <p class="text-sm text-muted mb-1">@{{ user.username }}</p>
              <p class="text-xs text-muted">
                {{ t('userProfile.joined') }} {{ new Date(user.created_at).toLocaleDateString() }}
              </p>
            </div>
            <router-link
              v-if="isOwnProfile"
              to="/profile"
              class="text-sm text-brand-600 hover:underline shrink-0"
            >
              {{ t('userProfile.editProfileBtn') }}
            </router-link>
          </div>

          <!-- Info Cards -->
          <div v-if="user.bio || user.affiliation || user.orcid" class="mt-4 space-y-2">
            <div v-if="user.bio" class="text-sm text-foreground/80">
              <span class="font-medium text-foreground">{{ t('userProfile.bio') }}</span>
              {{ user.bio }}
            </div>
            <div v-if="user.affiliation" class="text-sm text-foreground/80">
              <span class="font-medium text-foreground">{{ t('userProfile.affiliation') }}</span>
              {{ user.affiliation }}
            </div>
            <div v-if="user.orcid" class="text-sm text-foreground/80">
              <span class="font-medium text-foreground">{{ t('userProfile.orcid') }}</span>
              {{ user.orcid }}
            </div>
          </div>
        </BaseCard>

        <!-- Posts Feed -->
        <h2 class="text-lg font-semibold text-foreground mb-4">
          {{ t('userProfile.postsTitle') }} ({{ postsTotal }})
        </h2>

        <SkeletonLoader v-if="postsLoading" :lines="3" variant="card" />
        <EmptyState
          v-else-if="posts.length === 0"
          :title="t('userProfile.postsEmptyTitle')"
          :message="t('userProfile.postsEmptyMessage')"
        />

        <div v-else class="space-y-4">
          <div v-for="p in posts" :key="p.id">
            <PostCard :post="p" :format-time="toLocaleTime" :max-preview-lines="3" />
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
  </div>
</template>

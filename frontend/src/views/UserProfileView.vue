<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { formatDate, formatDateTime } from '@/utils/date'
import { useAuthStore } from '@/stores/auth'
import { useToastStore } from '@/stores/toast'
import { usePagination } from '@/composables/usePagination'
import { getErrorMessage } from '@/utils/error'
import type { PublicUser, Post } from '@/types'
import { getPublicProfile } from '@/api/users'
import { listPosts } from '@/api/posts'
import { listCoAuthoredPosts } from '@/api/coauthors'
import { sanitizeHtml } from '@/utils/sanitize'
import { MessageSquare, Lock } from 'lucide-vue-next'
import PostCard from '@/components/PostCard.vue'
import BaseCard from '@/components/base/BaseCard.vue'
import BaseBadge from '@/components/base/BaseBadge.vue'
import BasePagination from '@/components/base/BasePagination.vue'
import BaseAvatar from '@/components/base/BaseAvatar.vue'
import SkeletonLoader from '@/components/SkeletonLoader.vue'
import EmptyState from '@/components/EmptyState.vue'
import BaseBreadcrumb from '@/components/base/BaseBreadcrumb.vue'
import SocialActions from '@/components/social/SocialActions.vue'
import FriendRecommendations from '@/components/social/FriendRecommendations.vue'

const { t, locale } = useI18n()
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

// Co-authored posts
const coAuthoredPosts = ref<Post[]>([])
const coAuthoredLoading = ref(false)

async function fetchCoAuthoredPosts() {
  coAuthoredLoading.value = true
  try {
    const data = await listCoAuthoredPosts(userId.value, 1, 10)
    coAuthoredPosts.value = data.posts as Post[]
  } catch {
    // Non-critical, silently fail
  } finally {
    coAuthoredLoading.value = false
  }
}

// Active tab for the profile sections
const activeSection = ref<'posts' | 'coauthored'>('posts')

function switchSection(section: 'posts' | 'coauthored') {
  activeSection.value = section
  if (section === 'coauthored' && coAuthoredPosts.value.length === 0 && !coAuthoredLoading.value) {
    fetchCoAuthoredPosts()
  }
}

function goToPage(page: number) {
  setPage(page)
  fetchPosts()
}

function toLocaleTime(dateStr: string): string {
  return formatDateTime(dateStr, locale.value)
}

watch(userId, () => {
  resetPage()
  coAuthoredPosts.value = []
  coAuthoredLoading.value = false
  activeSection.value = 'posts'
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
          <div class="flex flex-col sm:flex-row sm:items-start gap-4">
            <div class="flex items-center sm:items-start gap-3 sm:gap-4">
              <BaseAvatar :src="user.avatar_url" :name="user.display_name" size="lg" />
              <div class="min-w-0">
                <div class="flex flex-wrap items-center gap-2 mb-1">
                  <h1 class="text-xl sm:text-2xl font-bold text-foreground">
                    {{ user.display_name }}
                  </h1>
                  <BaseBadge :variant="roleBadgeVariant">{{ user.role }}</BaseBadge>
                </div>
                <p class="text-sm text-muted mb-1">@{{ user.username }}</p>
                <p class="text-xs text-muted">
                  {{ t('userProfile.joined') }} {{ formatDate(user.created_at, locale) }}
                </p>
              </div>
            </div>
            <div
              class="flex flex-wrap items-center gap-2 sm:shrink-0 sm:flex-col sm:items-end sm:ml-auto"
            >
              <router-link
                v-if="isOwnProfile"
                to="/profile"
                class="text-sm text-brand-600 hover:underline"
              >
                {{ t('userProfile.editProfileBtn') }}
              </router-link>
              <SocialActions
                v-if="!isOwnProfile && auth.isAuthenticated && !auth.isGuest"
                :user-id="userId"
              />
              <router-link
                v-if="!isOwnProfile && auth.isAuthenticated && !auth.isGuest"
                :to="`/messages/${userId}`"
                class="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium rounded-lg border border-border text-foreground hover:bg-surface-alt transition"
                :title="
                  user?.dm_friends_only
                    ? 'This user only accepts messages from friends'
                    : 'Send message'
                "
                data-testid="message-btn"
              >
                <MessageSquare class="w-4 h-4" aria-hidden="true" />
                Message
                <Lock
                  v-if="user?.dm_friends_only"
                  class="w-3 h-3 text-muted"
                  aria-label="Friends only"
                />
              </router-link>
            </div>
          </div>

          <!-- Info Cards -->
          <div v-if="user.bio || user.affiliation || user.orcid" class="mt-4 space-y-2">
            <div v-if="user.bio" class="text-sm text-foreground/80">
              <span class="font-medium text-foreground block mb-1">{{ t('userProfile.bio') }}</span>
              <div
                class="prose prose-sm max-w-none break-words"
                v-html="sanitizeHtml(user.bio)"
              ></div>
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

          <!-- Profile View Counts -->
          <div class="mt-3 text-xs text-muted">
            {{
              t('profile.viewCount', {
                unique: user.profile_view_count_unique,
                total: user.profile_view_count_total,
              })
            }}
          </div>
        </BaseCard>

        <!-- Friend Recommendations (own profile only) -->
        <FriendRecommendations v-if="isOwnProfile" class="mb-6" />

        <!-- Section Tabs -->
        <div class="flex gap-1 mb-4 border-b border-border" role="tablist">
          <button
            id="tab-posts"
            role="tab"
            :aria-selected="activeSection === 'posts'"
            aria-controls="panel-posts"
            class="px-4 py-2 text-sm font-medium border-b-2 transition"
            :class="
              activeSection === 'posts'
                ? 'border-brand-600 text-brand-600'
                : 'border-transparent text-muted hover:text-foreground'
            "
            @click="switchSection('posts')"
          >
            {{ t('userProfile.postsTitle') }} ({{ postsTotal }})
          </button>
          <button
            id="tab-coauthored"
            role="tab"
            :aria-selected="activeSection === 'coauthored'"
            aria-controls="panel-coauthored"
            class="px-4 py-2 text-sm font-medium border-b-2 transition"
            :class="
              activeSection === 'coauthored'
                ? 'border-brand-600 text-brand-600'
                : 'border-transparent text-muted hover:text-foreground'
            "
            @click="switchSection('coauthored')"
          >
            {{ t('profile.coAuthoredPosts') }}
          </button>
        </div>

        <!-- Posts Feed -->
        <div
          v-if="activeSection === 'posts'"
          id="panel-posts"
          role="tabpanel"
          aria-labelledby="tab-posts"
        >
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
        </div>

        <!-- Co-Authored Posts -->
        <div
          v-if="activeSection === 'coauthored'"
          id="panel-coauthored"
          role="tabpanel"
          aria-labelledby="tab-coauthored"
        >
          <SkeletonLoader v-if="coAuthoredLoading" :lines="3" variant="card" />
          <EmptyState
            v-else-if="coAuthoredPosts.length === 0"
            :title="t('userProfile.coAuthoredEmptyTitle')"
            :message="t('userProfile.coAuthoredEmptyMessage')"
          />
          <div v-else class="space-y-4">
            <div v-for="p in coAuthoredPosts" :key="p.id">
              <PostCard :post="p" :format-time="toLocaleTime" :max-preview-lines="3" />
            </div>
          </div>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import type { FollowUser } from '@/types/social'
import { listFollowing, listFollowers, unfollowUser, followUser } from '@/api/social'
import { usePagination } from '@/composables/usePagination'
import { getErrorMessage } from '@/utils/error'
import { useToastStore } from '@/stores/toast'
import { useLocale } from '@/composables/useLocale'
import BaseAvatar from '@/components/base/BaseAvatar.vue'
import BaseButton from '@/components/base/BaseButton.vue'
import BasePagination from '@/components/base/BasePagination.vue'
import SkeletonLoader from '@/components/SkeletonLoader.vue'
import EmptyState from '@/components/EmptyState.vue'
import BaseBreadcrumb from '@/components/base/BaseBreadcrumb.vue'
import { UserPlus, UserMinus } from 'lucide-vue-next'

const { t } = useLocale()
const toast = useToastStore()

const activeTab = ref<'following' | 'followers'>('following')

// Following state
const following = ref<FollowUser[]>([])
const followingLoading = ref(false)
const {
  page: followingPage,
  totalPages: followingTotalPages,
  pageSize: followingPageSize,
  setPage: setFollowingPage,
  updateFromResponse: updateFollowingResponse,
} = usePagination()
let followingFetchId = 0

// Followers state
const followers = ref<FollowUser[]>([])
const followersLoading = ref(false)
const followingBackSet = ref<Set<string>>(new Set())
const {
  page: followersPage,
  totalPages: followersTotalPages,
  pageSize: followersPageSize,
  setPage: setFollowersPage,
  updateFromResponse: updateFollowersResponse,
} = usePagination()
let followersFetchId = 0

// Track loading state per user for follow back
const followActionLoading = ref<Set<string>>(new Set())

async function fetchFollowing() {
  const localId = ++followingFetchId
  followingLoading.value = true
  try {
    const result = await listFollowing(followingPage.value, followingPageSize)
    if (localId !== followingFetchId) return
    following.value = result.users
    updateFollowingResponse(result.total)
    // Build the set of user IDs we are following for cross-reference
    followingBackSet.value = new Set(result.users.map((u) => u.user_id))
  } catch (e: unknown) {
    if (localId !== followingFetchId) return
    toast.show(getErrorMessage(e, t('social.loadFollowingError')), 'error')
  } finally {
    if (localId === followingFetchId) {
      followingLoading.value = false
    }
  }
}

async function fetchFollowers() {
  const localId = ++followersFetchId
  followersLoading.value = true
  try {
    const result = await listFollowers(followersPage.value, followersPageSize)
    if (localId !== followersFetchId) return
    followers.value = result.users
    updateFollowersResponse(result.total)
  } catch (e: unknown) {
    if (localId !== followersFetchId) return
    toast.show(getErrorMessage(e, t('social.loadFollowersError')), 'error')
  } finally {
    if (localId === followersFetchId) {
      followersLoading.value = false
    }
  }
}

function switchTab(tab: 'following' | 'followers') {
  activeTab.value = tab
  if (tab === 'following') {
    setFollowingPage(1)
    fetchFollowing()
  } else {
    setFollowersPage(1)
    fetchFollowers()
  }
}

function goToFollowingPage(p: number) {
  setFollowingPage(p)
  fetchFollowing()
}

function goToFollowersPage(p: number) {
  setFollowersPage(p)
  fetchFollowers()
}

async function handleUnfollow(userId: string) {
  followActionLoading.value.add(userId)
  try {
    await unfollowUser(userId)
    following.value = following.value.filter((u) => u.user_id !== userId)
    followingBackSet.value.delete(userId)
    toast.show(t('social.unfollowSuccess'), 'success')
  } catch (e: unknown) {
    toast.show(getErrorMessage(e, t('social.unfollowError')), 'error')
  } finally {
    followActionLoading.value.delete(userId)
  }
}

async function handleFollowBack(userId: string) {
  followActionLoading.value.add(userId)
  try {
    await followUser(userId)
    followingBackSet.value.add(userId)
    toast.show(t('social.followSuccess'), 'success')
  } catch (e: unknown) {
    toast.show(getErrorMessage(e, t('social.followError')), 'error')
  } finally {
    followActionLoading.value.delete(userId)
  }
}

function isFollowingUser(userId: string): boolean {
  return followingBackSet.value.has(userId)
}

onMounted(() => {
  fetchFollowing()
  fetchFollowers()
})
</script>

<template>
  <div class="max-w-3xl mx-auto">
    <BaseBreadcrumb
      :items="[{ label: t('breadcrumb.home'), to: '/' }, { label: t('breadcrumb.following') }]"
    />
    <h1 class="text-2xl font-bold text-foreground mb-6">{{ t('social.following') }}</h1>

    <!-- Tabs -->
    <div class="flex gap-1 mb-4 border-b border-border" role="tablist">
      <button
        role="tab"
        :aria-selected="activeTab === 'following'"
        class="px-4 py-2 text-sm font-medium border-b-2 transition"
        :class="
          activeTab === 'following'
            ? 'border-brand-600 text-brand-600'
            : 'border-transparent text-muted hover:text-foreground'
        "
        @click="switchTab('following')"
      >
        {{ t('social.following') }}
      </button>
      <button
        role="tab"
        :aria-selected="activeTab === 'followers'"
        class="px-4 py-2 text-sm font-medium border-b-2 transition"
        :class="
          activeTab === 'followers'
            ? 'border-brand-600 text-brand-600'
            : 'border-transparent text-muted hover:text-foreground'
        "
        @click="switchTab('followers')"
      >
        {{ t('social.followers') }}
      </button>
    </div>

    <!-- Following Tab -->
    <div v-if="activeTab === 'following'">
      <SkeletonLoader v-if="followingLoading" :lines="5" variant="list" />

      <EmptyState
        v-else-if="following.length === 0"
        :title="t('social.noFollowing')"
        :message="t('social.noFollowingMessage')"
      />

      <div v-else class="bg-surface rounded-lg shadow border border-border divide-y divide-border">
        <div v-for="user in following" :key="user.id" class="flex items-center gap-4 px-5 py-4">
          <router-link :to="`/users/${user.user_id}`">
            <BaseAvatar :src="user.avatar_url" :name="user.display_name" size="md" />
          </router-link>

          <div class="flex-1 min-w-0">
            <router-link
              :to="`/users/${user.user_id}`"
              class="text-sm font-semibold text-foreground hover:text-brand-600 hover:underline"
            >
              {{ user.display_name }}
            </router-link>
            <p class="text-xs text-muted truncate">@{{ user.username }}</p>
          </div>

          <BaseButton
            size="sm"
            variant="secondary"
            :disabled="followActionLoading.has(user.user_id)"
            @click="handleUnfollow(user.user_id)"
          >
            <UserMinus class="w-3.5 h-3.5 mr-1" />
            {{ t('social.unfollow') }}
          </BaseButton>
        </div>
      </div>

      <BasePagination
        v-if="followingTotalPages > 1"
        :current-page="followingPage"
        :total-pages="followingTotalPages"
        class="mt-6"
        @update:current-page="goToFollowingPage"
      />
    </div>

    <!-- Followers Tab -->
    <div v-if="activeTab === 'followers'">
      <SkeletonLoader v-if="followersLoading" :lines="5" variant="list" />

      <EmptyState
        v-else-if="followers.length === 0"
        :title="t('social.noFollowers')"
        :message="t('social.noFollowersMessage')"
      />

      <div v-else class="bg-surface rounded-lg shadow border border-border divide-y divide-border">
        <div v-for="user in followers" :key="user.id" class="flex items-center gap-4 px-5 py-4">
          <router-link :to="`/users/${user.user_id}`">
            <BaseAvatar :src="user.avatar_url" :name="user.display_name" size="md" />
          </router-link>

          <div class="flex-1 min-w-0">
            <router-link
              :to="`/users/${user.user_id}`"
              class="text-sm font-semibold text-foreground hover:text-brand-600 hover:underline"
            >
              {{ user.display_name }}
            </router-link>
            <p class="text-xs text-muted truncate">@{{ user.username }}</p>
          </div>

          <BaseButton
            v-if="!isFollowingUser(user.user_id)"
            size="sm"
            :disabled="followActionLoading.has(user.user_id)"
            @click="handleFollowBack(user.user_id)"
          >
            <UserPlus class="w-3.5 h-3.5 mr-1" />
            {{ t('social.followBack') }}
          </BaseButton>
          <BaseButton
            v-else
            size="sm"
            variant="secondary"
            :disabled="followActionLoading.has(user.user_id)"
            @click="handleUnfollow(user.user_id)"
          >
            <UserMinus class="w-3.5 h-3.5 mr-1" />
            {{ t('social.unfollow') }}
          </BaseButton>
        </div>
      </div>

      <BasePagination
        v-if="followersTotalPages > 1"
        :current-page="followersPage"
        :total-pages="followersTotalPages"
        class="mt-6"
        @update:current-page="goToFollowersPage"
      />
    </div>
  </div>
</template>

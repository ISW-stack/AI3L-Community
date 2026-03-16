<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import type { Friendship, FriendRequest } from '@/types/social'
import {
  listFriends,
  listFriendRequests,
  unfriend,
  acceptFriendRequest,
  rejectFriendRequest,
} from '@/api/social'
import { usePagination } from '@/composables/usePagination'
import { getErrorMessage } from '@/utils/error'
import { useToastStore } from '@/stores/toast'
import { useLocale } from '@/composables/useLocale'
import BaseAvatar from '@/components/base/BaseAvatar.vue'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseModal from '@/components/base/BaseModal.vue'
import BasePagination from '@/components/base/BasePagination.vue'
import SkeletonLoader from '@/components/SkeletonLoader.vue'
import EmptyState from '@/components/EmptyState.vue'
import FriendRequestCard from '@/components/social/FriendRequestCard.vue'
import BaseBreadcrumb from '@/components/base/BaseBreadcrumb.vue'
import { relativeTime } from '@/utils/datetime'
import { UserMinus } from 'lucide-vue-next'

const { t } = useLocale()
const toast = useToastStore()

const activeTab = ref<'friends' | 'requests'>('friends')

// Friends state
const friends = ref<Friendship[]>([])
const friendsLoading = ref(false)
const {
  page: friendsPage,
  totalPages: friendsTotalPages,
  pageSize: friendsPageSize,
  setPage: setFriendsPage,
  updateFromResponse: updateFriendsResponse,
} = usePagination()
let friendsFetchId = 0

// Requests state
const requests = ref<FriendRequest[]>([])
const requestsLoading = ref(false)
const incomingCount = ref(0)
const {
  page: requestsPage,
  totalPages: requestsTotalPages,
  pageSize: requestsPageSize,
  setPage: setRequestsPage,
  updateFromResponse: updateRequestsResponse,
} = usePagination()
let requestsFetchId = 0

// Unfriend confirmation
const showUnfriendConfirm = ref(false)
const unfriendTarget = ref<Friendship | null>(null)
const unfriendLoading = ref(false)

const incomingRequests = computed(() => requests.value.filter((r) => r.status === 'pending'))

async function fetchFriends() {
  const localId = ++friendsFetchId
  friendsLoading.value = true
  try {
    const data = await listFriends(friendsPage.value, friendsPageSize)
    if (localId !== friendsFetchId) return
    friends.value = data.friends
    updateFriendsResponse(data.total)
  } catch (e: unknown) {
    if (localId !== friendsFetchId) return
    toast.show(getErrorMessage(e, t('social.loadFriendsError')), 'error')
  } finally {
    if (localId === friendsFetchId) {
      friendsLoading.value = false
    }
  }
}

async function fetchRequests() {
  const localId = ++requestsFetchId
  requestsLoading.value = true
  try {
    const data = await listFriendRequests(requestsPage.value, requestsPageSize)
    if (localId !== requestsFetchId) return
    requests.value = data.requests
    updateRequestsResponse(data.total)
    incomingCount.value = data.requests.filter((r) => r.status === 'pending').length
  } catch (e: unknown) {
    if (localId !== requestsFetchId) return
    toast.show(getErrorMessage(e, t('social.loadRequestsError')), 'error')
  } finally {
    if (localId === requestsFetchId) {
      requestsLoading.value = false
    }
  }
}

function switchTab(tab: 'friends' | 'requests') {
  activeTab.value = tab
  if (tab === 'friends') {
    setFriendsPage(1)
    fetchFriends()
  } else {
    setRequestsPage(1)
    fetchRequests()
  }
}

function goToFriendsPage(p: number) {
  setFriendsPage(p)
  fetchFriends()
}

function goToRequestsPage(p: number) {
  setRequestsPage(p)
  fetchRequests()
}

function confirmUnfriend(friend: Friendship) {
  unfriendTarget.value = friend
  showUnfriendConfirm.value = true
}

async function handleUnfriend() {
  if (!unfriendTarget.value) return
  unfriendLoading.value = true
  try {
    await unfriend(unfriendTarget.value.user_id)
    friends.value = friends.value.filter((f) => f.id !== unfriendTarget.value!.id)
    toast.show(t('social.unfriendSuccess'), 'success')
    showUnfriendConfirm.value = false
    unfriendTarget.value = null
  } catch (e: unknown) {
    toast.show(getErrorMessage(e, t('social.unfriendError')), 'error')
  } finally {
    unfriendLoading.value = false
  }
}

async function handleAcceptRequest(requestId: string) {
  try {
    await acceptFriendRequest(requestId)
    requests.value = requests.value.filter((r) => r.id !== requestId)
    incomingCount.value = Math.max(0, incomingCount.value - 1)
    toast.show(t('social.acceptSuccess'), 'success')
    // Refresh friends list if on friends tab
    if (activeTab.value === 'friends') {
      fetchFriends()
    }
  } catch (e: unknown) {
    toast.show(getErrorMessage(e, t('social.acceptError')), 'error')
  }
}

async function handleRejectRequest(requestId: string) {
  try {
    await rejectFriendRequest(requestId)
    requests.value = requests.value.filter((r) => r.id !== requestId)
    incomingCount.value = Math.max(0, incomingCount.value - 1)
    toast.show(t('social.declineSuccess'), 'success')
  } catch (e: unknown) {
    toast.show(getErrorMessage(e, t('social.declineError')), 'error')
  }
}

onMounted(() => {
  fetchFriends()
  fetchRequests()
})
</script>

<template>
  <div class="max-w-3xl mx-auto">
    <BaseBreadcrumb
      :items="[{ label: t('breadcrumb.home'), to: '/' }, { label: t('breadcrumb.friends') }]"
    />
    <h1 class="text-2xl font-bold text-foreground mb-6">{{ t('social.friends') }}</h1>

    <!-- Tabs -->
    <div class="flex gap-1 mb-4 border-b border-border" role="tablist">
      <button
        id="tab-friends"
        role="tab"
        :aria-selected="activeTab === 'friends'"
        aria-controls="panel-friends"
        class="px-4 py-2 text-sm font-medium border-b-2 transition"
        :class="
          activeTab === 'friends'
            ? 'border-brand-600 text-brand-600'
            : 'border-transparent text-muted hover:text-foreground'
        "
        @click="switchTab('friends')"
      >
        {{ t('social.friends') }}
      </button>
      <button
        id="tab-requests"
        role="tab"
        :aria-selected="activeTab === 'requests'"
        aria-controls="panel-requests"
        class="px-4 py-2 text-sm font-medium border-b-2 transition"
        :class="
          activeTab === 'requests'
            ? 'border-brand-600 text-brand-600'
            : 'border-transparent text-muted hover:text-foreground'
        "
        @click="switchTab('requests')"
      >
        {{ t('social.requests') }}
        <span
          v-if="incomingCount > 0"
          class="ml-1 text-xs bg-brand-100 text-brand-700 rounded-full px-1.5"
        >
          {{ incomingCount }}
        </span>
      </button>
    </div>

    <!-- Friends Tab -->
    <div v-if="activeTab === 'friends'" id="panel-friends" role="tabpanel" aria-labelledby="tab-friends">
      <SkeletonLoader v-if="friendsLoading" :lines="5" variant="list" />

      <EmptyState
        v-else-if="friends.length === 0"
        :title="t('social.noFriends')"
        :message="t('social.noFriendsMessage')"
      />

      <div v-else class="bg-surface rounded-lg shadow border border-border divide-y divide-border">
        <div v-for="friend in friends" :key="friend.id" class="flex items-center gap-4 px-5 py-4">
          <router-link :to="`/users/${friend.user_id}`">
            <BaseAvatar :src="friend.avatar_url" :name="friend.display_name" size="md" />
          </router-link>

          <div class="flex-1 min-w-0">
            <router-link
              :to="`/users/${friend.user_id}`"
              class="text-sm font-semibold text-foreground hover:text-brand-600 hover:underline"
            >
              {{ friend.display_name }}
            </router-link>
            <p class="text-xs text-muted truncate">@{{ friend.username }}</p>
            <p v-if="friend.affiliation" class="text-xs text-muted truncate">
              {{ friend.affiliation }}
            </p>
          </div>

          <div class="flex items-center gap-2 shrink-0">
            <span class="text-xs text-muted hidden sm:inline">
              {{ t('social.friendsSince', { time: relativeTime(friend.created_at) }) }}
            </span>
            <BaseButton size="sm" variant="soft-danger" @click="confirmUnfriend(friend)">
              <UserMinus class="w-3.5 h-3.5 mr-1" />
              {{ t('social.unfriend') }}
            </BaseButton>
          </div>
        </div>
      </div>

      <BasePagination
        v-if="friendsTotalPages > 1"
        :current-page="friendsPage"
        :total-pages="friendsTotalPages"
        class="mt-6"
        @update:current-page="goToFriendsPage"
      />
    </div>

    <!-- Requests Tab -->
    <div v-if="activeTab === 'requests'" id="panel-requests" role="tabpanel" aria-labelledby="tab-requests">
      <SkeletonLoader v-if="requestsLoading" :lines="4" variant="list" />

      <EmptyState
        v-else-if="requests.length === 0"
        :title="t('social.noRequests')"
        :message="t('social.noRequestsMessage')"
      />

      <div v-else class="space-y-3">
        <!-- Incoming requests section -->
        <div v-if="incomingRequests.length > 0">
          <h3 class="text-sm font-semibold text-foreground mb-2">
            {{ t('social.incomingRequests') }}
          </h3>
          <div class="space-y-2">
            <FriendRequestCard
              v-for="req in incomingRequests"
              :key="req.id"
              :request="req"
              type="incoming"
              @accept="handleAcceptRequest"
              @reject="handleRejectRequest"
            />
          </div>
        </div>

        <!-- Outgoing requests section -->
        <div
          v-if="
            requests.filter((r) => r.status !== 'pending' || !incomingRequests.includes(r)).length >
            0
          "
        >
          <h3 class="text-sm font-semibold text-foreground mb-2 mt-4">
            {{ t('social.sentRequests') }}
          </h3>
          <div class="space-y-2">
            <FriendRequestCard
              v-for="req in requests.filter((r) => !incomingRequests.includes(r))"
              :key="req.id"
              :request="req"
              type="outgoing"
            />
          </div>
        </div>
      </div>

      <BasePagination
        v-if="requestsTotalPages > 1"
        :current-page="requestsPage"
        :total-pages="requestsTotalPages"
        class="mt-6"
        @update:current-page="goToRequestsPage"
      />
    </div>

    <!-- Unfriend confirmation modal -->
    <BaseModal v-model="showUnfriendConfirm" :title="t('social.removeFriend')" size="sm">
      <p class="text-sm text-muted">
        {{ t('social.removeFriendConfirm', { name: unfriendTarget?.display_name ?? '' }) }}
      </p>
      <template #footer>
        <BaseButton size="sm" variant="secondary" @click="showUnfriendConfirm = false">
          {{ t('common.cancel') }}
        </BaseButton>
        <BaseButton
          size="sm"
          variant="soft-danger"
          :loading="unfriendLoading"
          @click="handleUnfriend"
        >
          {{ t('social.unfriend') }}
        </BaseButton>
      </template>
    </BaseModal>
  </div>
</template>

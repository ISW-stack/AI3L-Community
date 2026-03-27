<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import type { RelationshipStatus } from '@/types/social'
import {
  sendFriendRequest,
  acceptFriendRequest,
  rejectFriendRequest,
  unfriend,
  followUser,
  unfollowUser,
  blockUser,
  unblockUser,
  getRelationshipStatus,
} from '@/api/social'
import { getErrorMessage } from '@/utils/error'
import { useToastStore } from '@/stores/toast'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseBadge from '@/components/base/BaseBadge.vue'
import BaseModal from '@/components/base/BaseModal.vue'
import { MoreVertical, UserPlus, UserMinus, UserX, Shield, ShieldOff } from 'lucide-vue-next'

const props = defineProps<{
  userId: string
  initialStatus?: RelationshipStatus
}>()

const toast = useToastStore()

const status = ref<RelationshipStatus | null>(props.initialStatus ?? null)
const loading = ref(false)
const actionLoading = ref(false)
const dropdownOpen = ref(false)
const showBlockConfirm = ref(false)
const showUnfriendConfirm = ref(false)

const isFriend = computed(() => status.value?.is_friend === true)
const isFollowing = computed(() => status.value?.is_following === true)
const isBlocked = computed(() => status.value?.is_blocked === true)
const pendingRequest = computed(() => status.value?.pending_request ?? null)

async function fetchStatus() {
  loading.value = true
  try {
    const data = await getRelationshipStatus(props.userId)
    status.value = data
  } catch (e: unknown) {
    toast.show(getErrorMessage(e, 'Failed to load relationship status'), 'error')
  } finally {
    loading.value = false
  }
}

async function handleSendFriendRequest() {
  actionLoading.value = true
  // Optimistic update
  if (status.value) {
    status.value = { ...status.value, pending_request: 'sent' }
  }
  try {
    await sendFriendRequest(props.userId)
    toast.show('Friend request sent', 'success')
  } catch (e: unknown) {
    // Rollback
    await fetchStatus()
    toast.show(getErrorMessage(e, 'Failed to send friend request'), 'error')
  } finally {
    actionLoading.value = false
  }
}

async function handleAcceptRequest() {
  if (!status.value?.friendship_id) return
  actionLoading.value = true
  try {
    await acceptFriendRequest(status.value.friendship_id)
    status.value = {
      ...status.value,
      is_friend: true,
      pending_request: null,
    }
    toast.show('Friend request accepted', 'success')
  } catch (e: unknown) {
    await fetchStatus()
    toast.show(getErrorMessage(e, 'Failed to accept friend request'), 'error')
  } finally {
    actionLoading.value = false
  }
}

async function handleRejectRequest() {
  if (!status.value?.friendship_id) return
  actionLoading.value = true
  try {
    await rejectFriendRequest(status.value.friendship_id)
    status.value = {
      ...status.value,
      pending_request: null,
    }
    toast.show('Friend request declined', 'success')
  } catch (e: unknown) {
    await fetchStatus()
    toast.show(getErrorMessage(e, 'Failed to decline friend request'), 'error')
  } finally {
    actionLoading.value = false
  }
}

async function handleUnfriend() {
  showUnfriendConfirm.value = false
  actionLoading.value = true
  try {
    await unfriend(props.userId)
    status.value = {
      ...status.value!,
      is_friend: false,
      friendship_id: null,
    }
    toast.show('Unfriended successfully', 'success')
  } catch (e: unknown) {
    await fetchStatus()
    toast.show(getErrorMessage(e, 'Failed to unfriend'), 'error')
  } finally {
    actionLoading.value = false
  }
}

async function handleFollowToggle() {
  if (!status.value) return
  actionLoading.value = true
  const wasFollowing = status.value.is_following
  // Optimistic update
  status.value = { ...status.value, is_following: !wasFollowing }
  try {
    if (wasFollowing) {
      await unfollowUser(props.userId)
      toast.show('Unfollowed', 'success')
    } else {
      await followUser(props.userId)
      toast.show('Following', 'success')
    }
  } catch (e: unknown) {
    // Rollback
    status.value = { ...status.value, is_following: wasFollowing }
    toast.show(getErrorMessage(e, 'Failed to update follow status'), 'error')
  } finally {
    actionLoading.value = false
  }
}

async function handleBlock() {
  showBlockConfirm.value = false
  dropdownOpen.value = false
  actionLoading.value = true
  try {
    await blockUser(props.userId)
    status.value = {
      is_friend: false,
      is_following: false,
      is_followed_by: false,
      is_blocked: true,
      pending_request: null,
      friendship_id: null,
    }
    toast.show('User blocked', 'success')
  } catch (e: unknown) {
    await fetchStatus()
    toast.show(getErrorMessage(e, 'Failed to block user'), 'error')
  } finally {
    actionLoading.value = false
  }
}

async function handleUnblock() {
  actionLoading.value = true
  try {
    await unblockUser(props.userId)
    status.value = {
      is_friend: false,
      is_following: false,
      is_followed_by: false,
      is_blocked: false,
      pending_request: null,
      friendship_id: null,
    }
    toast.show('User unblocked', 'success')
  } catch (e: unknown) {
    await fetchStatus()
    toast.show(getErrorMessage(e, 'Failed to unblock user'), 'error')
  } finally {
    actionLoading.value = false
  }
}

function openBlockConfirm() {
  dropdownOpen.value = false
  showBlockConfirm.value = true
}

function openUnfriendConfirm() {
  showUnfriendConfirm.value = true
}

function toggleDropdown() {
  dropdownOpen.value = !dropdownOpen.value
}

function closeDropdown() {
  dropdownOpen.value = false
}

watch(() => props.userId, fetchStatus)

onMounted(() => {
  if (!props.initialStatus) {
    fetchStatus()
  }
})
</script>

<template>
  <div class="flex flex-wrap items-center gap-2" data-testid="social-actions">
    <!-- Loading state -->
    <div v-if="loading" class="flex items-center gap-2">
      <div class="h-8 w-24 bg-gray-200 rounded-lg animate-pulse"></div>
      <div class="h-8 w-20 bg-gray-200 rounded-lg animate-pulse"></div>
    </div>

    <template v-else-if="status">
      <!-- Blocked state -->
      <template v-if="isBlocked">
        <BaseBadge variant="danger" size="md">
          <Shield class="w-3 h-3 mr-1" />
          Blocked
        </BaseBadge>
        <BaseButton size="sm" variant="secondary" :disabled="actionLoading" @click="handleUnblock">
          <ShieldOff class="w-3.5 h-3.5 mr-1" />
          Unblock
        </BaseButton>
      </template>

      <!-- Friend request received -->
      <template v-else-if="pendingRequest === 'received'">
        <BaseButton size="sm" :disabled="actionLoading" @click="handleAcceptRequest">
          Accept
        </BaseButton>
        <BaseButton
          size="sm"
          variant="secondary"
          :disabled="actionLoading"
          @click="handleRejectRequest"
        >
          Decline
        </BaseButton>
      </template>

      <!-- Normal states -->
      <template v-else>
        <!-- Friend status -->
        <template v-if="isFriend">
          <BaseBadge variant="success" size="md" class="cursor-default">Friends</BaseBadge>
          <BaseButton
            size="sm"
            variant="soft-danger"
            :disabled="actionLoading"
            @click="openUnfriendConfirm"
          >
            <UserMinus class="w-3.5 h-3.5 mr-1" />
            Unfriend
          </BaseButton>
        </template>

        <!-- Friend request sent -->
        <template v-else-if="pendingRequest === 'sent'">
          <BaseButton size="sm" variant="secondary" disabled>Request Sent</BaseButton>
        </template>

        <!-- No relationship -->
        <template v-else>
          <BaseButton size="sm" :disabled="actionLoading" @click="handleSendFriendRequest">
            <UserPlus class="w-3.5 h-3.5 mr-1" />
            Add Friend
          </BaseButton>
        </template>

        <!-- Follow/Unfollow -->
        <BaseButton
          size="sm"
          :variant="isFollowing ? 'secondary' : 'ghost'"
          :disabled="actionLoading"
          @click="handleFollowToggle"
        >
          {{ isFollowing ? 'Unfollow' : 'Follow' }}
        </BaseButton>
      </template>

      <!-- More menu (Block) -->
      <div v-if="!isBlocked" class="relative">
        <button
          class="p-1.5 rounded-lg text-muted hover:bg-surface-alt hover:text-foreground transition"
          aria-label="More actions"
          @click="toggleDropdown"
          @blur="closeDropdown"
        >
          <MoreVertical class="w-4 h-4" />
        </button>
        <div
          v-if="dropdownOpen"
          class="absolute right-0 mt-1 w-40 bg-surface rounded-lg shadow-lg border border-border py-1 z-10"
        >
          <button
            class="w-full text-left px-3 py-2 text-sm text-danger-600 hover:bg-surface-alt transition"
            @mousedown.prevent="openBlockConfirm"
          >
            <UserX class="w-4 h-4 inline mr-2" />
            Block User
          </button>
        </div>
      </div>
    </template>

    <!-- Block confirmation modal -->
    <BaseModal v-model="showBlockConfirm" title="Block User" size="sm">
      <p class="text-sm text-muted">
        Are you sure you want to block this user? This will remove any existing friendship and they
        will not be able to interact with you.
      </p>
      <template #footer>
        <BaseButton size="sm" variant="secondary" @click="showBlockConfirm = false">
          Cancel
        </BaseButton>
        <BaseButton size="sm" variant="danger" :loading="actionLoading" @click="handleBlock">
          Block
        </BaseButton>
      </template>
    </BaseModal>

    <!-- Unfriend confirmation modal -->
    <BaseModal v-model="showUnfriendConfirm" title="Remove Friend" size="sm">
      <p class="text-sm text-muted">
        Are you sure you want to remove this user from your friends list?
      </p>
      <template #footer>
        <BaseButton size="sm" variant="secondary" @click="showUnfriendConfirm = false">
          Cancel
        </BaseButton>
        <BaseButton
          size="sm"
          variant="soft-danger"
          :loading="actionLoading"
          @click="handleUnfriend"
        >
          Unfriend
        </BaseButton>
      </template>
    </BaseModal>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useToastStore } from '@/stores/toast'
import { useAlbumLayout } from '@/composables/useAlbumLayout'
import {
  listAlbumMembers,
  joinAlbum,
  removeAlbumMember,
  approveAlbumMember,
  addAlbumMember,
} from '@/api/albums'
import { getErrorMessage } from '@/utils/error'
import type { AlbumMember } from '@/types/album'
import SkeletonLoader from '@/components/SkeletonLoader.vue'
import EmptyState from '@/components/EmptyState.vue'
import BaseCard from '@/components/base/BaseCard.vue'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseBadge from '@/components/base/BaseBadge.vue'
import BaseAvatar from '@/components/base/BaseAvatar.vue'
import BaseModal from '@/components/base/BaseModal.vue'
import BaseInput from '@/components/base/BaseInput.vue'

const auth = useAuthStore()
const toast = useToastStore()
const { album, userAlbumRole } = useAlbumLayout()

const members = ref<AlbumMember[]>([])
const loading = ref(false)
const joining = ref(false)
const showAddMemberModal = ref(false)
const addMemberUserId = ref('')
const addingMember = ref(false)

const isAlbumAdmin = computed(() => userAlbumRole.value === 'ADMIN')
const isMember = computed(() => userAlbumRole.value !== null)
const canJoin = computed(() => auth.isAuthenticated && !auth.isGuest && !isMember.value)

const acceptedMembers = computed(() =>
  members.value.filter((m) => m.status === 'ACCEPTED'),
)

const pendingMembers = computed(() =>
  members.value.filter((m) => m.status === 'PENDING'),
)

async function fetchMembers() {
  if (!album.value) return
  loading.value = true
  try {
    const { data } = await listAlbumMembers(album.value.id)
    members.value = data.members
  } catch (e: unknown) {
    toast.show(getErrorMessage(e, 'Failed to load members'), 'error')
  } finally {
    loading.value = false
  }
}

async function handleJoin() {
  if (!album.value) return
  joining.value = true
  try {
    await joinAlbum(album.value.id)
    toast.show('Join request sent', 'success')
    await fetchMembers()
  } catch (e: unknown) {
    toast.show(getErrorMessage(e, 'Failed to join album'), 'error')
  } finally {
    joining.value = false
  }
}

async function handleLeave() {
  if (!album.value || !auth.user) return
  try {
    await removeAlbumMember(album.value.id, auth.user.id)
    toast.show('Left album', 'info')
    await fetchMembers()
  } catch (e: unknown) {
    toast.show(getErrorMessage(e, 'Failed to leave album'), 'error')
  }
}

async function handleApprove(member: AlbumMember) {
  if (!album.value) return
  try {
    await approveAlbumMember(album.value.id, member.id)
    toast.show('Member approved', 'success')
    await fetchMembers()
  } catch (e: unknown) {
    toast.show(getErrorMessage(e, 'Failed to approve member'), 'error')
  }
}

async function handleRemove(member: AlbumMember) {
  if (!album.value) return
  try {
    await removeAlbumMember(album.value.id, member.user_id)
    toast.show('Member removed', 'info')
    await fetchMembers()
  } catch (e: unknown) {
    toast.show(getErrorMessage(e, 'Failed to remove member'), 'error')
  }
}

function openAddMember() {
  addMemberUserId.value = ''
  showAddMemberModal.value = true
}

async function handleAddMember() {
  if (!album.value || !addMemberUserId.value.trim()) return
  addingMember.value = true
  try {
    await addAlbumMember(album.value.id, addMemberUserId.value.trim())
    toast.show('Member added', 'success')
    showAddMemberModal.value = false
    await fetchMembers()
  } catch (e: unknown) {
    toast.show(getErrorMessage(e, 'Failed to add member'), 'error')
  } finally {
    addingMember.value = false
  }
}

onMounted(fetchMembers)
watch(() => album.value?.id, fetchMembers)
</script>

<template>
  <div>
    <div class="flex justify-between items-center mb-4">
      <h2 class="text-lg font-semibold text-foreground">Members</h2>
      <div class="flex gap-2">
        <BaseButton v-if="canJoin" size="sm" :loading="joining" @click="handleJoin">
          Join Album
        </BaseButton>
        <BaseButton
          v-if="isMember && !isAlbumAdmin"
          size="sm"
          variant="secondary"
          @click="handleLeave"
        >
          Leave
        </BaseButton>
        <BaseButton v-if="isAlbumAdmin" size="sm" @click="openAddMember">
          Add Member
        </BaseButton>
      </div>
    </div>

    <SkeletonLoader v-if="loading" :lines="4" variant="card" />

    <EmptyState
      v-else-if="members.length === 0"
      title="No members"
      message="This album has no members yet."
    />

    <template v-else>
      <!-- Pending requests (admin only) -->
      <div v-if="isAlbumAdmin && pendingMembers.length > 0" class="mb-6">
        <h3 class="text-sm font-semibold text-foreground mb-3">
          Pending Requests ({{ pendingMembers.length }})
        </h3>
        <div class="space-y-2">
          <BaseCard v-for="member in pendingMembers" :key="member.id" class="!p-3">
            <div class="flex items-center justify-between gap-3">
              <div class="flex items-center gap-3 min-w-0">
                <BaseAvatar :src="member.avatar_url" :name="member.display_name" size="sm" />
                <div class="min-w-0">
                  <p class="text-sm font-medium text-foreground truncate">{{ member.display_name }}</p>
                  <p class="text-xs text-muted">@{{ member.username }}</p>
                </div>
              </div>
              <div class="flex gap-2 shrink-0">
                <BaseButton size="sm" @click="handleApprove(member)">Approve</BaseButton>
                <BaseButton size="sm" variant="soft-danger" @click="handleRemove(member)">Reject</BaseButton>
              </div>
            </div>
          </BaseCard>
        </div>
      </div>

      <!-- Accepted members -->
      <div class="space-y-2">
        <BaseCard v-for="member in acceptedMembers" :key="member.id" class="!p-3">
          <div class="flex items-center justify-between gap-3">
            <div class="flex items-center gap-3 min-w-0">
              <BaseAvatar :src="member.avatar_url" :name="member.display_name" size="sm" />
              <div class="min-w-0">
                <p class="text-sm font-medium text-foreground truncate">{{ member.display_name }}</p>
                <p class="text-xs text-muted">@{{ member.username }}</p>
              </div>
              <BaseBadge v-if="member.role === 'ADMIN'" variant="brand">Admin</BaseBadge>
            </div>
            <BaseButton
              v-if="isAlbumAdmin && member.user_id !== auth.user?.id"
              size="sm"
              variant="soft-danger"
              @click="handleRemove(member)"
            >
              Remove
            </BaseButton>
          </div>
        </BaseCard>
      </div>
    </template>

    <BaseModal
      v-model="showAddMemberModal"
      title="Add Member"
      size="sm"
    >
      <div class="space-y-4">
        <BaseInput
          v-model="addMemberUserId"
          label="User ID"
          placeholder="Enter user ID"
        />
      </div>
      <template #footer>
        <BaseButton variant="secondary" @click="showAddMemberModal = false">Cancel</BaseButton>
        <BaseButton :loading="addingMember" @click="handleAddMember">Add</BaseButton>
      </template>
    </BaseModal>
  </div>
</template>

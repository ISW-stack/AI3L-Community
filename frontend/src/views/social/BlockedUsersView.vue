<script setup lang="ts">
import { ref, onMounted } from 'vue'
import type { BlockedUser } from '@/types/social'
import { listBlocks, unblockUser } from '@/api/social'
import { usePagination } from '@/composables/usePagination'
import { relativeTime } from '@/utils/datetime'
import { getErrorMessage } from '@/utils/error'
import { useToastStore } from '@/stores/toast'
import BaseAvatar from '@/components/base/BaseAvatar.vue'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseAlert from '@/components/base/BaseAlert.vue'
import BaseModal from '@/components/base/BaseModal.vue'
import BasePagination from '@/components/base/BasePagination.vue'
import SkeletonLoader from '@/components/SkeletonLoader.vue'
import EmptyState from '@/components/EmptyState.vue'
import { ShieldOff } from 'lucide-vue-next'

const toast = useToastStore()

const blocks = ref<BlockedUser[]>([])
const loading = ref(false)
const { page, totalPages, pageSize, setPage, updateFromResponse } = usePagination()
let fetchId = 0

// Unblock confirmation
const showUnblockConfirm = ref(false)
const unblockTarget = ref<BlockedUser | null>(null)
const unblockLoading = ref(false)

async function fetchBlocks() {
  const localId = ++fetchId
  loading.value = true
  try {
    const { data } = await listBlocks(page.value, pageSize)
    if (localId !== fetchId) return
    blocks.value = data.blocks
    updateFromResponse(data.total)
  } catch (e: unknown) {
    if (localId !== fetchId) return
    toast.show(getErrorMessage(e, 'Failed to load blocked users'), 'error')
  } finally {
    if (localId === fetchId) {
      loading.value = false
    }
  }
}

function goToPage(p: number) {
  setPage(p)
  fetchBlocks()
}

function confirmUnblock(blocked: BlockedUser) {
  unblockTarget.value = blocked
  showUnblockConfirm.value = true
}

async function handleUnblock() {
  if (!unblockTarget.value) return
  unblockLoading.value = true
  try {
    await unblockUser(unblockTarget.value.blocked_id)
    blocks.value = blocks.value.filter((b) => b.id !== unblockTarget.value!.id)
    toast.show('User unblocked', 'success')
    showUnblockConfirm.value = false
    unblockTarget.value = null
  } catch (e: unknown) {
    toast.show(getErrorMessage(e, 'Failed to unblock user'), 'error')
  } finally {
    unblockLoading.value = false
  }
}

onMounted(fetchBlocks)
</script>

<template>
  <div class="max-w-3xl mx-auto">
    <h1 class="text-2xl font-bold text-foreground mb-4">Blocked Users</h1>

    <BaseAlert type="info" class="mb-6">
      You can block up to 5 users. Blocked users cannot send you friend requests, follow you, or
      interact with your content.
    </BaseAlert>

    <SkeletonLoader v-if="loading" :lines="3" variant="list" />

    <EmptyState
      v-else-if="blocks.length === 0"
      title="No blocked users"
      message="You have not blocked anyone."
    />

    <div
      v-else
      class="bg-surface rounded-lg shadow border border-border divide-y divide-border"
    >
      <div
        v-for="blocked in blocks"
        :key="blocked.id"
        class="flex items-center gap-4 px-5 py-4"
      >
        <BaseAvatar :src="blocked.avatar_url" :name="blocked.display_name" size="md" />

        <div class="flex-1 min-w-0">
          <p class="text-sm font-semibold text-foreground">{{ blocked.display_name }}</p>
          <p class="text-xs text-muted truncate">@{{ blocked.username }}</p>
          <p class="text-xs text-muted mt-0.5">
            Blocked {{ relativeTime(blocked.created_at) }}
          </p>
        </div>

        <BaseButton
          size="sm"
          variant="secondary"
          @click="confirmUnblock(blocked)"
        >
          <ShieldOff class="w-3.5 h-3.5 mr-1" />
          Unblock
        </BaseButton>
      </div>
    </div>

    <BasePagination
      v-if="totalPages > 1"
      :current-page="page"
      :total-pages="totalPages"
      class="mt-6"
      @update:current-page="goToPage"
    />

    <!-- Unblock confirmation modal -->
    <BaseModal v-model="showUnblockConfirm" title="Unblock User" size="sm">
      <p class="text-sm text-muted">
        Are you sure you want to unblock
        <strong class="text-foreground">{{ unblockTarget?.display_name }}</strong>?
        They will be able to interact with you again.
      </p>
      <template #footer>
        <BaseButton size="sm" variant="secondary" @click="showUnblockConfirm = false">
          Cancel
        </BaseButton>
        <BaseButton
          size="sm"
          :loading="unblockLoading"
          @click="handleUnblock"
        >
          Unblock
        </BaseButton>
      </template>
    </BaseModal>
  </div>
</template>

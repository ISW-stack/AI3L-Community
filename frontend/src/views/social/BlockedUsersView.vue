<script setup lang="ts">
import { ref, onMounted } from 'vue'
import type { BlockedUser } from '@/types/social'
import { listBlocks, unblockUser } from '@/api/social'
import { usePagination } from '@/composables/usePagination'
import { relativeTime } from '@/utils/datetime'
import { getErrorMessage } from '@/utils/error'
import { useToastStore } from '@/stores/toast'
import { useLocale } from '@/composables/useLocale'
import BaseAvatar from '@/components/base/BaseAvatar.vue'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseAlert from '@/components/base/BaseAlert.vue'
import BaseModal from '@/components/base/BaseModal.vue'
import BasePagination from '@/components/base/BasePagination.vue'
import SkeletonLoader from '@/components/SkeletonLoader.vue'
import EmptyState from '@/components/EmptyState.vue'
import BaseBreadcrumb from '@/components/base/BaseBreadcrumb.vue'
import { ShieldOff } from 'lucide-vue-next'

const { t } = useLocale()
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
    const result = await listBlocks(page.value, pageSize)
    if (localId !== fetchId) return
    blocks.value = result.blocks
    updateFromResponse(result.total)
  } catch (e: unknown) {
    if (localId !== fetchId) return
    toast.show(getErrorMessage(e, t('social.loadBlockedError')), 'error')
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
    toast.show(t('social.unblockSuccess'), 'success')
    showUnblockConfirm.value = false
    unblockTarget.value = null
  } catch (e: unknown) {
    toast.show(getErrorMessage(e, t('social.unblockError')), 'error')
  } finally {
    unblockLoading.value = false
  }
}

onMounted(fetchBlocks)
</script>

<template>
  <div class="max-w-3xl mx-auto">
    <BaseBreadcrumb
      :items="[{ label: t('breadcrumb.home'), to: '/' }, { label: t('breadcrumb.blockedUsers') }]"
    />
    <h1 class="text-2xl font-bold text-foreground mb-4">{{ t('social.blockedUsers') }}</h1>

    <BaseAlert type="info" class="mb-6">
      {{ t('social.blockLimitDescription') }}
    </BaseAlert>

    <SkeletonLoader v-if="loading" :lines="3" variant="list" />

    <EmptyState
      v-else-if="blocks.length === 0"
      :title="t('social.noBlocked')"
      :message="t('social.noBlockedMessage')"
    />

    <div v-else class="bg-surface rounded-lg shadow border border-border divide-y divide-border">
      <div v-for="blocked in blocks" :key="blocked.id" class="flex items-center gap-4 px-5 py-4">
        <BaseAvatar :src="blocked.avatar_url" :name="blocked.display_name" size="md" />

        <div class="flex-1 min-w-0">
          <p class="text-sm font-semibold text-foreground">{{ blocked.display_name }}</p>
          <p class="text-xs text-muted truncate">@{{ blocked.username }}</p>
          <p class="text-xs text-muted mt-0.5">
            {{ t('social.blocked', { time: relativeTime(blocked.created_at) }) }}
          </p>
        </div>

        <BaseButton size="sm" variant="secondary" @click="confirmUnblock(blocked)">
          <ShieldOff class="w-3.5 h-3.5 mr-1" />
          {{ t('social.unblock') }}
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
    <BaseModal v-model="showUnblockConfirm" :title="t('social.unblockUser')" size="sm">
      <p class="text-sm text-muted">
        {{ t('social.unblockConfirm', { name: unblockTarget?.display_name ?? '' }) }}
      </p>
      <template #footer>
        <BaseButton size="sm" variant="secondary" @click="showUnblockConfirm = false">
          {{ t('common.cancel') }}
        </BaseButton>
        <BaseButton size="sm" :loading="unblockLoading" @click="handleUnblock">
          {{ t('social.unblock') }}
        </BaseButton>
      </template>
    </BaseModal>
  </div>
</template>

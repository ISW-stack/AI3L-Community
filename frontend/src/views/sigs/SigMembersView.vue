<script setup lang="ts">
import { ref, onMounted, computed, watch } from 'vue'
import { useRoute } from 'vue-router'
import { formatDate } from '@/utils/date'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@/stores/auth'
import { useToastStore } from '@/stores/toast'
import { usePagination } from '@/composables/usePagination'
import { useSigLayout } from '@/composables/useSigLayout'
import {
  getSigMembers,
  removeMember as removeMemberApi,
  assignSubAdmin as assignSubAdminApi,
  demoteSubAdmin as demoteSubAdminApi,
} from '@/api/sigs'
import { getErrorMessage } from '@/utils/error'
import type { SigMember } from '@/types'
import BaseCard from '@/components/base/BaseCard.vue'
import BaseBreadcrumb from '@/components/base/BaseBreadcrumb.vue'
import BaseBadge from '@/components/base/BaseBadge.vue'
import BaseAvatar from '@/components/base/BaseAvatar.vue'
import BasePagination from '@/components/base/BasePagination.vue'
import SkeletonLoader from '@/components/SkeletonLoader.vue'
import EmptyState from '@/components/EmptyState.vue'
import BaseModal from '@/components/base/BaseModal.vue'
import BaseButton from '@/components/base/BaseButton.vue'

const { t, locale } = useI18n()
const route = useRoute()
const auth = useAuthStore()
const toastStore = useToastStore()

const PAGE_SIZE = 20

const sigId = computed(() => route.params.id as string)
const { sig, userSigRole, refreshSigRole } = useSigLayout()

const members = ref<SigMember[]>([])
const loading = ref(true)
const { page, total, totalPages, pageSize, setPage, updateFromResponse } = usePagination(PAGE_SIZE)

const confirmAction = ref<{ action: 'remove' | 'demote'; user: SigMember } | null>(null)
const showConfirmModal = computed({
  get: () => !!confirmAction.value,
  set: (v: boolean) => {
    if (!v) confirmAction.value = null
  },
})

const isSigOwner = computed(() => userSigRole?.value === 'ADMIN')
const isSigSubAdmin = computed(() => userSigRole?.value === 'SUB_ADMIN')
const canEdit = computed(() => auth.isAdmin || isSigOwner.value || isSigSubAdmin.value)

const memberRoleBadge: Record<string, 'orange' | 'purple' | 'brand'> = {
  ADMIN: 'orange',
  SUB_ADMIN: 'purple',
  MEMBER: 'brand',
}

async function fetchMembers() {
  loading.value = true
  try {
    const data = await getSigMembers(sigId.value, { page: page.value, page_size: pageSize })
    members.value = data.members
    updateFromResponse(data.total)
  } catch (e: unknown) {
    toastStore.show(getErrorMessage(e, t('sigs.members.fetchError')), 'error')
  } finally {
    loading.value = false
  }
}

function goToPage(p: number) {
  setPage(p)
  fetchMembers()
}

function canRemoveMember(m: SigMember) {
  if (m.user_id === auth.user?.id) return false
  // Platform admin can remove anyone
  if (auth.isAdmin) return true
  // SUB_ADMIN can only remove regular MEMBERs
  if (isSigSubAdmin.value) {
    return m.role === 'MEMBER'
  }
  // SIG ADMIN cannot remove other ADMINs
  if (m.role === 'ADMIN') return false
  return isSigOwner.value
}

function canAssignSubAdmin(m: SigMember) {
  if (m.role !== 'MEMBER') return false
  if (m.user_id === auth.user?.id) return false
  return auth.isAdmin || isSigOwner.value
}

function promptRemoveMember(user: SigMember) {
  confirmAction.value = { action: 'remove', user }
}

async function executeRemoveMember() {
  if (!confirmAction.value) return
  try {
    await removeMemberApi(sigId.value, confirmAction.value.user.user_id)
    await fetchMembers()
    await refreshSigRole?.()
    toastStore.show(t('sigs.members.removeSuccess'), 'info')
  } catch (e: unknown) {
    toastStore.show(getErrorMessage(e, t('sigs.members.removeError')), 'error')
  } finally {
    confirmAction.value = null
  }
}

function canDemoteMember(m: SigMember) {
  if (m.role !== 'SUB_ADMIN') return false
  if (m.user_id === auth.user?.id) return false
  return auth.isAdmin || userSigRole?.value === 'ADMIN'
}

function promptDemoteMember(user: SigMember) {
  confirmAction.value = { action: 'demote', user }
}

async function executeDemoteMember() {
  if (!confirmAction.value) return
  try {
    await demoteSubAdminApi(sigId.value, confirmAction.value.user.user_id)
    await fetchMembers()
    await refreshSigRole?.()
    toastStore.show(t('sigs.members.demoteSuccess'), 'info')
  } catch (e: unknown) {
    toastStore.show(getErrorMessage(e, t('sigs.members.demoteError')), 'error')
  } finally {
    confirmAction.value = null
  }
}

async function handleAssignSubAdmin(userId: string) {
  try {
    await assignSubAdminApi(sigId.value, userId)
    await fetchMembers()
    await refreshSigRole?.()
    toastStore.show(t('sigs.members.promoteSuccess'), 'success')
  } catch (e: unknown) {
    toastStore.show(getErrorMessage(e, t('sigs.members.promoteError')), 'error')
  }
}

onMounted(fetchMembers)

// Re-fetch when the current user's SIG role changes so action buttons and badges stay in sync.
watch(userSigRole, () => {
  fetchMembers()
})
</script>

<template>
  <div class="space-y-4">
    <BaseBreadcrumb
      :items="[
        { label: t('breadcrumb.home'), to: '/' },
        { label: t('breadcrumb.sigs'), to: '/sigs' },
        { label: sig?.name || '...', to: `/sigs/${sigId}` },
        { label: t('breadcrumb.members') },
      ]"
    />
    <h2 class="text-lg font-semibold text-foreground">
      {{ t('sigs.members.title') }} ({{ total }})
    </h2>

    <div v-if="loading" class="space-y-3">
      <SkeletonLoader variant="card" :lines="4" />
    </div>

    <EmptyState
      v-else-if="members.length === 0"
      :title="t('sigs.members.emptyTitle')"
      :message="t('sigs.members.emptyMessage')"
    />

    <div v-else class="space-y-4">
      <!-- Desktop Table View -->
      <div
        class="hidden md:block bg-surface border border-border rounded-xl overflow-hidden shadow-sm"
      >
        <table class="w-full text-sm">
          <thead class="bg-surface-alt border-b border-border">
            <tr>
              <th
                class="text-left px-6 py-4 font-semibold text-muted tracking-wider uppercase text-[10px]"
              >
                {{ t('sigs.members.tableHeader.name') }}
              </th>
              <th
                class="text-left px-6 py-4 font-semibold text-muted tracking-wider uppercase text-[10px]"
              >
                {{ t('sigs.members.tableHeader.username') }}
              </th>
              <th
                class="text-left px-6 py-4 font-semibold text-muted tracking-wider uppercase text-[10px]"
              >
                {{ t('sigs.members.tableHeader.role') }}
              </th>
              <th
                class="text-left px-6 py-4 font-semibold text-muted tracking-wider uppercase text-[10px]"
              >
                {{ t('sigs.members.tableHeader.joined') }}
              </th>
              <th
                v-if="canEdit"
                class="text-right px-6 py-4 font-semibold text-muted tracking-wider uppercase text-[10px]"
              >
                {{ t('sigs.members.tableHeader.actions') }}
              </th>
            </tr>
          </thead>
          <tbody class="divide-y divide-border">
            <tr v-for="m in members" :key="m.id" class="hover:bg-brand-50/30 transition-colors">
              <td class="px-6 py-4 whitespace-nowrap">
                <div class="flex items-center gap-3">
                  <router-link :to="`/users/${m.user_id}`">
                    <BaseAvatar :src="m.avatar_url" :name="m.display_name" size="sm" />
                  </router-link>
                  <router-link
                    :to="`/users/${m.user_id}`"
                    class="font-medium text-foreground hover:text-brand-600 transition-colors"
                  >
                    {{ m.display_name }}
                  </router-link>
                </div>
              </td>
              <td class="px-6 py-4 whitespace-nowrap text-muted">@{{ m.username }}</td>
              <td class="px-6 py-4 whitespace-nowrap">
                <BaseBadge :variant="memberRoleBadge[m.role] || 'brand'" size="sm">
                  {{ m.role.replace('_', ' ') }}
                </BaseBadge>
              </td>
              <td class="px-6 py-4 whitespace-nowrap text-xs text-muted">
                {{ formatDate(m.created_at, locale) }}
              </td>
              <td v-if="canEdit" class="px-6 py-4 whitespace-nowrap text-right space-x-3 text-xs">
                <button
                  v-if="canAssignSubAdmin(m)"
                  @click="handleAssignSubAdmin(m.user_id)"
                  class="text-brand-600 hover:text-brand-700 font-medium hover:underline"
                >
                  {{ t('sigs.members.promoteBtn') }}
                </button>
                <button
                  v-if="canDemoteMember(m)"
                  @click="promptDemoteMember(m)"
                  class="text-warning-600 hover:text-warning-700 font-medium hover:underline"
                >
                  {{ t('sigs.members.demoteBtn') }}
                </button>
                <button
                  v-if="canRemoveMember(m)"
                  @click="promptRemoveMember(m)"
                  class="text-danger-600 hover:text-danger-700 font-medium hover:underline"
                >
                  {{ t('sigs.members.removeBtn') }}
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Mobile Card View -->
      <div class="grid gap-3 md:hidden">
        <BaseCard v-for="m in members" :key="m.id" padding="md">
          <div class="flex items-start justify-between">
            <div class="flex items-center gap-3">
              <BaseAvatar :src="m.avatar_url" :name="m.display_name" size="md" />
              <div class="min-w-0">
                <router-link
                  :to="`/users/${m.user_id}`"
                  class="font-bold text-foreground hover:text-brand-600 block truncate"
                >
                  {{ m.display_name }}
                </router-link>
                <div class="text-xs text-muted">@{{ m.username }}</div>
              </div>
            </div>
            <BaseBadge :variant="memberRoleBadge[m.role] || 'brand'" size="sm">
              {{ m.role.replace('_', ' ') }}
            </BaseBadge>
          </div>

          <div class="mt-4 pt-3 border-t border-border flex items-center justify-between">
            <span class="text-[10px] text-muted">
              {{ t('sigs.members.tableHeader.joined') }}
              {{ formatDate(m.created_at, locale) }}
            </span>

            <div v-if="canEdit" class="flex gap-1">
              <button
                v-if="canAssignSubAdmin(m)"
                @click="handleAssignSubAdmin(m.user_id)"
                class="text-xs text-brand-600 font-medium px-2.5 py-1.5 rounded-md hover:bg-brand-50 active:bg-brand-100 transition touch-manipulation"
              >
                {{ t('sigs.members.promoteBtn') }}
              </button>
              <button
                v-if="canDemoteMember(m)"
                @click="promptDemoteMember(m)"
                class="text-xs text-warning-600 font-medium px-2.5 py-1.5 rounded-md hover:bg-warning-50 active:bg-warning-100 transition touch-manipulation"
              >
                {{ t('sigs.members.demoteBtn') }}
              </button>
              <button
                v-if="canRemoveMember(m)"
                @click="promptRemoveMember(m)"
                class="text-xs text-danger-600 font-medium px-2.5 py-1.5 rounded-md hover:bg-danger-50 active:bg-danger-100 transition touch-manipulation"
              >
                {{ t('sigs.members.removeBtn') }}
              </button>
            </div>
          </div>
        </BaseCard>
      </div>
    </div>
    <!-- Pagination -->
    <div v-if="totalPages > 1" class="mt-4">
      <BasePagination
        :current-page="page"
        :total-pages="totalPages"
        :page-size="pageSize"
        :total="total"
        @update:current-page="goToPage"
      />
    </div>

    <!-- Confirm Action Modal -->
    <BaseModal
      v-model="showConfirmModal"
      :title="
        confirmAction?.action === 'demote'
          ? t('sigs.members.demoteConfirm.title')
          : t('sigs.members.removeConfirm.title')
      "
      size="sm"
    >
      <p class="text-sm text-muted mb-4 leading-relaxed">
        {{
          confirmAction?.action === 'demote'
            ? t('sigs.members.demoteConfirm.message', {
                name: confirmAction?.user.display_name ?? '',
              })
            : t('sigs.members.removeConfirm.message', {
                name: confirmAction?.user.display_name ?? '',
              })
        }}
      </p>
      <template #footer>
        <BaseButton variant="secondary" @click="showConfirmModal = false">
          {{ t('common.cancel') }}
        </BaseButton>
        <BaseButton
          :variant="confirmAction?.action === 'demote' ? 'primary' : 'danger'"
          @click="
            confirmAction?.action === 'demote' ? executeDemoteMember() : executeRemoveMember()
          "
        >
          {{
            confirmAction?.action === 'demote'
              ? t('sigs.members.demoteConfirm.confirmBtn')
              : t('sigs.members.removeConfirm.confirmBtn')
          }}
        </BaseButton>
      </template>
    </BaseModal>
  </div>
</template>

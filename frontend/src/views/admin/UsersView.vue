<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@/stores/auth'
import { useToastStore } from '@/stores/toast'
import { usePagination } from '@/composables/usePagination'
import { getErrorMessage } from '@/utils/error'
import type { AdminUser } from '@/api/admin'
import {
  listUsers,
  createAccount as apiCreateAccount,
  changeRole as apiChangeRole,
  banUser,
  unbanUser as apiUnbanUser,
} from '@/api/admin'
import api from '@/composables/api'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseBadge from '@/components/base/BaseBadge.vue'
import BaseAlert from '@/components/base/BaseAlert.vue'
import BaseInput from '@/components/base/BaseInput.vue'
import BaseTextarea from '@/components/base/BaseTextarea.vue'
import BaseModal from '@/components/base/BaseModal.vue'
import BasePagination from '@/components/base/BasePagination.vue'
import SkeletonLoader from '@/components/SkeletonLoader.vue'
import EmptyState from '@/components/EmptyState.vue'
import BaseBreadcrumb from '@/components/base/BaseBreadcrumb.vue'

const { t } = useI18n()
const auth = useAuthStore()
const toast = useToastStore()

const users = ref<AdminUser[]>([])
const { page, total, totalPages, pageSize, setPage, resetPage, updateFromResponse } =
  usePagination()
const loading = ref(false)
const message = ref('')
const searchQuery = ref('')
let searchTimer: ReturnType<typeof setTimeout> | null = null

// Bulk selection
const selectedIds = ref<Set<string>>(new Set())
const bulkRole = ref('MEMBER')
const bulkLoading = ref(false)

const allSelected = computed({
  get: () => users.value.length > 0 && users.value.every((u) => selectedIds.value.has(u.id)),
  set: (v: boolean) => {
    if (v) {
      users.value.forEach((u) => {
        if (u.id !== auth.user?.id) selectedIds.value.add(u.id)
      })
    } else {
      selectedIds.value.clear()
    }
  },
})

function toggleSelect(userId: string) {
  if (selectedIds.value.has(userId)) selectedIds.value.delete(userId)
  else selectedIds.value.add(userId)
}

async function applyBulkRole() {
  if (selectedIds.value.size === 0) return
  bulkLoading.value = true
  try {
    const { data } = await api.put('/users/bulk-role', {
      user_ids: Array.from(selectedIds.value),
      role: bulkRole.value,
    })
    toast.show(
      t('admin.users.message.bulkRoleUpdated', {
        count: data.updated_count ?? selectedIds.value.size,
      }),
      'success',
    )
    selectedIds.value.clear()
    await fetchUsers()
  } catch (e: unknown) {
    toast.show(getErrorMessage(e, t('admin.users.message.bulkRoleFailed')), 'error')
  } finally {
    bulkLoading.value = false
  }
}

const showCreateModal = ref(false)
const newUsername = ref('')
const newPassword = ref('')
const newDisplayName = ref('')
const newRole = ref('MEMBER')
const creating = ref(false)

const showBanModal = ref(false)
const banTargetUser = ref<AdminUser | null>(null)
const banReason = ref('')
const banning = ref(false)

const roles = ['MEMBER', 'ADMIN', 'SUPER_ADMIN']
const roleKeyMap: Record<string, string> = {
  SUPER_ADMIN: 'common.role.superAdmin',
  ADMIN: 'common.role.admin',
  MEMBER: 'common.role.member',
  GUEST: 'common.role.guest',
}
const roleBadge: Record<string, 'danger' | 'orange' | 'brand' | 'neutral'> = {
  SUPER_ADMIN: 'danger',
  ADMIN: 'orange',
  MEMBER: 'brand',
  GUEST: 'neutral',
}

function onSearchInput() {
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    resetPage()
    fetchUsers()
  }, 300)
}

async function fetchUsers() {
  loading.value = true
  try {
    const params: { page: number; page_size: number; search?: string } = {
      page: page.value,
      page_size: pageSize,
    }
    if (searchQuery.value.trim()) params.search = searchQuery.value.trim()
    const data = await listUsers(params)
    users.value = data.users
    updateFromResponse(data.total)
  } catch {
    message.value = t('admin.users.message.loadFailed', 'Failed to load user list.')
  } finally {
    loading.value = false
  }
}

function goToPage(p: number) {
  setPage(p)
  fetchUsers()
}

async function changeRole(userId: string, newRole: string) {
  try {
    const updated = await apiChangeRole(userId, newRole)
    const idx = users.value.findIndex((u) => u.id === userId)
    if (idx >= 0) {
      users.value[idx] = { ...users.value[idx], role: updated.role }
    }
    message.value = t('admin.users.message.roleUpdated')
  } catch (e: unknown) {
    message.value = getErrorMessage(e, t('admin.users.message.roleFailed'))
  }
}

async function createAccount() {
  creating.value = true
  message.value = ''
  try {
    await apiCreateAccount({
      username: newUsername.value,
      password: newPassword.value,
      display_name: newDisplayName.value,
      role: newRole.value,
    })
    showCreateModal.value = false
    newUsername.value = ''
    newPassword.value = ''
    newDisplayName.value = ''
    newRole.value = 'MEMBER'
    message.value = t('admin.users.message.accountCreated')
    await fetchUsers()
  } catch (e: unknown) {
    message.value = getErrorMessage(e, t('admin.users.message.createFailed'))
  } finally {
    creating.value = false
  }
}

function openBanModal(user: AdminUser) {
  banTargetUser.value = user
  banReason.value = ''
  showBanModal.value = true
}

async function confirmBan() {
  if (!banTargetUser.value) return
  banning.value = true
  try {
    await banUser(banTargetUser.value.id, banReason.value)
    showBanModal.value = false
    message.value = t('admin.users.message.banned', { username: banTargetUser.value.username })
    await fetchUsers()
  } catch (e: unknown) {
    message.value = getErrorMessage(e, t('admin.users.message.banFailed'))
  } finally {
    banning.value = false
  }
}

async function handleUnban(user: AdminUser) {
  try {
    await apiUnbanUser(user.id)
    message.value = t('admin.users.message.unbanned', { username: user.username })
    await fetchUsers()
  } catch (e: unknown) {
    message.value = getErrorMessage(e, t('admin.users.message.unbanFailed'))
  }
}

onMounted(fetchUsers)
</script>

<template>
  <div>
    <BaseBreadcrumb
      :items="[
        { label: t('breadcrumb.admin'), to: '/admin' },
        { label: t('breadcrumb.userManagement') },
      ]"
    />
    <div class="flex justify-between items-center mb-6">
      <h1 class="text-2xl font-bold text-foreground">{{ t('admin.users.title') }}</h1>
      <BaseButton @click="showCreateModal = true">{{ t('admin.users.createButton') }}</BaseButton>
    </div>

    <!-- Search bar -->
    <div class="mb-4">
      <input
        v-model="searchQuery"
        type="text"
        :placeholder="t('admin.users.searchPlaceholder')"
        class="w-full sm:w-80 px-3 py-2 border border-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 text-foreground"
        @input="onSearchInput"
      />
    </div>

    <BaseAlert v-if="message" type="info" class="mb-4">{{ message }}</BaseAlert>

    <!-- Bulk action bar -->
    <div
      v-if="auth.isSuperAdmin && selectedIds.size > 0"
      class="mb-4 flex items-center gap-3 bg-brand-50 border border-brand-200 rounded-lg px-4 py-3"
    >
      <span class="text-sm text-foreground font-medium">{{
        t('admin.users.selectedCount', { count: selectedIds.size })
      }}</span>
      <select
        v-model="bulkRole"
        class="text-sm border border-border rounded px-2 py-1 focus:outline-none focus:ring-2 focus:ring-brand-500"
      >
        <option v-for="r in roles" :key="r" :value="r">{{ t(roleKeyMap[r]) }}</option>
      </select>
      <BaseButton size="sm" :loading="bulkLoading" @click="applyBulkRole">{{
        t('admin.users.bulkApplyRole')
      }}</BaseButton>
      <button class="text-sm text-muted hover:text-foreground" @click="selectedIds.clear()">
        {{ t('admin.users.bulkClear') }}
      </button>
    </div>

    <SkeletonLoader v-if="loading" :lines="5" variant="list" />

    <EmptyState
      v-else-if="users.length === 0"
      :title="t('admin.users.emptyTitle')"
      :message="t('admin.users.emptyMessage')"
    />

    <div v-else class="relative">
      <div class="bg-surface rounded-lg shadow overflow-hidden overflow-x-auto">
        <table class="w-full text-sm min-w-[700px]">
          <thead class="bg-surface-alt border-b border-border">
            <tr>
              <th v-if="auth.isSuperAdmin" class="px-4 py-3 w-10">
                <input
                  type="checkbox"
                  :checked="allSelected"
                  @change="allSelected = ($event.target as HTMLInputElement).checked"
                  class="rounded"
                />
              </th>
              <th class="text-left px-4 py-3 font-medium text-muted">
                {{ t('admin.users.table.username') }}
              </th>
              <th class="text-left px-4 py-3 font-medium text-muted">
                {{ t('admin.users.table.displayName') }}
              </th>
              <th class="text-left px-4 py-3 font-medium text-muted">
                {{ t('admin.users.table.role') }}
              </th>
              <th class="text-left px-4 py-3 font-medium text-muted">
                {{ t('admin.users.table.status') }}
              </th>
              <th v-if="auth.isSuperAdmin" class="text-left px-4 py-3 font-medium text-muted">
                {{ t('admin.users.table.actions') }}
              </th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="user in users"
              :key="user.id"
              class="border-b border-border last:border-0 hover:bg-surface-alt transition"
            >
              <td v-if="auth.isSuperAdmin" class="px-4 py-3 w-10">
                <input
                  v-if="user.id !== auth.user?.id"
                  type="checkbox"
                  :checked="selectedIds.has(user.id)"
                  @change="toggleSelect(user.id)"
                  class="rounded"
                />
              </td>
              <td class="px-4 py-3 text-foreground">{{ user.username }}</td>
              <td class="px-4 py-3 text-foreground">{{ user.display_name }}</td>
              <td class="px-4 py-3">
                <BaseBadge :variant="roleBadge[user.role] || 'neutral'">{{
                  t(roleKeyMap[user.role] || 'common.role.guest')
                }}</BaseBadge>
              </td>
              <td class="px-4 py-3">
                <BaseBadge v-if="user.is_banned" variant="danger" :title="user.ban_reason || ''">{{
                  t('admin.users.table.banned')
                }}</BaseBadge>
                <span v-else class="text-xs text-muted">{{ t('admin.users.table.active') }}</span>
              </td>
              <td v-if="auth.isSuperAdmin" class="px-4 py-3">
                <div class="flex items-center gap-2">
                  <select
                    v-if="user.id !== auth.user?.id"
                    :value="user.role"
                    @change="changeRole(user.id, ($event.target as HTMLSelectElement).value)"
                    class="text-xs border border-border rounded px-2 py-1 focus:outline-none focus:ring-2 focus:ring-brand-500"
                  >
                    <option v-for="r in roles" :key="r" :value="r">{{ t(roleKeyMap[r]) }}</option>
                  </select>
                  <span v-else class="text-xs text-muted">{{
                    t('admin.users.table.currentUser')
                  }}</span>

                  <template v-if="user.id !== auth.user?.id">
                    <BaseButton
                      v-if="!user.is_banned"
                      size="sm"
                      variant="soft-danger"
                      @click="openBanModal(user)"
                      >{{ t('admin.users.banBtn') }}</BaseButton
                    >
                    <BaseButton v-else size="sm" variant="success" @click="handleUnban(user)">{{
                      t('admin.users.unbanBtn')
                    }}</BaseButton>
                  </template>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <div
        class="absolute right-0 top-0 bottom-0 w-8 bg-gradient-to-l from-surface to-transparent pointer-events-none lg:hidden"
      ></div>
    </div>

    <div class="mt-4 flex items-center justify-between">
      <p class="text-sm text-muted">{{ t('admin.users.total', { count: total }) }}</p>
      <BasePagination
        v-if="totalPages > 1"
        :current-page="page"
        :total-pages="totalPages"
        @update:current-page="goToPage"
      />
    </div>

    <!-- Create account modal -->
    <BaseModal v-model="showCreateModal" :title="t('admin.users.createModal.title')" size="sm">
      <form @submit.prevent="createAccount" class="space-y-3">
        <BaseInput
          v-model="newUsername"
          :label="t('admin.users.createModal.usernameLabel')"
          required
          :placeholder="t('admin.users.createModal.usernamePlaceholder')"
        />
        <BaseInput
          v-model="newDisplayName"
          :label="t('admin.users.createModal.displayNameLabel')"
          required
          :placeholder="t('admin.users.createModal.displayNamePlaceholder')"
        />
        <BaseInput
          v-model="newPassword"
          :label="t('admin.users.createModal.passwordLabel')"
          type="password"
          required
          :placeholder="t('admin.users.createModal.passwordPlaceholder')"
        />
        <div>
          <label class="block text-sm font-medium text-foreground mb-1">{{
            t('admin.users.createModal.roleLabel')
          }}</label>
          <select
            v-model="newRole"
            class="w-full px-3 py-2 border border-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
          >
            <option value="MEMBER">{{ t('admin.users.createModal.roleMember') }}</option>
            <option v-if="auth.isSuperAdmin" value="ADMIN">
              {{ t('admin.users.createModal.roleAdmin') }}
            </option>
          </select>
        </div>
      </form>
      <template #footer>
        <BaseButton variant="secondary" @click="showCreateModal = false">{{
          t('common.cancel')
        }}</BaseButton>
        <BaseButton :loading="creating" @click="createAccount">{{ t('common.create') }}</BaseButton>
      </template>
    </BaseModal>

    <!-- Ban user modal -->
    <BaseModal v-model="showBanModal" :title="t('admin.users.banModal.title')" size="sm">
      <p class="text-sm text-muted mb-4">
        {{ t('admin.users.banModal.message', { username: banTargetUser?.username }) }}
      </p>
      <form @submit.prevent="confirmBan">
        <BaseTextarea
          v-model="banReason"
          :label="t('admin.users.banModal.reasonLabel')"
          required
          :rows="3"
          :placeholder="t('admin.users.banModal.reasonPlaceholder')"
        />
      </form>
      <template #footer>
        <BaseButton variant="secondary" @click="showBanModal = false">{{
          t('common.cancel')
        }}</BaseButton>
        <BaseButton variant="danger" :loading="banning" @click="confirmBan">{{
          t('admin.users.banModal.confirmBtn')
        }}</BaseButton>
      </template>
    </BaseModal>
  </div>
</template>

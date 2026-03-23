<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@/stores/auth'
import { useToastStore } from '@/stores/toast'
import { useFetchPaginated } from '@/composables/useFetchPaginated'
import { getErrorMessage } from '@/utils/error'
import type { AdminUser } from '@/api/admin'
import {
  listUsers,
  createAccount as apiCreateAccount,
  changeRole as apiChangeRole,
  bulkChangeRole as apiBulkChangeRole,
  banUser,
  unbanUser as apiUnbanUser,
  deleteUser as apiDeleteUser,
} from '@/api/admin'
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

const searchQuery = ref('')
let searchTimer: ReturnType<typeof setTimeout> | null = null

const {
  items: users,
  loading,
  error: fetchError,
  page,
  total,
  totalPages,
  fetchPage: fetchUsers,
  setPage,
  resetPage,
} = useFetchPaginated<AdminUser>(async (p, ps) => {
  const params: { page: number; page_size: number; search?: string } = {
    page: p,
    page_size: ps,
  }
  if (searchQuery.value.trim()) params.search = searchQuery.value.trim()
  const data = await listUsers(params)
  return { items: data.users, total: data.total }
})

const message = ref('')

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

const showBulkRoleConfirm = ref(false)

function applyBulkRole() {
  if (selectedIds.value.size === 0) return
  showBulkRoleConfirm.value = true
}

async function confirmBulkRole() {
  showBulkRoleConfirm.value = false
  bulkLoading.value = true
  try {
    const data = await apiBulkChangeRole(Array.from(selectedIds.value), bulkRole.value)
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
const newPasswordError = ref<string | null>(null)
const newDisplayName = ref('')
const newRole = ref('MEMBER')
const creating = ref(false)

function validatePassword(pw: string): string | null {
  if (pw.length < 8) return t('admin.users.createModal.passwordTooShort')
  if (!/[A-Z]/.test(pw)) return t('admin.users.createModal.passwordNeedsUpper')
  if (!/[a-z]/.test(pw)) return t('admin.users.createModal.passwordNeedsLower')
  if (!/[0-9]/.test(pw)) return t('admin.users.createModal.passwordNeedsDigit')
  if (!/[^A-Za-z0-9]/.test(pw)) return t('admin.users.createModal.passwordNeedsSpecial')
  return null
}

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
  newPasswordError.value = validatePassword(newPassword.value)
  if (newPasswordError.value) return
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

const showDeleteModal = ref(false)
const deleteTargetUser = ref<AdminUser | null>(null)
const deleteReason = ref('')
const deleteConfirmText = ref('')
const deleting = ref(false)

function openDeleteModal(user: AdminUser) {
  deleteTargetUser.value = user
  deleteReason.value = ''
  deleteConfirmText.value = ''
  showDeleteModal.value = true
}

async function confirmDelete() {
  if (!deleteTargetUser.value || deleteConfirmText.value !== 'DELETE') return
  deleting.value = true
  try {
    await apiDeleteUser(deleteTargetUser.value.id, deleteReason.value)
    showDeleteModal.value = false
    toast.show(
      t('admin.users.message.deleted', { username: deleteTargetUser.value.username }),
      'success',
    )
    await fetchUsers()
  } catch (e: unknown) {
    toast.show(getErrorMessage(e, t('admin.users.message.deleteFailed')), 'error')
  } finally {
    deleting.value = false
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

onUnmounted(() => {
  if (searchTimer) {
    clearTimeout(searchTimer)
    searchTimer = null
  }
})
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
        name="search"
        :placeholder="t('admin.users.searchPlaceholder')"
        class="w-full sm:w-80 px-3 py-2 border border-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 text-foreground"
        @input="onSearchInput"
      />
    </div>

    <BaseAlert v-if="fetchError" type="error" class="mb-4">{{ fetchError }}</BaseAlert>
    <BaseAlert v-if="message" type="info" class="mb-4">{{ message }}</BaseAlert>

    <!-- Bulk action bar -->
    <div
      v-if="auth.isSuperAdmin && selectedIds.size > 0"
      class="mb-4 flex flex-col sm:flex-row sm:flex-wrap items-start sm:items-center gap-2 sm:gap-3 bg-brand-50 border border-brand-200 rounded-lg px-4 py-3"
    >
      <span class="text-sm text-foreground font-medium">{{
        t('admin.users.selectedCount', { count: selectedIds.size })
      }}</span>
      <select
        v-model="bulkRole"
        name="bulk-role"
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
      <!-- Mobile card view -->
      <div class="grid gap-3 md:hidden">
        <div
          v-for="user in users"
          :key="'mobile-' + user.id"
          class="bg-surface rounded-lg shadow border border-border p-4"
        >
          <div class="flex items-start justify-between gap-2">
            <div class="min-w-0">
              <div class="flex items-center gap-2 flex-wrap">
                <input
                  v-if="auth.isSuperAdmin && user.id !== auth.user?.id"
                  type="checkbox"
                  name="select-user"
                  :checked="selectedIds.has(user.id)"
                  @change="toggleSelect(user.id)"
                  class="rounded shrink-0"
                />
                <span class="font-medium text-foreground truncate">{{ user.display_name }}</span>
              </div>
              <div class="text-xs text-muted mt-0.5">@{{ user.username }}</div>
            </div>
            <BaseBadge :variant="roleBadge[user.role] || 'neutral'" class="shrink-0">
              {{ t(roleKeyMap[user.role] || 'common.role.guest') }}
            </BaseBadge>
          </div>
          <div class="mt-3 pt-3 border-t border-border flex items-center justify-between gap-2">
            <div>
              <BaseBadge v-if="user.is_banned" variant="danger" :title="user.ban_reason || ''">
                {{ t('admin.users.table.banned') }}
              </BaseBadge>
              <span v-else class="text-xs text-muted">{{ t('admin.users.table.active') }}</span>
            </div>
            <div
              v-if="auth.isSuperAdmin && user.id !== auth.user?.id"
              class="flex items-center gap-2"
            >
              <select
                :value="user.role"
                name="user-role"
                @change="changeRole(user.id, ($event.target as HTMLSelectElement).value)"
                class="text-xs border border-border rounded px-2 py-1 focus:outline-none focus:ring-2 focus:ring-brand-500"
              >
                <option v-for="r in roles" :key="r" :value="r">{{ t(roleKeyMap[r]) }}</option>
              </select>
              <BaseButton
                v-if="!user.is_banned"
                size="sm"
                variant="soft-danger"
                @click="openBanModal(user)"
                >{{ t('admin.users.banBtn') }}</BaseButton
              >
              <BaseButton v-else size="sm" variant="success" @click="handleUnban(user)">
                {{ t('admin.users.unbanBtn') }}
              </BaseButton>
              <BaseButton size="sm" variant="danger" @click="openDeleteModal(user)">{{
                t('admin.users.deleteBtn')
              }}</BaseButton>
            </div>
          </div>
        </div>
      </div>

      <!-- Desktop table view -->
      <div class="hidden md:block bg-surface rounded-lg shadow overflow-hidden overflow-x-auto">
        <table class="w-full text-sm min-w-[700px]">
          <thead class="bg-surface-alt border-b border-border">
            <tr>
              <th v-if="auth.isSuperAdmin" class="px-4 py-3 w-10 sticky left-0 z-10 bg-surface-alt">
                <input
                  type="checkbox"
                  name="select-all"
                  :checked="allSelected"
                  @change="allSelected = ($event.target as HTMLInputElement).checked"
                  class="rounded"
                />
              </th>
              <th
                class="text-left px-4 py-3 font-medium text-muted sticky z-10 bg-surface-alt shadow-[2px_0_4px_-1px_rgba(0,0,0,0.08)]"
                :class="auth.isSuperAdmin ? 'left-10' : 'left-0'"
              >
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
              class="group border-b border-border last:border-0 hover:bg-surface-alt transition"
            >
              <td
                v-if="auth.isSuperAdmin"
                class="px-4 py-3 w-10 sticky left-0 z-10 bg-surface group-hover:bg-surface-alt transition"
              >
                <input
                  v-if="user.id !== auth.user?.id"
                  type="checkbox"
                  name="select-user"
                  :checked="selectedIds.has(user.id)"
                  @change="toggleSelect(user.id)"
                  class="rounded"
                />
              </td>
              <td
                class="px-4 py-3 text-foreground sticky z-10 bg-surface group-hover:bg-surface-alt transition shadow-[2px_0_4px_-1px_rgba(0,0,0,0.08)]"
                :class="auth.isSuperAdmin ? 'left-10' : 'left-0'"
              >
                {{ user.username }}
              </td>
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
                    name="user-role"
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
                    <BaseButton size="sm" variant="danger" @click="openDeleteModal(user)">{{
                      t('admin.users.deleteBtn')
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
        <div>
          <BaseInput
            v-model="newPassword"
            :label="t('admin.users.createModal.passwordLabel')"
            type="password"
            required
            :placeholder="t('admin.users.createModal.passwordPlaceholder')"
            :error="newPasswordError ?? undefined"
            @update:model-value="newPasswordError = null"
          />
        </div>
        <div>
          <label for="new-user-role" class="block text-sm font-medium text-foreground mb-1">{{
            t('admin.users.createModal.roleLabel')
          }}</label>
          <select
            id="new-user-role"
            v-model="newRole"
            name="new-user-role"
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

    <!-- Bulk Role Confirmation Modal -->
    <BaseModal v-model="showBulkRoleConfirm" :title="t('admin.users.bulkApplyRole')" size="sm">
      <p class="text-sm text-muted">
        {{ t('admin.users.confirmBulkRole', { role: bulkRole, count: selectedIds.size }) }}
      </p>
      <template #footer>
        <BaseButton variant="secondary" @click="showBulkRoleConfirm = false">{{
          t('common.cancel')
        }}</BaseButton>
        <BaseButton variant="danger" :loading="bulkLoading" @click="confirmBulkRole">{{
          t('common.confirm')
        }}</BaseButton>
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

    <!-- Delete user modal -->
    <BaseModal v-model="showDeleteModal" :title="t('admin.users.deleteModal.title')" size="sm">
      <p class="text-sm text-muted mb-4">
        {{ t('admin.users.deleteModal.message', { username: deleteTargetUser?.username }) }}
      </p>
      <BaseTextarea
        v-model="deleteReason"
        :label="t('admin.users.deleteModal.reasonLabel')"
        :rows="2"
        :placeholder="t('admin.users.deleteModal.reasonPlaceholder')"
      />
      <BaseInput
        v-model="deleteConfirmText"
        :label="t('admin.users.deleteModal.typeLabel')"
        placeholder="DELETE"
        class="mt-3"
      />
      <template #footer>
        <BaseButton variant="secondary" @click="showDeleteModal = false">{{
          t('common.cancel')
        }}</BaseButton>
        <BaseButton
          variant="danger"
          :loading="deleting"
          :disabled="deleteConfirmText !== 'DELETE'"
          @click="confirmDelete"
          >{{ t('admin.users.deleteModal.confirmBtn') }}</BaseButton
        >
      </template>
    </BaseModal>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
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
    await api.put('/users/bulk-role', {
      user_ids: Array.from(selectedIds.value),
      role: bulkRole.value,
    })
    toast.show(`Role updated for ${selectedIds.value.size} user(s).`, 'success')
    selectedIds.value.clear()
    await fetchUsers()
  } catch (e: unknown) {
    toast.show(getErrorMessage(e, 'Bulk role update failed.'), 'error')
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
const roleLabels: Record<string, string> = {
  SUPER_ADMIN: 'Super Admin',
  ADMIN: 'Admin',
  MEMBER: 'Member',
  GUEST: 'Guest',
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
    message.value = 'Failed to load user list.'
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
    await apiChangeRole(userId, newRole)
    message.value = 'Role updated successfully.'
    await fetchUsers()
  } catch (e: unknown) {
    message.value = getErrorMessage(e, 'Failed to update role.')
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
    message.value = 'Account created successfully.'
    await fetchUsers()
  } catch (e: unknown) {
    message.value = getErrorMessage(e, 'Failed to create account.')
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
    message.value = `${banTargetUser.value.username} has been banned.`
    await fetchUsers()
  } catch (e: unknown) {
    message.value = getErrorMessage(e, 'Failed to ban user.')
  } finally {
    banning.value = false
  }
}

async function handleUnban(user: AdminUser) {
  try {
    await apiUnbanUser(user.id)
    message.value = `${user.username} has been unbanned.`
    await fetchUsers()
  } catch (e: unknown) {
    message.value = getErrorMessage(e, 'Failed to unban user.')
  }
}

onMounted(fetchUsers)
</script>

<template>
  <div>
    <div class="flex justify-between items-center mb-6">
      <h1 class="text-2xl font-bold text-foreground">User Management</h1>
      <BaseButton @click="showCreateModal = true">Create Account</BaseButton>
    </div>

    <!-- Search bar -->
    <div class="mb-4">
      <input
        v-model="searchQuery"
        type="text"
        placeholder="Search by username or display name..."
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
      <span class="text-sm text-foreground font-medium">{{ selectedIds.size }} selected</span>
      <select
        v-model="bulkRole"
        class="text-sm border border-border rounded px-2 py-1 focus:outline-none focus:ring-2 focus:ring-brand-500"
      >
        <option v-for="r in roles" :key="r" :value="r">{{ roleLabels[r] }}</option>
      </select>
      <BaseButton size="sm" :loading="bulkLoading" @click="applyBulkRole">Apply Role</BaseButton>
      <button class="text-sm text-muted hover:text-foreground" @click="selectedIds.clear()">
        Clear
      </button>
    </div>

    <SkeletonLoader v-if="loading" :lines="5" variant="list" />

    <EmptyState
      v-else-if="users.length === 0"
      title="No Users"
      message="No users found matching your search."
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
              <th class="text-left px-4 py-3 font-medium text-muted">Username</th>
              <th class="text-left px-4 py-3 font-medium text-muted">Display Name</th>
              <th class="text-left px-4 py-3 font-medium text-muted">Role</th>
              <th class="text-left px-4 py-3 font-medium text-muted">Status</th>
              <th v-if="auth.isSuperAdmin" class="text-left px-4 py-3 font-medium text-muted">
                Actions
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
                  roleLabels[user.role] || user.role
                }}</BaseBadge>
              </td>
              <td class="px-4 py-3">
                <BaseBadge v-if="user.is_banned" variant="danger" :title="user.ban_reason || ''"
                  >Banned</BaseBadge
                >
                <span v-else class="text-xs text-muted">Active</span>
              </td>
              <td v-if="auth.isSuperAdmin" class="px-4 py-3">
                <div class="flex items-center gap-2">
                  <select
                    v-if="user.id !== auth.user?.id"
                    :value="user.role"
                    @change="changeRole(user.id, ($event.target as HTMLSelectElement).value)"
                    class="text-xs border border-border rounded px-2 py-1 focus:outline-none focus:ring-2 focus:ring-brand-500"
                  >
                    <option v-for="r in roles" :key="r" :value="r">{{ roleLabels[r] }}</option>
                  </select>
                  <span v-else class="text-xs text-muted">Current user</span>

                  <template v-if="user.id !== auth.user?.id">
                    <BaseButton
                      v-if="!user.is_banned"
                      size="sm"
                      variant="soft-danger"
                      @click="openBanModal(user)"
                      >Ban</BaseButton
                    >
                    <BaseButton v-else size="sm" variant="success" @click="handleUnban(user)"
                      >Unban</BaseButton
                    >
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
      <p class="text-sm text-muted">{{ total }} users total</p>
      <BasePagination
        v-if="totalPages > 1"
        :current-page="page"
        :total-pages="totalPages"
        @update:current-page="goToPage"
      />
    </div>

    <!-- Create account modal -->
    <BaseModal v-model="showCreateModal" title="Create Account" size="sm">
      <form @submit.prevent="createAccount" class="space-y-3">
        <BaseInput v-model="newUsername" label="Username" required placeholder="Username" />
        <BaseInput
          v-model="newDisplayName"
          label="Display Name"
          required
          placeholder="Display Name"
        />
        <BaseInput
          v-model="newPassword"
          label="Password"
          type="password"
          required
          placeholder="8+ chars, upper/lower/digit"
        />
        <div>
          <label class="block text-sm font-medium text-foreground mb-1">Role</label>
          <select
            v-model="newRole"
            class="w-full px-3 py-2 border border-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
          >
            <option value="MEMBER">Member</option>
            <option v-if="auth.isSuperAdmin" value="ADMIN">Admin</option>
          </select>
        </div>
      </form>
      <template #footer>
        <BaseButton variant="secondary" @click="showCreateModal = false">Cancel</BaseButton>
        <BaseButton :loading="creating" @click="createAccount">Create</BaseButton>
      </template>
    </BaseModal>

    <!-- Ban user modal -->
    <BaseModal v-model="showBanModal" title="Ban User" size="sm">
      <p class="text-sm text-muted mb-4">
        Ban <strong class="text-foreground">{{ banTargetUser?.username }}</strong
        >? This will immediately revoke their session.
      </p>
      <form @submit.prevent="confirmBan">
        <BaseTextarea
          v-model="banReason"
          label="Reason for ban"
          required
          :rows="3"
          placeholder="Reason for ban"
        />
      </form>
      <template #footer>
        <BaseButton variant="secondary" @click="showBanModal = false">Cancel</BaseButton>
        <BaseButton variant="danger" :loading="banning" @click="confirmBan">Confirm Ban</BaseButton>
      </template>
    </BaseModal>
  </div>
</template>

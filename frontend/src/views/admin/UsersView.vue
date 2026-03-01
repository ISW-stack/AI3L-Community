<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import type { AdminUser } from '@/api/admin'
import {
  listUsers,
  createAccount as apiCreateAccount,
  changeRole as apiChangeRole,
  banUser,
  unbanUser as apiUnbanUser,
} from '@/api/admin'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseBadge from '@/components/base/BaseBadge.vue'
import BaseAlert from '@/components/base/BaseAlert.vue'
import BaseInput from '@/components/base/BaseInput.vue'
import BaseTextarea from '@/components/base/BaseTextarea.vue'
import BaseModal from '@/components/base/BaseModal.vue'

const auth = useAuthStore()

const users = ref<AdminUser[]>([])
const total = ref(0)
const loading = ref(false)
const message = ref('')

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

async function fetchUsers() {
  loading.value = true
  try {
    const data = await listUsers({ limit: 100 })
    users.value = data.users
    total.value = data.total
  } catch {
    message.value = 'Failed to load user list.'
  } finally {
    loading.value = false
  }
}

async function changeRole(userId: string, newRole: string) {
  try {
    await apiChangeRole(userId, newRole)
    message.value = 'Role updated successfully.'
    await fetchUsers()
  } catch (e: any) {
    const detail = e.response?.data?.detail
    message.value =
      typeof detail === 'object' ? detail?.message : detail || 'Failed to update role.'
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
  } catch (e: any) {
    const detail = e.response?.data?.detail
    message.value =
      typeof detail === 'object' ? detail?.message : detail || 'Failed to create account.'
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
  } catch (e: any) {
    const detail = e.response?.data?.detail
    message.value = typeof detail === 'object' ? detail?.message : detail || 'Failed to ban user.'
  } finally {
    banning.value = false
  }
}

async function handleUnban(user: AdminUser) {
  try {
    await apiUnbanUser(user.id)
    message.value = `${user.username} has been unbanned.`
    await fetchUsers()
  } catch (e: any) {
    const detail = e.response?.data?.detail
    message.value = typeof detail === 'object' ? detail?.message : detail || 'Failed to unban user.'
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

    <BaseAlert v-if="message" type="info" class="mb-4">{{ message }}</BaseAlert>

    <div class="bg-surface rounded-lg shadow overflow-hidden overflow-x-auto">
      <table class="w-full text-sm min-w-[700px]">
        <thead class="bg-surface-alt border-b border-border">
          <tr>
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
          <tr v-if="loading">
            <td colspan="5" class="px-4 py-8 text-center text-muted">Loading...</td>
          </tr>
          <tr
            v-for="user in users"
            :key="user.id"
            class="border-b border-border last:border-0 hover:bg-surface-alt transition"
          >
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

    <p class="mt-4 text-sm text-muted">{{ total }} users total</p>

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

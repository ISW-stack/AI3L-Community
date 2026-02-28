<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import api from '@/composables/api'

const auth = useAuthStore()

interface User {
  id: string
  username: string
  display_name: string
  role: string
  is_banned: boolean
  ban_reason: string | null
}

const users = ref<User[]>([])
const total = ref(0)
const loading = ref(false)
const message = ref('')

// Create account modal
const showCreateModal = ref(false)
const newUsername = ref('')
const newPassword = ref('')
const newDisplayName = ref('')
const newRole = ref('MEMBER')
const creating = ref(false)

// Ban modal
const showBanModal = ref(false)
const banTargetUser = ref<User | null>(null)
const banReason = ref('')
const banning = ref(false)

const roles = ['MEMBER', 'ADMIN', 'SUPER_ADMIN']
const roleLabels: Record<string, string> = {
  SUPER_ADMIN: 'Super Admin',
  ADMIN: 'Admin',
  MEMBER: 'Member',
  GUEST: 'Guest',
}

async function fetchUsers() {
  loading.value = true
  try {
    const { data } = await api.get('/users', { params: { limit: 100 } })
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
    await api.put(`/users/${userId}/role`, { role: newRole })
    message.value = 'Role updated successfully.'
    await fetchUsers()
  } catch (e: any) {
    const detail = e.response?.data?.detail
    message.value = typeof detail === 'object' ? detail?.message : detail || 'Failed to update role.'
  }
}

async function createAccount() {
  creating.value = true
  message.value = ''
  try {
    await api.post('/users/admin/create-account', {
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
    message.value = typeof detail === 'object' ? detail?.message : detail || 'Failed to create account.'
  } finally {
    creating.value = false
  }
}

function openBanModal(user: User) {
  banTargetUser.value = user
  banReason.value = ''
  showBanModal.value = true
}

async function confirmBan() {
  if (!banTargetUser.value) return
  banning.value = true
  try {
    await api.post(`/users/${banTargetUser.value.id}/ban`, { reason: banReason.value })
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

async function unbanUser(user: User) {
  try {
    await api.post(`/users/${user.id}/unban`)
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
  <div class="max-w-5xl mx-auto py-8 px-4">
    <div class="flex justify-between items-center mb-6">
      <h1 class="text-2xl font-bold text-gray-900">User Management</h1>
      <button
        @click="showCreateModal = true"
        class="bg-blue-600 text-white px-4 py-2 rounded-lg text-sm hover:bg-blue-700 transition"
      >
        Create Account
      </button>
    </div>

    <div v-if="message" class="bg-blue-50 border border-blue-200 text-blue-700 rounded-lg p-3 mb-4 text-sm">
      {{ message }}
    </div>

    <div class="bg-white rounded-xl shadow overflow-hidden">
      <table class="w-full text-sm">
        <thead class="bg-gray-50 border-b">
          <tr>
            <th class="text-left px-4 py-3 font-medium text-gray-600">Username</th>
            <th class="text-left px-4 py-3 font-medium text-gray-600">Display Name</th>
            <th class="text-left px-4 py-3 font-medium text-gray-600">Role</th>
            <th class="text-left px-4 py-3 font-medium text-gray-600">Status</th>
            <th v-if="auth.isSuperAdmin" class="text-left px-4 py-3 font-medium text-gray-600">Actions</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="loading">
            <td colspan="5" class="px-4 py-8 text-center text-gray-400">Loading...</td>
          </tr>
          <tr v-for="user in users" :key="user.id" class="border-b last:border-0 hover:bg-gray-50">
            <td class="px-4 py-3">{{ user.username }}</td>
            <td class="px-4 py-3">{{ user.display_name }}</td>
            <td class="px-4 py-3">
              <span
                class="text-xs px-2 py-0.5 rounded-full"
                :class="{
                  'bg-red-100 text-red-700': user.role === 'SUPER_ADMIN',
                  'bg-orange-100 text-orange-700': user.role === 'ADMIN',
                  'bg-blue-100 text-blue-700': user.role === 'MEMBER',
                  'bg-gray-100 text-gray-600': user.role === 'GUEST',
                }"
              >
                {{ roleLabels[user.role] || user.role }}
              </span>
            </td>
            <td class="px-4 py-3">
              <span
                v-if="user.is_banned"
                class="text-xs px-2 py-0.5 rounded-full bg-red-100 text-red-700"
                :title="user.ban_reason || ''"
              >
                Banned
              </span>
              <span v-else class="text-xs text-gray-400">Active</span>
            </td>
            <td v-if="auth.isSuperAdmin" class="px-4 py-3">
              <div class="flex items-center gap-2">
                <select
                  v-if="user.id !== auth.user?.id"
                  :value="user.role"
                  @change="changeRole(user.id, ($event.target as HTMLSelectElement).value)"
                  class="text-xs border border-gray-300 rounded px-2 py-1"
                >
                  <option v-for="r in roles" :key="r" :value="r">{{ roleLabels[r] }}</option>
                </select>
                <span v-else class="text-xs text-gray-400">Current user</span>

                <template v-if="user.id !== auth.user?.id">
                  <button
                    v-if="!user.is_banned"
                    @click="openBanModal(user)"
                    class="text-xs px-2 py-1 bg-red-50 text-red-600 rounded hover:bg-red-100 transition"
                  >
                    Ban
                  </button>
                  <button
                    v-else
                    @click="unbanUser(user)"
                    class="text-xs px-2 py-1 bg-green-50 text-green-600 rounded hover:bg-green-100 transition"
                  >
                    Unban
                  </button>
                </template>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <p class="mt-4 text-sm text-gray-500">{{ total }} users total</p>

    <!-- Create account modal -->
    <div v-if="showCreateModal" class="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
      <div class="bg-white rounded-xl shadow-xl p-6 w-full max-w-md">
        <h2 class="text-lg font-bold mb-4">Create Account</h2>
        <form @submit.prevent="createAccount" class="space-y-3">
          <input v-model="newUsername" type="text" required placeholder="Username" class="w-full px-3 py-2 border rounded-lg" />
          <input v-model="newDisplayName" type="text" required placeholder="Display Name" class="w-full px-3 py-2 border rounded-lg" />
          <input v-model="newPassword" type="password" required placeholder="Password (8+ chars, upper/lower/digit)" class="w-full px-3 py-2 border rounded-lg" />
          <select v-model="newRole" class="w-full px-3 py-2 border rounded-lg">
            <option value="MEMBER">Member</option>
            <option v-if="auth.isSuperAdmin" value="ADMIN">Admin</option>
          </select>
          <div class="flex gap-3 pt-2">
            <button type="submit" :disabled="creating" class="flex-1 bg-blue-600 text-white py-2 rounded-lg hover:bg-blue-700 disabled:opacity-50">
              {{ creating ? 'Creating...' : 'Create' }}
            </button>
            <button type="button" @click="showCreateModal = false" class="flex-1 bg-gray-100 py-2 rounded-lg hover:bg-gray-200">
              Cancel
            </button>
          </div>
        </form>
      </div>
    </div>

    <!-- Ban user modal -->
    <div v-if="showBanModal" class="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
      <div class="bg-white rounded-xl shadow-xl p-6 w-full max-w-md">
        <h2 class="text-lg font-bold mb-2">Ban User</h2>
        <p class="text-sm text-gray-600 mb-4">
          Ban <strong>{{ banTargetUser?.username }}</strong>? This will immediately revoke their session.
        </p>
        <form @submit.prevent="confirmBan" class="space-y-3">
          <textarea
            v-model="banReason"
            required
            placeholder="Reason for ban"
            rows="3"
            class="w-full px-3 py-2 border rounded-lg resize-none"
          ></textarea>
          <div class="flex gap-3 pt-2">
            <button type="submit" :disabled="banning" class="flex-1 bg-red-600 text-white py-2 rounded-lg hover:bg-red-700 disabled:opacity-50">
              {{ banning ? 'Banning...' : 'Confirm Ban' }}
            </button>
            <button type="button" @click="showBanModal = false" class="flex-1 bg-gray-100 py-2 rounded-lg hover:bg-gray-200">
              Cancel
            </button>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>

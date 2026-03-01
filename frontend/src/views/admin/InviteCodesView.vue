<script setup lang="ts">
import { ref, onMounted } from 'vue'
import api from '@/composables/api'
import SkeletonLoader from '@/components/SkeletonLoader.vue'
import EmptyState from '@/components/EmptyState.vue'

interface InviteCode {
  id: string
  code: string
  creator_username: string | null
  consumed_by_username: string | null
  status: 'active' | 'consumed' | 'expired'
  created_at: string
  expires_at: string | null
}

const codes = ref<InviteCode[]>([])
const total = ref(0)
const loading = ref(false)
const statusFilter = ref<string | null>(null)
const generating = ref(false)
const message = ref('')

async function fetchCodes() {
  loading.value = true
  try {
    const params: Record<string, unknown> = {}
    if (statusFilter.value) params.status = statusFilter.value
    const { data } = await api.get('/admin/invite-codes', { params })
    codes.value = data.codes
    total.value = data.total
  } catch {
    // silent
  } finally {
    loading.value = false
  }
}

async function generateCode() {
  generating.value = true
  message.value = ''
  try {
    const { data } = await api.post('/auth/invite-code')
    message.value = `Generated: ${data.invite_code}`
    await fetchCodes()
  } catch {
    message.value = 'Failed to generate code.'
  } finally {
    generating.value = false
  }
}

function statusBadgeClass(status: string) {
  switch (status) {
    case 'active':
      return 'bg-green-100 text-green-700'
    case 'consumed':
      return 'bg-gray-100 text-gray-600'
    case 'expired':
      return 'bg-red-100 text-red-600'
    default:
      return 'bg-gray-100 text-gray-600'
  }
}

onMounted(fetchCodes)
</script>

<template>
  <div class="max-w-5xl mx-auto py-8 px-4">
    <div class="flex items-center justify-between mb-6">
      <h1 class="text-2xl font-bold text-gray-900">Invite Codes</h1>
      <button
        @click="generateCode"
        :disabled="generating"
        class="bg-blue-600 text-white px-4 py-2 rounded-lg text-sm hover:bg-blue-700 transition disabled:opacity-50"
      >
        {{ generating ? 'Generating...' : 'Generate Code' }}
      </button>
    </div>

    <p v-if="message" class="mb-4 text-sm text-green-600 bg-green-50 px-4 py-2 rounded-lg">
      {{ message }}
    </p>

    <!-- Filter -->
    <div class="mb-4">
      <select
        v-model="statusFilter"
        @change="fetchCodes"
        class="px-3 py-2 border border-gray-300 rounded-lg text-sm"
      >
        <option :value="null">All Statuses</option>
        <option value="active">Active</option>
        <option value="consumed">Consumed</option>
        <option value="expired">Expired</option>
      </select>
    </div>

    <SkeletonLoader v-if="loading" :lines="5" variant="list" />

    <EmptyState
      v-else-if="codes.length === 0"
      message="No invite codes found."
      title="No Codes"
    />

    <div v-else class="bg-white rounded-xl shadow overflow-hidden">
      <table class="w-full text-sm">
        <thead class="bg-gray-50 text-left text-gray-500">
          <tr>
            <th class="px-4 py-3 font-medium">Code</th>
            <th class="px-4 py-3 font-medium">Status</th>
            <th class="px-4 py-3 font-medium">Created By</th>
            <th class="px-4 py-3 font-medium">Used By</th>
            <th class="px-4 py-3 font-medium">Created</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-gray-100">
          <tr v-for="code in codes" :key="code.id" class="hover:bg-gray-50">
            <td class="px-4 py-3 font-mono text-xs">{{ code.code }}</td>
            <td class="px-4 py-3">
              <span
                class="text-xs px-2 py-0.5 rounded-full"
                :class="statusBadgeClass(code.status)"
              >
                {{ code.status }}
              </span>
            </td>
            <td class="px-4 py-3 text-gray-600">{{ code.creator_username || '—' }}</td>
            <td class="px-4 py-3 text-gray-600">{{ code.consumed_by_username || '—' }}</td>
            <td class="px-4 py-3 text-gray-400">{{ new Date(code.created_at).toLocaleDateString() }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <p class="mt-4 text-xs text-gray-400">{{ total }} code(s) total</p>
  </div>
</template>

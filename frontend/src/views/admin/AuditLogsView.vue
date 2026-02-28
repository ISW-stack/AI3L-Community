<script setup lang="ts">
import { ref, onMounted } from 'vue'
import api from '@/composables/api'

interface AuditLog {
  id: string
  user_id: string
  username: string | null
  display_name: string | null
  action: string
  target_type: string | null
  target_id: string | null
  ip_address: string | null
  created_at: string
}

const logs = ref<AuditLog[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = 50
const loading = ref(false)
const error = ref('')

async function fetchLogs() {
  loading.value = true
  error.value = ''
  try {
    const { data } = await api.get('/users/admin/audit-logs', {
      params: { page: page.value, page_size: pageSize },
    })
    logs.value = data.logs
    total.value = data.total
  } catch {
    error.value = 'Failed to load audit logs.'
  } finally {
    loading.value = false
  }
}

function prevPage() {
  if (page.value > 1) {
    page.value--
    fetchLogs()
  }
}

function nextPage() {
  if (page.value * pageSize < total.value) {
    page.value++
    fetchLogs()
  }
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString()
}

onMounted(fetchLogs)
</script>

<template>
  <div class="max-w-5xl mx-auto py-8 px-4">
    <h1 class="text-2xl font-bold text-gray-900 mb-6">Audit Logs</h1>

    <div v-if="error" class="bg-red-50 border border-red-200 text-red-700 rounded-lg p-3 mb-4 text-sm">
      {{ error }}
    </div>

    <div class="bg-white rounded-xl shadow overflow-hidden">
      <table class="w-full text-sm">
        <thead class="bg-gray-50 border-b">
          <tr>
            <th class="text-left px-4 py-3 font-medium text-gray-600">Timestamp</th>
            <th class="text-left px-4 py-3 font-medium text-gray-600">User</th>
            <th class="text-left px-4 py-3 font-medium text-gray-600">Action</th>
            <th class="text-left px-4 py-3 font-medium text-gray-600">Target</th>
            <th class="text-left px-4 py-3 font-medium text-gray-600">IP Address</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="loading">
            <td colspan="5" class="px-4 py-8 text-center text-gray-400">Loading...</td>
          </tr>
          <tr v-else-if="logs.length === 0">
            <td colspan="5" class="px-4 py-8 text-center text-gray-400">No audit logs found.</td>
          </tr>
          <tr v-for="log in logs" :key="log.id" class="border-b last:border-0 hover:bg-gray-50">
            <td class="px-4 py-3 text-gray-500 whitespace-nowrap">{{ formatDate(log.created_at) }}</td>
            <td class="px-4 py-3">
              <span v-if="log.display_name">{{ log.display_name }}</span>
              <span v-else class="text-gray-400">{{ log.user_id.slice(0, 8) }}</span>
            </td>
            <td class="px-4 py-3">
              <span class="text-xs px-2 py-0.5 rounded-full bg-gray-100 text-gray-700 font-mono">
                {{ log.action }}
              </span>
            </td>
            <td class="px-4 py-3 text-gray-500">
              <template v-if="log.target_type">
                {{ log.target_type }}
                <span v-if="log.target_id" class="text-xs text-gray-400">{{ log.target_id.slice(0, 8) }}</span>
              </template>
              <span v-else class="text-gray-300">-</span>
            </td>
            <td class="px-4 py-3 text-gray-500 font-mono text-xs">{{ log.ip_address || '-' }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <div class="flex items-center justify-between mt-4">
      <p class="text-sm text-gray-500">{{ total }} logs total</p>
      <div class="flex gap-2">
        <button
          @click="prevPage"
          :disabled="page <= 1"
          class="px-3 py-1 text-sm border rounded-lg disabled:opacity-30 hover:bg-gray-50"
        >
          Previous
        </button>
        <span class="px-3 py-1 text-sm text-gray-600">Page {{ page }}</span>
        <button
          @click="nextPage"
          :disabled="page * pageSize >= total"
          class="px-3 py-1 text-sm border rounded-lg disabled:opacity-30 hover:bg-gray-50"
        >
          Next
        </button>
      </div>
    </div>
  </div>
</template>

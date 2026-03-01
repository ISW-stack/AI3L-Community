<script setup lang="ts">
import { ref, onMounted } from 'vue'
import type { AuditLog } from '@/types'
import { getAuditLogs } from '@/api/admin'
import BaseAlert from '@/components/base/BaseAlert.vue'
import BaseBadge from '@/components/base/BaseBadge.vue'
import BaseButton from '@/components/base/BaseButton.vue'

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
    const data = await getAuditLogs({ page: page.value, page_size: pageSize })
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
  <div>
    <h1 class="text-2xl font-bold text-foreground mb-6">Audit Logs</h1>

    <BaseAlert v-if="error" type="error" class="mb-4">{{ error }}</BaseAlert>

    <div class="bg-surface rounded-lg shadow overflow-hidden overflow-x-auto">
      <table class="w-full text-sm min-w-[750px]">
        <thead class="bg-surface-alt border-b border-border">
          <tr>
            <th class="text-left px-4 py-3 font-medium text-muted">Timestamp</th>
            <th class="text-left px-4 py-3 font-medium text-muted">User</th>
            <th class="text-left px-4 py-3 font-medium text-muted">Action</th>
            <th class="text-left px-4 py-3 font-medium text-muted">Target</th>
            <th class="text-left px-4 py-3 font-medium text-muted">IP Address</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="loading">
            <td colspan="5" class="px-4 py-8 text-center text-muted">Loading...</td>
          </tr>
          <tr v-else-if="logs.length === 0">
            <td colspan="5" class="px-4 py-8 text-center text-muted">No audit logs found.</td>
          </tr>
          <tr
            v-for="log in logs"
            :key="log.id"
            class="border-b border-border last:border-0 hover:bg-surface-alt transition"
          >
            <td class="px-4 py-3 text-muted whitespace-nowrap">{{ formatDate(log.created_at) }}</td>
            <td class="px-4 py-3 text-foreground">
              <span v-if="log.display_name">{{ log.display_name }}</span>
              <span v-else class="text-muted">{{ log.user_id.slice(0, 8) }}</span>
            </td>
            <td class="px-4 py-3">
              <BaseBadge variant="neutral" class="font-mono">{{ log.action }}</BaseBadge>
            </td>
            <td class="px-4 py-3 text-muted">
              <template v-if="log.target_type">
                {{ log.target_type }}
                <span v-if="log.target_id" class="text-xs text-muted">{{
                  log.target_id.slice(0, 8)
                }}</span>
              </template>
              <span v-else class="text-muted">-</span>
            </td>
            <td class="px-4 py-3 text-muted font-mono text-xs">{{ log.ip_address || '-' }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <div class="flex items-center justify-between mt-4">
      <p class="text-sm text-muted">{{ total }} logs total</p>
      <div class="flex gap-2">
        <BaseButton size="sm" variant="secondary" @click="prevPage" :disabled="page <= 1"
          >Previous</BaseButton
        >
        <span class="px-3 py-1 text-sm text-muted">Page {{ page }}</span>
        <BaseButton
          size="sm"
          variant="secondary"
          @click="nextPage"
          :disabled="page * pageSize >= total"
          >Next</BaseButton
        >
      </div>
    </div>
  </div>
</template>

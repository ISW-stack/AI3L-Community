<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import type { AuditLog } from '@/types'
import { getAuditLogs } from '@/api/admin'
import { usePagination } from '@/composables/usePagination'
import BaseAlert from '@/components/base/BaseAlert.vue'
import BaseBadge from '@/components/base/BaseBadge.vue'
import BaseButton from '@/components/base/BaseButton.vue'
import EmptyState from '@/components/EmptyState.vue'

const logs = ref<AuditLog[]>([])
const { page, total, pageSize, setPage, resetPage, updateFromResponse } = usePagination(50)
const loading = ref(false)
const error = ref('')

const showFilters = ref(false)
const filterDateFrom = ref('')
const filterDateTo = ref('')
const filterUserId = ref('')

const dateRangeInvalid = computed(
  () => !!filterDateFrom.value && !!filterDateTo.value && filterDateFrom.value > filterDateTo.value,
)

function toggleFilters() {
  showFilters.value = !showFilters.value
}

function applyFilters() {
  resetPage()
  fetchLogs()
}

function clearFilters() {
  filterDateFrom.value = ''
  filterDateTo.value = ''
  filterUserId.value = ''
  resetPage()
  fetchLogs()
}

const hasActiveFilters = computed(
  () => !!filterDateFrom.value || !!filterDateTo.value || !!filterUserId.value,
)

async function fetchLogs() {
  loading.value = true
  error.value = ''
  try {
    const params: {
      page: number
      page_size: number
      user_id?: string
      date_from?: string
      date_to?: string
    } = { page: page.value, page_size: pageSize }
    if (filterUserId.value.trim()) params.user_id = filterUserId.value.trim()
    if (filterDateFrom.value) params.date_from = filterDateFrom.value
    if (filterDateTo.value) params.date_to = filterDateTo.value
    const data = await getAuditLogs(params)
    logs.value = data.logs
    updateFromResponse(data.total)
  } catch {
    error.value = 'Failed to load audit logs.'
  } finally {
    loading.value = false
  }
}

function prevPage() {
  if (page.value > 1) {
    setPage(page.value - 1)
    fetchLogs()
  }
}
function nextPage() {
  if (page.value * pageSize < total.value) {
    setPage(page.value + 1)
    fetchLogs()
  }
}
function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  })
}

onMounted(fetchLogs)
</script>

<template>
  <div>
    <div class="flex justify-between items-center mb-6">
      <h1 class="text-2xl font-bold text-foreground">Audit Logs</h1>
      <button
        class="text-sm text-brand-600 hover:text-brand-700 hover:underline"
        @click="toggleFilters"
      >
        {{ showFilters ? 'Hide Filters' : 'Filters' }}
        <span v-if="hasActiveFilters" class="ml-1 text-xs text-brand-600">(active)</span>
      </button>
    </div>

    <!-- Filter bar (collapsible) -->
    <div v-if="showFilters" class="bg-surface rounded-lg border border-border p-4 mb-4 space-y-3">
      <div class="flex flex-col sm:flex-row gap-3 items-start sm:items-center">
        <div class="flex items-center gap-2">
          <label class="text-sm text-muted whitespace-nowrap">From</label>
          <input
            v-model="filterDateFrom"
            type="date"
            class="px-3 py-2 border border-border rounded-lg text-sm focus:ring-2 focus:ring-brand-500 focus:border-transparent outline-none"
          />
        </div>
        <div class="flex items-center gap-2">
          <label class="text-sm text-muted whitespace-nowrap">To</label>
          <input
            v-model="filterDateTo"
            type="date"
            class="px-3 py-2 border border-border rounded-lg text-sm focus:ring-2 focus:ring-brand-500 focus:border-transparent outline-none"
          />
        </div>
        <div class="flex items-center gap-2">
          <label class="text-sm text-muted whitespace-nowrap">User ID</label>
          <input
            v-model="filterUserId"
            type="text"
            placeholder="UUID..."
            class="px-3 py-2 border border-border rounded-lg text-sm focus:ring-2 focus:ring-brand-500 focus:border-transparent outline-none w-48"
          />
        </div>
      </div>
      <p v-if="dateRangeInvalid" class="text-sm text-danger-600">
        Start date must be before end date.
      </p>
      <div class="flex gap-2">
        <BaseButton size="sm" :disabled="dateRangeInvalid" @click="applyFilters">Apply</BaseButton>
        <BaseButton v-if="hasActiveFilters" size="sm" variant="secondary" @click="clearFilters"
          >Clear</BaseButton
        >
      </div>
    </div>

    <BaseAlert v-if="error" type="error" class="mb-4">{{ error }}</BaseAlert>

    <EmptyState
      v-if="!loading && logs.length === 0"
      title="No Audit Logs"
      message="No audit logs found."
    />

    <div v-else class="relative">
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
            <tr
              v-for="log in logs"
              :key="log.id"
              class="border-b border-border last:border-0 hover:bg-surface-alt transition"
            >
              <td class="px-4 py-3 text-muted whitespace-nowrap">
                {{ formatDate(log.created_at) }}
              </td>
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
      <div
        class="absolute right-0 top-0 bottom-0 w-8 bg-gradient-to-l from-surface to-transparent pointer-events-none lg:hidden"
      ></div>
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

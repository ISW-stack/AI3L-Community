<script setup lang="ts">
import { ref, onMounted } from 'vue'
import type { Report } from '@/types'
import { listReports, reviewReport as apiReviewReport } from '@/api/admin'
import BaseBadge from '@/components/base/BaseBadge.vue'
import SkeletonLoader from '@/components/SkeletonLoader.vue'

const reports = ref<Report[]>([])
const total = ref(0)
const statusFilter = ref<string>('')
const loading = ref(false)

async function fetchReports() {
  loading.value = true
  try {
    const data = await listReports({ status_filter: statusFilter.value || undefined })
    reports.value = data.reports
    total.value = data.total
  } catch {
    /* silent */
  } finally {
    loading.value = false
  }
}

async function reviewReport(reportId: string, status: string) {
  try {
    await apiReviewReport(reportId, status)
    await fetchReports()
  } catch {
    /* silent */
  }
}

const statusBadge: Record<string, 'warning' | 'success' | 'neutral'> = {
  PENDING: 'warning',
  RESOLVED: 'success',
  DISMISSED: 'neutral',
}

onMounted(fetchReports)
</script>

<template>
  <div>
    <h1 class="text-2xl font-bold text-foreground mb-6">Post Reports</h1>

    <!-- Filter -->
    <div class="mb-4 flex gap-3 items-center">
      <label class="text-sm text-muted">Filter by status:</label>
      <select
        v-model="statusFilter"
        @change="fetchReports"
        class="px-3 py-1.5 border border-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
      >
        <option value="">All</option>
        <option value="PENDING">Pending</option>
        <option value="RESOLVED">Resolved</option>
        <option value="DISMISSED">Dismissed</option>
      </select>
    </div>

    <SkeletonLoader v-if="loading" :lines="4" variant="list" />

    <div v-else-if="reports.length === 0" class="text-center text-muted py-8">
      No reports found.
    </div>

    <div v-else class="bg-surface rounded-lg shadow overflow-hidden overflow-x-auto">
      <table class="w-full text-sm min-w-[700px]">
        <thead class="bg-surface-alt border-b border-border">
          <tr>
            <th class="text-left px-4 py-3 font-medium text-muted">Post</th>
            <th class="text-left px-4 py-3 font-medium text-muted">Reason</th>
            <th class="text-left px-4 py-3 font-medium text-muted">Status</th>
            <th class="text-left px-4 py-3 font-medium text-muted">Reported</th>
            <th class="text-left px-4 py-3 font-medium text-muted">Actions</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="report in reports"
            :key="report.id"
            class="border-b border-border last:border-0 hover:bg-surface-alt transition"
          >
            <td class="px-4 py-3">
              <router-link
                :to="`/forum/${report.post_id}`"
                class="text-brand-600 hover:underline text-xs"
              >
                {{ report.post_id.slice(0, 8) }}...
              </router-link>
            </td>
            <td class="px-4 py-3 max-w-xs truncate text-foreground">{{ report.reason }}</td>
            <td class="px-4 py-3">
              <BaseBadge :variant="statusBadge[report.status] || 'neutral'">{{
                report.status
              }}</BaseBadge>
            </td>
            <td class="px-4 py-3 text-muted text-xs">
              {{ new Date(report.created_at).toLocaleString() }}
            </td>
            <td class="px-4 py-3">
              <div v-if="report.status === 'PENDING'" class="flex gap-2">
                <button
                  @click="reviewReport(report.id, 'RESOLVED')"
                  class="text-xs text-success-600 hover:underline"
                >
                  Resolve
                </button>
                <button
                  @click="reviewReport(report.id, 'DISMISSED')"
                  class="text-xs text-muted hover:underline"
                >
                  Dismiss
                </button>
              </div>
              <span v-else class="text-xs text-muted">Reviewed</span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <p class="mt-3 text-xs text-muted">{{ total }} report(s) total</p>
  </div>
</template>

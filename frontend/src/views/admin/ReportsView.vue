<script setup lang="ts">
import { ref, onMounted } from 'vue'
import api from '@/composables/api'

interface Report {
  id: string
  post_id: string
  user_id: string
  reason: string
  status: string
  reviewed_by: string | null
  reviewed_at: string | null
  created_at: string
}

const reports = ref<Report[]>([])
const total = ref(0)
const statusFilter = ref<string>('')
const loading = ref(false)

async function fetchReports() {
  loading.value = true
  try {
    const params: Record<string, string> = {}
    if (statusFilter.value) params.status_filter = statusFilter.value
    const { data } = await api.get('/admin/reports', { params })
    reports.value = data.reports
    total.value = data.total
  } catch {
    // silent
  } finally {
    loading.value = false
  }
}

async function reviewReport(reportId: string, status: string) {
  try {
    await api.put(`/admin/reports/${reportId}/review`, { status })
    await fetchReports()
  } catch {
    // silent
  }
}

onMounted(fetchReports)
</script>

<template>
  <div class="max-w-5xl mx-auto py-8 px-4">
    <h1 class="text-2xl font-bold text-gray-900 mb-6">Post Reports</h1>

    <!-- Filter -->
    <div class="mb-4 flex gap-3 items-center">
      <label class="text-sm text-gray-600">Filter by status:</label>
      <select
        v-model="statusFilter"
        @change="fetchReports"
        class="px-3 py-1.5 border border-gray-300 rounded-lg text-sm"
      >
        <option value="">All</option>
        <option value="PENDING">Pending</option>
        <option value="RESOLVED">Resolved</option>
        <option value="DISMISSED">Dismissed</option>
      </select>
    </div>

    <div v-if="loading" class="text-center text-gray-400 py-8">Loading...</div>

    <div v-else-if="reports.length === 0" class="text-center text-gray-400 py-8">
      No reports found.
    </div>

    <div v-else class="bg-white rounded-xl shadow overflow-hidden">
      <table class="w-full text-sm">
        <thead class="bg-gray-50 border-b">
          <tr>
            <th class="text-left px-4 py-3 font-medium text-gray-600">Post</th>
            <th class="text-left px-4 py-3 font-medium text-gray-600">Reason</th>
            <th class="text-left px-4 py-3 font-medium text-gray-600">Status</th>
            <th class="text-left px-4 py-3 font-medium text-gray-600">Reported</th>
            <th class="text-left px-4 py-3 font-medium text-gray-600">Actions</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="report in reports" :key="report.id" class="border-b last:border-0 hover:bg-gray-50">
            <td class="px-4 py-3">
              <router-link :to="`/forum/${report.post_id}`" class="text-blue-600 hover:underline text-xs">
                {{ report.post_id.slice(0, 8) }}...
              </router-link>
            </td>
            <td class="px-4 py-3 max-w-xs truncate text-gray-700">{{ report.reason }}</td>
            <td class="px-4 py-3">
              <span
                class="text-xs px-2 py-0.5 rounded-full"
                :class="{
                  'bg-yellow-100 text-yellow-700': report.status === 'PENDING',
                  'bg-green-100 text-green-700': report.status === 'RESOLVED',
                  'bg-gray-100 text-gray-600': report.status === 'DISMISSED',
                }"
              >
                {{ report.status }}
              </span>
            </td>
            <td class="px-4 py-3 text-gray-400 text-xs">
              {{ new Date(report.created_at).toLocaleString() }}
            </td>
            <td class="px-4 py-3">
              <div v-if="report.status === 'PENDING'" class="flex gap-2">
                <button
                  @click="reviewReport(report.id, 'RESOLVED')"
                  class="text-xs text-green-600 hover:underline"
                >
                  Resolve
                </button>
                <button
                  @click="reviewReport(report.id, 'DISMISSED')"
                  class="text-xs text-gray-500 hover:underline"
                >
                  Dismiss
                </button>
              </div>
              <span v-else class="text-xs text-gray-400">Reviewed</span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <p class="mt-3 text-xs text-gray-400">{{ total }} report(s) total</p>
  </div>
</template>

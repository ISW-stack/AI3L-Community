<script setup lang="ts">
import { ref, onMounted } from 'vue'
import api from '@/composables/api'

interface Application {
  id: string
  user_id: string
  username: string
  display_name: string
  description: string
  status: string
  reviewed_at: string | null
  created_at: string
}

const applications = ref<Application[]>([])
const total = ref(0)
const loading = ref(false)
const message = ref('')
const statusFilter = ref('PENDING')

const statusLabels: Record<string, string> = {
  PENDING: 'Pending',
  APPROVED: 'Approved',
  REJECTED: 'Rejected',
}

async function fetchApplications() {
  loading.value = true
  try {
    const { data } = await api.get('/admin/applications', {
      params: { status: statusFilter.value || undefined },
    })
    applications.value = data.applications
    total.value = data.total
  } catch {
    message.value = 'Failed to load applications.'
  } finally {
    loading.value = false
  }
}

async function review(appId: string, action: 'APPROVED' | 'REJECTED') {
  try {
    await api.put(`/admin/applications/${appId}/review`, { action })
    message.value = action === 'APPROVED' ? 'Application approved.' : 'Application rejected.'
    await fetchApplications()
  } catch (e: any) {
    message.value = e.response?.data?.detail || 'Operation failed.'
  }
}

onMounted(fetchApplications)
</script>

<template>
  <div class="max-w-5xl mx-auto py-8 px-4">
    <h1 class="text-2xl font-bold text-gray-900 mb-6">Membership Applications</h1>

    <div class="flex gap-2 mb-4">
      <button
        v-for="s in ['PENDING', 'APPROVED', 'REJECTED']"
        :key="s"
        @click="statusFilter = s; fetchApplications()"
        class="px-3 py-1.5 text-sm rounded-lg transition"
        :class="statusFilter === s ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'"
      >
        {{ statusLabels[s] }}
      </button>
    </div>

    <div v-if="message" class="bg-blue-50 border border-blue-200 text-blue-700 rounded-lg p-3 mb-4 text-sm">
      {{ message }}
    </div>

    <div class="space-y-3">
      <div v-if="loading" class="text-center text-gray-400 py-8">Loading...</div>
      <div v-else-if="applications.length === 0" class="text-center text-gray-400 py-8">No applications found</div>

      <div
        v-for="app in applications"
        :key="app.id"
        class="bg-white rounded-xl shadow p-4 flex justify-between items-start"
      >
        <div>
          <div class="flex items-center gap-2 mb-1">
            <span class="font-medium text-gray-900">{{ app.display_name }}</span>
            <span class="text-sm text-gray-500">@{{ app.username }}</span>
            <span
              class="text-xs px-2 py-0.5 rounded-full"
              :class="{
                'bg-yellow-100 text-yellow-700': app.status === 'PENDING',
                'bg-green-100 text-green-700': app.status === 'APPROVED',
                'bg-red-100 text-red-700': app.status === 'REJECTED',
              }"
            >
              {{ statusLabels[app.status] }}
            </span>
          </div>
          <p class="text-sm text-gray-600 mb-1">{{ app.description }}</p>
          <p class="text-xs text-gray-400">{{ new Date(app.created_at).toLocaleString() }}</p>
        </div>

        <div v-if="app.status === 'PENDING'" class="flex gap-2 shrink-0">
          <button
            @click="review(app.id, 'APPROVED')"
            class="px-3 py-1.5 text-sm bg-green-600 text-white rounded-lg hover:bg-green-700"
          >
            Approve
          </button>
          <button
            @click="review(app.id, 'REJECTED')"
            class="px-3 py-1.5 text-sm bg-red-100 text-red-600 rounded-lg hover:bg-red-200"
          >
            Reject
          </button>
        </div>
      </div>
    </div>

    <p class="mt-4 text-sm text-gray-500">{{ total }} total</p>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import api from '@/composables/api'
import SkeletonLoader from '@/components/SkeletonLoader.vue'

interface DashboardStats {
  users: number
  posts: number
  sigs: number
  forms: number
  pending_reports: number
  pending_applications: number
}

const stats = ref<DashboardStats | null>(null)
const loading = ref(false)

async function fetchStats() {
  loading.value = true
  try {
    const { data } = await api.get('/admin/dashboard')
    stats.value = data
  } catch {
    // silent
  } finally {
    loading.value = false
  }
}

const cards = [
  { key: 'users', label: 'Users', color: 'bg-blue-50 text-blue-700' },
  { key: 'posts', label: 'Posts', color: 'bg-green-50 text-green-700' },
  { key: 'sigs', label: 'SIGs', color: 'bg-purple-50 text-purple-700' },
  { key: 'forms', label: 'Forms', color: 'bg-indigo-50 text-indigo-700' },
  { key: 'pending_reports', label: 'Pending Reports', color: 'bg-orange-50 text-orange-700' },
  { key: 'pending_applications', label: 'Pending Applications', color: 'bg-red-50 text-red-700' },
] as const

onMounted(fetchStats)
</script>

<template>
  <div class="max-w-5xl mx-auto py-8 px-4">
    <h1 class="text-2xl font-bold text-gray-900 mb-6">Admin Dashboard</h1>

    <SkeletonLoader v-if="loading" :lines="2" variant="card" />

    <div v-else-if="stats" class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      <div
        v-for="card in cards"
        :key="card.key"
        class="bg-white rounded-xl shadow p-6"
      >
        <p class="text-sm text-gray-500 mb-1">{{ card.label }}</p>
        <p class="text-3xl font-bold" :class="card.color">
          {{ stats[card.key] }}
        </p>
      </div>
    </div>
  </div>
</template>

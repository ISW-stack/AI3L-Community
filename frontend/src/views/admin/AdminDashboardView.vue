<script setup lang="ts">
import { ref, onMounted } from 'vue'
import SkeletonLoader from '@/components/SkeletonLoader.vue'
import BaseCard from '@/components/base/BaseCard.vue'
import type { DashboardStats } from '@/types'
import { getDashboard } from '@/api/admin'

const stats = ref<DashboardStats | null>(null)
const loading = ref(false)

async function fetchStats() {
  loading.value = true
  try {
    stats.value = await getDashboard()
  } catch {
    /* silent */
  } finally {
    loading.value = false
  }
}

const cards = [
  { key: 'users', label: 'Users', bg: 'bg-brand-50', text: 'text-brand-700' },
  { key: 'posts', label: 'Posts', bg: 'bg-success-50', text: 'text-success-600' },
  { key: 'sigs', label: 'SIGs', bg: 'bg-info-50', text: 'text-info-600' },
  { key: 'forms', label: 'Forms', bg: 'bg-info-50', text: 'text-info-600' },
  {
    key: 'pending_reports',
    label: 'Pending Reports',
    bg: 'bg-warning-50',
    text: 'text-warning-600',
  },
  {
    key: 'pending_applications',
    label: 'Pending Applications',
    bg: 'bg-danger-50',
    text: 'text-danger-600',
  },
] as const

onMounted(fetchStats)
</script>

<template>
  <div>
    <h1 class="text-2xl font-bold text-foreground mb-6">Admin Dashboard</h1>

    <SkeletonLoader v-if="loading" :lines="2" variant="card" />

    <div v-else-if="stats" class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      <BaseCard v-for="card in cards" :key="card.key" padding="lg">
        <p class="text-sm text-muted mb-1">{{ card.label }}</p>
        <p
          class="text-3xl font-bold"
          :class="[card.bg, card.text, 'inline-block px-3 py-1 rounded-lg']"
        >
          {{ stats[card.key] }}
        </p>
      </BaseCard>
    </div>
  </div>
</template>

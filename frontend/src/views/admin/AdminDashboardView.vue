<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { Users, FileText, UsersRound, ClipboardList, Flag, UserPlus } from 'lucide-vue-next'
import SkeletonLoader from '@/components/SkeletonLoader.vue'
import BaseCard from '@/components/base/BaseCard.vue'
import BaseButton from '@/components/base/BaseButton.vue'
import EmptyState from '@/components/EmptyState.vue'
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
  {
    key: 'users',
    label: 'Users',
    icon: Users,
    bg: 'bg-brand-50',
    text: 'text-brand-700',
    iconColor: 'text-brand-600',
  },
  {
    key: 'posts',
    label: 'Posts',
    icon: FileText,
    bg: 'bg-success-50',
    text: 'text-success-600',
    iconColor: 'text-success-600',
  },
  {
    key: 'sigs',
    label: 'SIGs',
    icon: UsersRound,
    bg: 'bg-info-50',
    text: 'text-info-600',
    iconColor: 'text-info-600',
  },
  {
    key: 'forms',
    label: 'Forms',
    icon: ClipboardList,
    bg: 'bg-info-50',
    text: 'text-info-600',
    iconColor: 'text-info-600',
  },
  {
    key: 'pending_reports',
    label: 'Pending Reports',
    icon: Flag,
    bg: 'bg-warning-50',
    text: 'text-warning-600',
    iconColor: 'text-warning-600',
  },
  {
    key: 'pending_applications',
    label: 'Pending Applications',
    icon: UserPlus,
    bg: 'bg-danger-50',
    text: 'text-danger-600',
    iconColor: 'text-danger-600',
  },
] as const

onMounted(fetchStats)
</script>

<template>
  <div>
    <h1 class="text-2xl font-bold text-foreground mb-6">Admin Dashboard</h1>

    <SkeletonLoader v-if="loading" :lines="2" variant="card" />

    <EmptyState v-else-if="!stats" message="No dashboard data available." />

    <template v-else>
      <div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <BaseCard v-for="card in cards" :key="card.key" padding="lg">
          <div class="flex items-center justify-between">
            <div>
              <p class="text-sm text-muted">{{ card.label }}</p>
              <p class="text-3xl font-bold" :class="card.text">
                {{ stats[card.key] }}
              </p>
            </div>
            <div class="w-12 h-12 rounded-lg flex items-center justify-center" :class="card.bg">
              <component :is="card.icon" class="w-6 h-6" :class="card.iconColor" />
            </div>
          </div>
        </BaseCard>
      </div>

      <BaseCard padding="lg" class="mt-6">
        <h2 class="text-lg font-semibold text-foreground mb-4">Quick Actions</h2>
        <div class="flex flex-wrap gap-3">
          <router-link to="/admin/users">
            <BaseButton variant="secondary" size="sm">Manage Users</BaseButton>
          </router-link>
          <router-link to="/admin/applications">
            <BaseButton variant="secondary" size="sm">Review Applications</BaseButton>
          </router-link>
          <router-link to="/admin/reports">
            <BaseButton variant="secondary" size="sm">View Reports</BaseButton>
          </router-link>
        </div>
      </BaseCard>
    </template>
  </div>
</template>

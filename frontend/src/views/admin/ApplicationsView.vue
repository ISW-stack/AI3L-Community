<script setup lang="ts">
import { ref, onMounted } from 'vue'
import type { Application } from '@/types'
import { listApplications, reviewApplication } from '@/api/admin'
import BaseCard from '@/components/base/BaseCard.vue'
import BaseBadge from '@/components/base/BaseBadge.vue'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseAlert from '@/components/base/BaseAlert.vue'
import SkeletonLoader from '@/components/SkeletonLoader.vue'

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
const statusBadge: Record<string, 'warning' | 'success' | 'danger'> = {
  PENDING: 'warning',
  APPROVED: 'success',
  REJECTED: 'danger',
}

async function fetchApplications() {
  loading.value = true
  try {
    const data = await listApplications({ status: statusFilter.value || undefined })
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
    await reviewApplication(appId, action)
    message.value = action === 'APPROVED' ? 'Application approved.' : 'Application rejected.'
    await fetchApplications()
  } catch (e: any) {
    message.value = e.response?.data?.detail || 'Operation failed.'
  }
}

onMounted(fetchApplications)
</script>

<template>
  <div>
    <h1 class="text-2xl font-bold text-foreground mb-6">Membership Applications</h1>

    <div class="flex gap-2 mb-4">
      <button
        v-for="s in ['PENDING', 'APPROVED', 'REJECTED']"
        :key="s"
        @click="
          () => {
            statusFilter = s
            fetchApplications()
          }
        "
        class="px-3 py-1.5 text-sm rounded-lg transition"
        :class="
          statusFilter === s
            ? 'bg-brand-600 text-white'
            : 'bg-surface-alt text-muted hover:bg-gray-100'
        "
      >
        {{ statusLabels[s] }}
      </button>
    </div>

    <BaseAlert v-if="message" type="info" class="mb-4">{{ message }}</BaseAlert>

    <div class="space-y-3">
      <SkeletonLoader v-if="loading" :lines="3" variant="card" />
      <div v-else-if="applications.length === 0" class="text-center text-muted py-8">
        No applications found
      </div>

      <BaseCard v-for="app in applications" :key="app.id" padding="lg">
        <div class="flex flex-col sm:flex-row sm:justify-between sm:items-start gap-3">
          <div>
            <div class="flex items-center gap-2 mb-1 flex-wrap">
              <span class="font-medium text-foreground">{{ app.display_name }}</span>
              <span class="text-sm text-muted">@{{ app.username }}</span>
              <BaseBadge :variant="statusBadge[app.status] || 'neutral'">{{
                statusLabels[app.status]
              }}</BaseBadge>
            </div>
            <p class="text-sm text-muted mb-1">{{ app.description }}</p>
            <p class="text-xs text-muted">{{ new Date(app.created_at).toLocaleString() }}</p>
          </div>

          <div v-if="app.status === 'PENDING'" class="flex gap-2 shrink-0">
            <BaseButton size="sm" variant="success" @click="review(app.id, 'APPROVED')"
              >Approve</BaseButton
            >
            <BaseButton size="sm" variant="soft-danger" @click="review(app.id, 'REJECTED')"
              >Reject</BaseButton
            >
          </div>
        </div>
      </BaseCard>
    </div>

    <p class="mt-4 text-sm text-muted">{{ total }} total</p>
  </div>
</template>

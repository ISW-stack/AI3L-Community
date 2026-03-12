<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import type { Application } from '@/types'
import { listApplications, reviewApplication } from '@/api/admin'
import { getErrorMessage } from '@/utils/error'
import BaseCard from '@/components/base/BaseCard.vue'
import BaseBadge from '@/components/base/BaseBadge.vue'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseAlert from '@/components/base/BaseAlert.vue'
import SkeletonLoader from '@/components/SkeletonLoader.vue'
import EmptyState from '@/components/EmptyState.vue'
import BaseBreadcrumb from '@/components/base/BaseBreadcrumb.vue'

const { t } = useI18n()
const applications = ref<Application[]>([])
const total = ref(0)
const loading = ref(false)
const message = ref('')
const statusFilter = ref('PENDING')

const statusKeyMap: Record<string, string> = {
  PENDING: 'admin.applications.filter.pending',
  APPROVED: 'admin.applications.filter.approved',
  REJECTED: 'admin.applications.filter.rejected',
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
    message.value = t('admin.applications.message.loadFailed')
  } finally {
    loading.value = false
  }
}

async function review(appId: string, action: 'APPROVED' | 'REJECTED') {
  try {
    await reviewApplication(appId, action)
    message.value =
      action === 'APPROVED'
        ? t('admin.applications.message.approved')
        : t('admin.applications.message.rejected')
    await fetchApplications()
  } catch (e: unknown) {
    message.value = getErrorMessage(e, t('admin.applications.message.failed'))
  }
}

function setStatusFilter(s: string) {
  statusFilter.value = s
  fetchApplications()
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  })
}

onMounted(fetchApplications)
</script>

<template>
  <div>
    <BaseBreadcrumb
      :items="[
        { label: t('breadcrumb.admin'), to: '/admin' },
        { label: t('breadcrumb.applications') },
      ]"
    />
    <h1 class="text-2xl font-bold text-foreground mb-6">{{ t('admin.applications.title') }}</h1>

    <div class="flex flex-wrap gap-2 mb-4">
      <button
        v-for="s in ['PENDING', 'APPROVED', 'REJECTED']"
        :key="s"
        @click="setStatusFilter(s)"
        class="px-3 py-1.5 text-sm rounded-lg transition"
        :class="
          statusFilter === s
            ? 'bg-brand-600 text-white'
            : 'bg-surface-alt text-muted hover:text-foreground'
        "
      >
        {{ t(statusKeyMap[s]) }}
      </button>
    </div>

    <BaseAlert v-if="message" type="info" class="mb-4">{{ message }}</BaseAlert>

    <div class="space-y-3">
      <SkeletonLoader v-if="loading" :lines="3" variant="card" />
      <EmptyState
        v-else-if="applications.length === 0"
        :title="t('admin.applications.emptyTitle')"
        :message="t('admin.applications.emptyMessage')"
      />

      <BaseCard v-for="app in applications" :key="app.id" padding="lg">
        <div class="flex flex-col sm:flex-row sm:justify-between sm:items-start gap-3">
          <div>
            <div class="flex items-center gap-2 mb-1 flex-wrap">
              <span class="font-medium text-foreground">{{ app.display_name }}</span>
              <span class="text-sm text-muted">@{{ app.username }}</span>
              <BaseBadge :variant="statusBadge[app.status] || 'neutral'">{{
                t(statusKeyMap[app.status])
              }}</BaseBadge>
            </div>
            <p class="text-sm text-muted mb-1">{{ app.description }}</p>
            <p class="text-xs text-muted">{{ formatDate(app.created_at) }}</p>
          </div>

          <div v-if="app.status === 'PENDING'" class="flex gap-2 shrink-0">
            <BaseButton size="sm" variant="success" @click="review(app.id, 'APPROVED')">{{
              t('admin.applications.approveBtn')
            }}</BaseButton>
            <BaseButton size="sm" variant="soft-danger" @click="review(app.id, 'REJECTED')">{{
              t('admin.applications.rejectBtn')
            }}</BaseButton>
          </div>
        </div>
      </BaseCard>
    </div>

    <p class="mt-4 text-sm text-muted">{{ t('admin.applications.total', { count: total }) }}</p>
  </div>
</template>

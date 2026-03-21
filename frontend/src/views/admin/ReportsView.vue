<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useToastStore } from '@/stores/toast'
import type { Report } from '@/types'
import { getErrorMessage } from '@/utils/error'
import { listReports, reviewReport as apiReviewReport } from '@/api/admin'
import { usePagination } from '@/composables/usePagination'
import BaseBadge from '@/components/base/BaseBadge.vue'
import BaseButton from '@/components/base/BaseButton.vue'
import BasePagination from '@/components/base/BasePagination.vue'
import EmptyState from '@/components/EmptyState.vue'
import BaseBreadcrumb from '@/components/base/BaseBreadcrumb.vue'
import SkeletonLoader from '@/components/SkeletonLoader.vue'

const { t } = useI18n()
const toast = useToastStore()
const reports = ref<Report[]>([])
const { page, total, totalPages, pageSize, setPage, resetPage, updateFromResponse } =
  usePagination()
const statusFilter = ref<string>('')
const loading = ref(false)

async function fetchReports() {
  loading.value = true
  try {
    const data = await listReports({
      status_filter: statusFilter.value || undefined,
      page: page.value,
      page_size: pageSize,
    })
    reports.value = data.reports
    updateFromResponse(data.total, data.total_pages)
  } catch (e: unknown) {
    toast.show(getErrorMessage(e, t('admin.reports.fetchError')), 'error')
  } finally {
    loading.value = false
  }
}

async function reviewReport(reportId: string, status: string) {
  try {
    await apiReviewReport(reportId, status)
    await fetchReports()
  } catch (e: unknown) {
    toast.show(getErrorMessage(e, t('admin.reports.reviewError')), 'error')
  }
}

const statusBadge: Record<string, 'warning' | 'success' | 'neutral'> = {
  PENDING: 'warning',
  RESOLVED: 'success',
  DISMISSED: 'neutral',
}

function handleStatusChange() {
  resetPage()
  fetchReports()
}

function handlePageChange(p: number) {
  setPage(p)
  fetchReports()
}

onMounted(fetchReports)
</script>

<template>
  <div>
    <BaseBreadcrumb
      :items="[{ label: t('breadcrumb.admin'), to: '/admin' }, { label: t('breadcrumb.reports') }]"
    />
    <h1 class="text-2xl font-bold text-foreground mb-6">{{ t('admin.reports.title') }}</h1>

    <!-- Filter -->
    <div class="mb-4 flex gap-3 items-center">
      <label class="text-sm text-muted">{{ t('admin.reports.filterLabel') }}</label>
      <select
        v-model="statusFilter"
        name="status-filter"
        class="px-3 py-1.5 border border-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
        @change="handleStatusChange"
      >
        <option value="">{{ t('admin.reports.filter.all') }}</option>
        <option value="PENDING">{{ t('admin.reports.filter.pending') }}</option>
        <option value="RESOLVED">{{ t('admin.reports.filter.resolved') }}</option>
        <option value="DISMISSED">{{ t('admin.reports.filter.dismissed') }}</option>
      </select>
    </div>

    <SkeletonLoader v-if="loading" :lines="4" variant="list" />

    <EmptyState v-else-if="reports.length === 0" :message="t('admin.reports.emptyMessage')" />

    <template v-else>
      <!-- Mobile card layout -->
      <div class="space-y-3 md:hidden">
        <div
          v-for="report in reports"
          :key="'mobile-' + report.id"
          class="bg-surface rounded-lg shadow border border-border p-4 space-y-2"
        >
          <div class="flex items-center justify-between gap-2">
            <router-link
              :to="`/forum/${report.post_id}`"
              class="text-brand-600 hover:underline text-sm font-medium truncate"
            >
              {{ report.post_title || report.post_id.slice(0, 8) + '...' }}
            </router-link>
            <BaseBadge :variant="statusBadge[report.status] || 'neutral'" class="shrink-0">{{
              report.status
            }}</BaseBadge>
          </div>
          <p class="text-sm text-foreground line-clamp-2">{{ report.reason }}</p>
          <p class="text-xs text-muted">{{ new Date(report.created_at).toLocaleString() }}</p>
          <div v-if="report.status === 'PENDING'" class="flex gap-2 pt-1">
            <BaseButton size="sm" variant="success" @click="reviewReport(report.id, 'RESOLVED')">{{
              t('admin.reports.resolveBtn')
            }}</BaseButton>
            <BaseButton
              size="sm"
              variant="secondary"
              @click="reviewReport(report.id, 'DISMISSED')"
              >{{ t('admin.reports.dismissBtn') }}</BaseButton
            >
          </div>
          <span v-else class="text-xs text-muted">{{ t('admin.reports.reviewedBtn') }}</span>
        </div>
      </div>

      <!-- Desktop table layout -->
      <div class="hidden md:block bg-surface rounded-lg shadow overflow-hidden overflow-x-auto">
        <table class="w-full text-sm min-w-[700px]">
          <thead class="bg-surface-alt border-b border-border">
            <tr>
              <th class="text-left px-4 py-3 font-medium text-muted">
                {{ t('admin.reports.table.post') }}
              </th>
              <th class="text-left px-4 py-3 font-medium text-muted">
                {{ t('admin.reports.table.reason') }}
              </th>
              <th class="text-left px-4 py-3 font-medium text-muted">
                {{ t('admin.reports.table.status') }}
              </th>
              <th class="text-left px-4 py-3 font-medium text-muted">
                {{ t('admin.reports.table.reported') }}
              </th>
              <th class="text-left px-4 py-3 font-medium text-muted">
                {{ t('admin.reports.table.actions') }}
              </th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="report in reports"
              :key="report.id"
              class="border-b border-border last:border-0 hover:bg-surface-alt transition"
            >
              <td class="px-4 py-3 max-w-xs truncate">
                <router-link
                  :to="`/forum/${report.post_id}`"
                  class="text-brand-600 hover:underline text-sm"
                >
                  {{ report.post_title || report.post_id.slice(0, 8) + '...' }}
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
                  <BaseButton
                    size="sm"
                    variant="success"
                    @click="reviewReport(report.id, 'RESOLVED')"
                    >{{ t('admin.reports.resolveBtn') }}</BaseButton
                  >
                  <BaseButton
                    size="sm"
                    variant="secondary"
                    @click="reviewReport(report.id, 'DISMISSED')"
                    >{{ t('admin.reports.dismissBtn') }}</BaseButton
                  >
                </div>
                <span v-else class="text-xs text-muted">{{ t('admin.reports.reviewedBtn') }}</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>

    <BasePagination
      v-if="totalPages > 1"
      :current-page="page"
      :total-pages="totalPages"
      class="mt-4"
      @update:current-page="handlePageChange"
    />

    <p class="mt-3 text-xs text-muted">{{ t('admin.reports.total', { count: total }) }}</p>
  </div>
</template>

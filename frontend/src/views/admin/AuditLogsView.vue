<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import type { AuditLog } from '@/types'
import { getAuditLogs } from '@/api/admin'
import { useFetchPaginated } from '@/composables/useFetchPaginated'
import BaseAlert from '@/components/base/BaseAlert.vue'
import BaseBadge from '@/components/base/BaseBadge.vue'
import BaseButton from '@/components/base/BaseButton.vue'
import EmptyState from '@/components/EmptyState.vue'
import BaseBreadcrumb from '@/components/base/BaseBreadcrumb.vue'

const { t } = useI18n()

const showFilters = ref(false)
const filterDateFrom = ref('')
const filterDateTo = ref('')
const filterUserId = ref('')

const {
  items: logs,
  loading,
  error,
  page,
  total,
  pageSize,
  fetchPage: fetchLogs,
  setPage,
  resetPage,
} = useFetchPaginated<AuditLog>(async (p, ps) => {
  const params: {
    page: number
    page_size: number
    user_id?: string
    date_from?: string
    date_to?: string
  } = { page: p, page_size: ps }
  if (filterUserId.value.trim()) params.user_id = filterUserId.value.trim()
  if (filterDateFrom.value) params.date_from = filterDateFrom.value
  if (filterDateTo.value) params.date_to = filterDateTo.value
  const data = await getAuditLogs(params)
  return { items: data.logs, total: data.total }
}, 50)

const dateRangeInvalid = computed(
  () => !!filterDateFrom.value && !!filterDateTo.value && filterDateFrom.value > filterDateTo.value,
)

function toggleFilters() {
  showFilters.value = !showFilters.value
}

function applyFilters() {
  if (dateRangeInvalid.value) return
  resetPage()
  fetchLogs()
}

function handleDateKeydown(event: KeyboardEvent) {
  if (event.key === 'Enter') {
    event.preventDefault()
    applyFilters()
  }
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
    <BaseBreadcrumb
      :items="[
        { label: t('breadcrumb.admin'), to: '/admin' },
        { label: t('breadcrumb.auditLogs') },
      ]"
    />
    <div class="flex justify-between items-center mb-6">
      <h1 class="text-2xl font-bold text-foreground">{{ t('admin.auditLogs.title') }}</h1>
      <button
        class="text-sm text-brand-600 hover:text-brand-700 hover:underline"
        @click="toggleFilters"
      >
        {{ showFilters ? t('admin.auditLogs.hideFilters') : t('admin.auditLogs.filters') }}
        <span v-if="hasActiveFilters" class="ml-1 text-xs text-brand-600">{{
          t('admin.auditLogs.filtersActive')
        }}</span>
      </button>
    </div>

    <!-- Filter bar (collapsible) -->
    <div v-if="showFilters" class="bg-surface rounded-lg border border-border p-4 mb-4 space-y-3">
      <div class="flex flex-col md:flex-row gap-3 items-start md:items-center">
        <div class="flex items-center gap-2">
          <label for="audit-date-from" class="text-sm text-muted whitespace-nowrap">{{
            t('admin.auditLogs.filter.from')
          }}</label>
          <input
            id="audit-date-from"
            v-model="filterDateFrom"
            type="date"
            name="date-from"
            class="px-3 py-2 border border-border rounded-lg text-sm focus:ring-2 focus:ring-brand-500 focus:border-transparent outline-none"
            @keydown.enter="handleDateKeydown"
          />
        </div>
        <div class="flex items-center gap-2">
          <label for="audit-date-to" class="text-sm text-muted whitespace-nowrap">{{
            t('admin.auditLogs.filter.to')
          }}</label>
          <input
            id="audit-date-to"
            v-model="filterDateTo"
            type="date"
            name="date-to"
            class="px-3 py-2 border border-border rounded-lg text-sm focus:ring-2 focus:ring-brand-500 focus:border-transparent outline-none"
            @keydown.enter="handleDateKeydown"
          />
        </div>
        <div class="flex items-center gap-2">
          <label for="audit-user-id" class="text-sm text-muted whitespace-nowrap">{{
            t('admin.auditLogs.filter.userId')
          }}</label>
          <input
            id="audit-user-id"
            v-model="filterUserId"
            type="text"
            name="user-id"
            :placeholder="t('admin.auditLogs.filter.userIdPlaceholder')"
            class="px-3 py-2 border border-border rounded-lg text-sm focus:ring-2 focus:ring-brand-500 focus:border-transparent outline-none w-full sm:w-48"
          />
        </div>
      </div>
      <p v-if="dateRangeInvalid" class="text-sm text-danger-600">
        {{ t('admin.auditLogs.invalidRange') }}
      </p>
      <div class="flex gap-2">
        <BaseButton size="sm" :disabled="dateRangeInvalid" @click="applyFilters">{{
          t('common.apply')
        }}</BaseButton>
        <BaseButton v-if="hasActiveFilters" size="sm" variant="secondary" @click="clearFilters">{{
          t('common.clear')
        }}</BaseButton>
      </div>
    </div>

    <BaseAlert v-if="error" type="error" class="mb-4">{{ error }}</BaseAlert>

    <EmptyState
      v-if="!loading && logs.length === 0"
      :title="t('admin.auditLogs.emptyTitle')"
      :message="t('admin.auditLogs.emptyMessage')"
    />

    <template v-else>
      <!-- Mobile card layout -->
      <div class="space-y-3 md:hidden">
        <div v-if="loading" class="px-4 py-8 text-center text-muted">
          {{ t('common.loading') }}
        </div>
        <div
          v-for="log in logs"
          :key="'m-' + log.id"
          class="bg-surface rounded-lg border border-border p-3 space-y-1.5"
        >
          <div class="flex items-center justify-between">
            <BaseBadge variant="neutral" class="font-mono text-xs">{{ log.action }}</BaseBadge>
            <span class="text-xs text-muted">{{ formatDate(log.created_at) }}</span>
          </div>
          <div class="text-sm text-foreground">
            <span v-if="log.display_name">{{ log.display_name }}</span>
            <span v-else class="text-muted">{{ log.user_id.slice(0, 8) }}</span>
          </div>
          <div v-if="log.target_type" class="text-xs text-muted">
            {{ log.target_type }}
            <span v-if="log.target_id">{{ log.target_id.slice(0, 8) }}</span>
          </div>
          <div class="text-xs text-muted font-mono">{{ log.ip_address || '-' }}</div>
        </div>
      </div>

      <!-- Desktop table layout -->
      <div class="relative hidden md:block">
        <div class="bg-surface rounded-lg shadow overflow-hidden overflow-x-auto">
          <table class="w-full text-sm min-w-[750px]">
            <thead class="bg-surface-alt border-b border-border">
              <tr>
                <th class="text-left px-4 py-3 font-medium text-muted">
                  {{ t('admin.auditLogs.table.timestamp') }}
                </th>
                <th class="text-left px-4 py-3 font-medium text-muted">
                  {{ t('admin.auditLogs.table.user') }}
                </th>
                <th class="text-left px-4 py-3 font-medium text-muted">
                  {{ t('admin.auditLogs.table.action') }}
                </th>
                <th class="text-left px-4 py-3 font-medium text-muted">
                  {{ t('admin.auditLogs.table.target') }}
                </th>
                <th class="text-left px-4 py-3 font-medium text-muted">
                  {{ t('admin.auditLogs.table.ipAddress') }}
                </th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="loading">
                <td colspan="5" class="px-4 py-8 text-center text-muted">
                  {{ t('common.loading') }}
                </td>
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
    </template>

    <div class="flex items-center justify-between mt-4">
      <p class="text-sm text-muted">{{ t('admin.auditLogs.total', { count: total }) }}</p>
      <div class="flex gap-2">
        <BaseButton size="sm" variant="secondary" @click="prevPage" :disabled="page <= 1">{{
          t('admin.auditLogs.previous')
        }}</BaseButton>
        <span class="px-3 py-1 text-sm text-muted">{{ t('admin.auditLogs.page', { page }) }}</span>
        <BaseButton
          size="sm"
          variant="secondary"
          @click="nextPage"
          :disabled="page * pageSize >= total"
          >{{ t('common.next') }}</BaseButton
        >
      </div>
    </div>
  </div>
</template>

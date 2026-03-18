<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { Copy, Check } from 'lucide-vue-next'
import SkeletonLoader from '@/components/SkeletonLoader.vue'
import EmptyState from '@/components/EmptyState.vue'
import BaseBreadcrumb from '@/components/base/BaseBreadcrumb.vue'
import type { InviteCode } from '@/types'
import { listInviteCodes, createInviteCode } from '@/api/admin'
import { getErrorMessage } from '@/utils/error'
import { useToastStore } from '@/stores/toast'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseBadge from '@/components/base/BaseBadge.vue'
import BaseAlert from '@/components/base/BaseAlert.vue'
import BasePagination from '@/components/base/BasePagination.vue'

const { t, locale } = useI18n()
const toastStore = useToastStore()
const codes = ref<InviteCode[]>([])
const total = ref(0)
const loading = ref(false)
const statusFilter = ref<string | null>(null)
const generating = ref(false)
const message = ref('')
const copiedId = ref<string | null>(null)
const copyFeedbackTimer = ref<ReturnType<typeof setTimeout> | null>(null)
const page = ref(1)
const pageSize = 50
const totalPages = computed(() => Math.ceil(total.value / pageSize) || 1)

async function fetchCodes() {
  loading.value = true
  try {
    const data = await listInviteCodes({
      status: statusFilter.value || undefined,
      page: page.value,
      page_size: pageSize,
    })
    codes.value = data.codes
    total.value = data.total
  } catch (e: unknown) {
    toastStore.show(getErrorMessage(e, t('admin.inviteCodes.message.fetchFailed')), 'error')
  } finally {
    loading.value = false
  }
}

function goToPage(p: number) {
  page.value = p
  fetchCodes()
}

function handleFilterChange() {
  page.value = 1
  fetchCodes()
}

async function generateCode() {
  generating.value = true
  message.value = ''
  try {
    const data = await createInviteCode()
    try {
      await navigator.clipboard.writeText(data.invite_code)
      toastStore.show(
        t('admin.inviteCodes.message.generated', { code: data.invite_code }),
        'success',
      )
    } catch {
      message.value = t('admin.inviteCodes.message.generatedOnly', { code: data.invite_code })
    }
    await fetchCodes()
  } catch {
    toastStore.show(t('admin.inviteCodes.message.generateFailed'), 'error')
  } finally {
    generating.value = false
  }
}

async function copyCode(code: string, codeId: string) {
  try {
    await navigator.clipboard.writeText(code)
    copiedId.value = codeId
    toastStore.show(t('admin.inviteCodes.message.copied'), 'success')
    if (copyFeedbackTimer.value) clearTimeout(copyFeedbackTimer.value)
    copyFeedbackTimer.value = setTimeout(() => {
      if (copiedId.value === codeId) copiedId.value = null
      copyFeedbackTimer.value = null
    }, 2000)
  } catch {
    toastStore.show(t('admin.inviteCodes.message.copyFailed'), 'error')
  }
}

const statusBadge: Record<string, 'success' | 'neutral' | 'danger'> = {
  active: 'success',
  consumed: 'neutral',
  expired: 'danger',
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString(locale.value, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  })
}

onMounted(fetchCodes)

onUnmounted(() => {
  if (copyFeedbackTimer.value) {
    clearTimeout(copyFeedbackTimer.value)
    copyFeedbackTimer.value = null
  }
})
</script>

<template>
  <div>
    <BaseBreadcrumb
      :items="[
        { label: t('breadcrumb.admin'), to: '/admin' },
        { label: t('breadcrumb.inviteCodes') },
      ]"
    />
    <div class="flex items-center justify-between mb-6">
      <h1 class="text-2xl font-bold text-foreground">{{ t('admin.inviteCodes.title') }}</h1>
      <BaseButton :loading="generating" @click="generateCode">{{
        t('admin.inviteCodes.generateBtn')
      }}</BaseButton>
    </div>

    <BaseAlert v-if="message" type="success" class="mb-4">{{ message }}</BaseAlert>

    <!-- Filter -->
    <div class="mb-4">
      <select
        v-model="statusFilter"
        @change="handleFilterChange"
        class="px-3 py-2 border border-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
      >
        <option :value="null">{{ t('admin.inviteCodes.filter.all') }}</option>
        <option value="active">{{ t('admin.inviteCodes.filter.active') }}</option>
        <option value="consumed">{{ t('admin.inviteCodes.filter.consumed') }}</option>
        <option value="expired">{{ t('admin.inviteCodes.filter.expired') }}</option>
      </select>
    </div>

    <SkeletonLoader v-if="loading" :lines="5" variant="list" />

    <EmptyState
      v-else-if="codes.length === 0"
      :message="t('admin.inviteCodes.emptyMessage')"
      :title="t('admin.inviteCodes.emptyTitle')"
    />

    <div v-else class="relative">
      <!-- Mobile card layout -->
      <div class="space-y-3 md:hidden">
        <div
          v-for="code in codes"
          :key="'mobile-' + code.id"
          class="bg-surface rounded-lg shadow border border-border p-4 space-y-2"
        >
          <div class="flex items-center justify-between gap-2">
            <div class="flex items-center gap-2 min-w-0">
              <code class="font-mono text-xs text-foreground truncate">{{ code.code }}</code>
              <button
                @click="copyCode(code.code, code.id)"
                class="p-2 sm:p-1 rounded hover:bg-surface-alt text-muted hover:text-foreground transition shrink-0"
                :aria-label="t('admin.inviteCodes.copyAriaLabel')"
              >
                <Check
                  v-if="copiedId === code.id"
                  class="w-3.5 h-3.5 text-success-600"
                  aria-hidden="true"
                />
                <Copy v-else class="w-3.5 h-3.5" aria-hidden="true" />
              </button>
            </div>
            <BaseBadge :variant="statusBadge[code.status] || 'neutral'" class="shrink-0">{{
              code.status
            }}</BaseBadge>
          </div>
          <div class="grid grid-cols-2 gap-1 text-xs text-muted">
            <span
              >{{ t('admin.inviteCodes.table.createdBy') }}:
              {{ code.creator_username || '—' }}</span
            >
            <span
              >{{ t('admin.inviteCodes.table.usedBy') }}:
              {{ code.consumed_by_username || '—' }}</span
            >
            <span
              >{{ t('admin.inviteCodes.table.created') }}: {{ formatDate(code.created_at) }}</span
            >
            <span
              >{{ t('admin.inviteCodes.table.expires') }}:
              {{ code.expires_at ? formatDate(code.expires_at) : '—' }}</span
            >
          </div>
        </div>
      </div>

      <!-- Desktop table layout -->
      <div class="hidden md:block bg-surface rounded-lg shadow overflow-hidden overflow-x-auto">
        <table class="w-full text-sm min-w-[650px]">
          <thead class="bg-surface-alt text-left border-b border-border">
            <tr>
              <th class="px-4 py-3 font-medium text-muted">
                {{ t('admin.inviteCodes.table.code') }}
              </th>
              <th class="px-4 py-3 font-medium text-muted">
                {{ t('admin.inviteCodes.table.status') }}
              </th>
              <th class="px-4 py-3 font-medium text-muted">
                {{ t('admin.inviteCodes.table.createdBy') }}
              </th>
              <th class="px-4 py-3 font-medium text-muted">
                {{ t('admin.inviteCodes.table.usedBy') }}
              </th>
              <th class="px-4 py-3 font-medium text-muted">
                {{ t('admin.inviteCodes.table.created') }}
              </th>
              <th class="px-4 py-3 font-medium text-muted">
                {{ t('admin.inviteCodes.table.expires') }}
              </th>
            </tr>
          </thead>
          <tbody class="divide-y divide-border">
            <tr v-for="code in codes" :key="code.id" class="hover:bg-surface-alt transition">
              <td class="px-4 py-3">
                <div class="flex items-center gap-2">
                  <code class="font-mono text-xs text-foreground">{{ code.code }}</code>
                  <button
                    @click="copyCode(code.code, code.id)"
                    class="p-1 rounded hover:bg-surface-alt text-muted hover:text-foreground transition"
                    :aria-label="t('admin.inviteCodes.copyAriaLabel')"
                  >
                    <Check
                      v-if="copiedId === code.id"
                      class="w-3.5 h-3.5 text-success-600"
                      aria-hidden="true"
                    />
                    <Copy v-else class="w-3.5 h-3.5" aria-hidden="true" />
                  </button>
                </div>
              </td>
              <td class="px-4 py-3">
                <BaseBadge :variant="statusBadge[code.status] || 'neutral'">{{
                  code.status
                }}</BaseBadge>
              </td>
              <td class="px-4 py-3 text-muted">{{ code.creator_username || '—' }}</td>
              <td class="px-4 py-3 text-muted">{{ code.consumed_by_username || '—' }}</td>
              <td class="px-4 py-3 text-muted text-xs">
                {{ formatDate(code.created_at) }}
              </td>
              <td class="px-4 py-3 text-muted text-xs">
                {{ code.expires_at ? formatDate(code.expires_at) : '—' }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <div
        class="absolute right-0 top-0 bottom-0 w-8 bg-gradient-to-l from-surface to-transparent pointer-events-none hidden md:block lg:hidden"
      ></div>
    </div>

    <div class="mt-4 flex items-center justify-between">
      <p class="text-xs text-muted">{{ t('admin.inviteCodes.total', { count: total }) }}</p>
      <BasePagination
        v-if="totalPages > 1"
        :current-page="page"
        :total-pages="totalPages"
        @update:current-page="goToPage"
      />
    </div>
  </div>
</template>

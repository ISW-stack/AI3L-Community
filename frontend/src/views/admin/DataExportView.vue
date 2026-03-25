<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useI18n } from 'vue-i18n'
import { formatDateTime } from '@/utils/date'
import { useToastStore } from '@/stores/toast'
import { getErrorMessage } from '@/utils/error'
import {
  startSiteExport,
  getExportProgress,
  getExportHistory,
  deleteExport,
} from '@/api/admin'
import type { ExportProgress, ExportHistoryItem } from '@/types/common'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseCard from '@/components/base/BaseCard.vue'
import BaseBreadcrumb from '@/components/base/BaseBreadcrumb.vue'
import { AlertTriangle, Download, Trash2, Database, FolderArchive, Loader2 } from 'lucide-vue-next'
import { isAllowedDownloadUrl } from '@/composables/useFormExport'

const { t, locale } = useI18n()
const toast = useToastStore()

// ── Options ──
const includeDatabase = ref(true)
const includeFiles = ref(true)

// ── Export state ──
const starting = ref(false)
const activeTaskId = ref<string | null>(null)
const progress = ref<ExportProgress | null>(null)

// ── History ──
const history = ref<ExportHistoryItem[]>([])
const loadingHistory = ref(false)

// ── Polling ──
let pollTimer: ReturnType<typeof setInterval> | null = null
const POLL_INTERVAL = 3000

const isRunning = computed(
  () =>
    progress.value != null &&
    progress.value.status !== 'SUCCESS' &&
    progress.value.status !== 'FAILURE',
)

const canStart = computed(
  () => !starting.value && !isRunning.value && (includeDatabase.value || includeFiles.value),
)

const progressPercent = computed(() => {
  if (!progress.value || !progress.value.total) return 0
  return Math.min(100, Math.round((progress.value.current / progress.value.total) * 100))
})

function formatBytes(bytes: number | null | undefined): string {
  if (bytes == null || bytes === 0) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB']
  let idx = 0
  let val = bytes
  while (val >= 1024 && idx < units.length - 1) {
    val /= 1024
    idx++
  }
  return `${val.toFixed(idx === 0 ? 0 : 1)} ${units[idx]}`
}

function formatDate(iso: string): string {
  if (!iso) return '-'
  return formatDateTime(iso, locale.value)
}

// ── Actions ──

async function handleStartExport() {
  starting.value = true
  try {
    const resp = await startSiteExport({
      include_database: includeDatabase.value,
      include_files: includeFiles.value,
    })
    activeTaskId.value = resp.task_id
    progress.value = {
      task_id: resp.task_id,
      status: 'PENDING',
      phase: null,
      current: 0,
      total: 0,
      detail: null,
      zip_size: 0,
      download_url: null,
      started_at: null,
      error: null,
    }
    startPolling(resp.task_id)
    toast.show(t('admin.dataExport.message.started'), 'success')
  } catch (e: unknown) {
    toast.show(getErrorMessage(e, t('admin.dataExport.message.startFailed')), 'error')
  } finally {
    starting.value = false
  }
}

function startPolling(taskId: string) {
  stopPolling()
  pollTimer = setInterval(async () => {
    try {
      const p = await getExportProgress(taskId)
      progress.value = p
      if (p.status === 'SUCCESS' || p.status === 'FAILURE') {
        stopPolling()
        if (p.status === 'SUCCESS') {
          toast.show(t('admin.dataExport.message.completed'), 'success')
          await fetchHistory()
        } else {
          toast.show(t('admin.dataExport.message.failed'), 'error')
        }
      }
    } catch {
      // Silently ignore poll errors
    }
  }, POLL_INTERVAL)
}

function stopPolling() {
  if (pollTimer != null) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

async function fetchHistory() {
  loadingHistory.value = true
  try {
    const resp = await getExportHistory()
    history.value = resp.exports
  } catch (e: unknown) {
    toast.show(getErrorMessage(e, t('admin.dataExport.message.loadFailed')), 'error')
  } finally {
    loadingHistory.value = false
  }
}

function handleDownload(url: string) {
  if (!isAllowedDownloadUrl(url)) {
    toast.show(t('admin.dataExport.message.invalidUrl'), 'error')
    return
  }
  window.open(url, '_blank')
}

async function handleDelete(taskId: string) {
  if (!confirm(t('admin.dataExport.deleteConfirm'))) return
  try {
    await deleteExport(taskId)
    toast.show(t('admin.dataExport.message.deleted'), 'success')
    history.value = history.value.filter((h) => h.task_id !== taskId)
  } catch (e: unknown) {
    toast.show(getErrorMessage(e, t('admin.dataExport.message.deleteFailed')), 'error')
  }
}

onMounted(fetchHistory)
onBeforeUnmount(stopPolling)
</script>

<template>
  <div>
    <BaseBreadcrumb
      :items="[
        { label: t('breadcrumb.admin'), to: '/admin' },
        { label: t('breadcrumb.dataExport') },
      ]"
    />

    <h1 class="text-2xl font-bold text-foreground mb-6">
      {{ t('admin.dataExport.title') }}
    </h1>

    <!-- Security warning -->
    <BaseCard class="mb-6 border-amber-300 bg-amber-50">
      <div class="flex gap-3 items-start p-4">
        <AlertTriangle class="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
        <p class="text-sm text-amber-800">
          {{ t('admin.dataExport.securityWarning') }}
        </p>
      </div>
    </BaseCard>

    <!-- Export options -->
    <BaseCard class="mb-6">
      <div class="p-5 space-y-4">
        <h2 class="text-sm font-semibold text-foreground uppercase tracking-wide">
          {{ t('admin.dataExport.optionsTitle') }}
        </h2>

        <label class="flex items-start gap-3 cursor-pointer">
          <input
            v-model="includeDatabase"
            type="checkbox"
            class="mt-1 rounded border-border text-brand-600 focus:ring-brand-500"
          />
          <div>
            <span class="text-sm font-medium text-foreground flex items-center gap-2">
              <Database class="w-4 h-4" />
              {{ t('admin.dataExport.optionDb') }}
            </span>
            <p class="text-xs text-muted mt-0.5">
              {{ t('admin.dataExport.optionDbDesc') }}
            </p>
          </div>
        </label>

        <label class="flex items-start gap-3 cursor-pointer">
          <input
            v-model="includeFiles"
            type="checkbox"
            class="mt-1 rounded border-border text-brand-600 focus:ring-brand-500"
          />
          <div>
            <span class="text-sm font-medium text-foreground flex items-center gap-2">
              <FolderArchive class="w-4 h-4" />
              {{ t('admin.dataExport.optionFiles') }}
            </span>
            <p class="text-xs text-muted mt-0.5">
              {{ t('admin.dataExport.optionFilesDesc') }}
            </p>
          </div>
        </label>

        <div class="pt-2">
          <BaseButton :disabled="!canStart" :loading="starting" @click="handleStartExport">
            {{ t('admin.dataExport.startBtn') }}
          </BaseButton>
        </div>
      </div>
    </BaseCard>

    <!-- Progress -->
    <BaseCard v-if="progress" class="mb-6">
      <div class="p-5 space-y-3">
        <h2 class="text-sm font-semibold text-foreground uppercase tracking-wide">
          {{ t('admin.dataExport.progressTitle') }}
        </h2>

        <!-- Status badge -->
        <div class="flex items-center gap-2">
          <Loader2
            v-if="isRunning"
            class="w-4 h-4 text-brand-600 animate-spin"
          />
          <span
            class="text-xs font-medium px-2 py-0.5 rounded-full"
            :class="{
              'bg-brand-100 text-brand-700': isRunning,
              'bg-green-100 text-green-700': progress.status === 'SUCCESS',
              'bg-red-100 text-red-700': progress.status === 'FAILURE',
            }"
          >
            {{ progress.status }}
          </span>
          <span v-if="progress.phase" class="text-xs text-muted">
            &mdash; {{ progress.phase }}
          </span>
        </div>

        <!-- Progress bar -->
        <div v-if="isRunning && progress.total > 0" class="space-y-1">
          <div class="w-full bg-surface-alt rounded-full h-2.5">
            <div
              class="bg-brand-600 h-2.5 rounded-full transition-all duration-300"
              :style="{ width: progressPercent + '%' }"
            />
          </div>
          <div class="flex justify-between text-xs text-muted">
            <span>{{ progress.current }} / {{ progress.total }}</span>
            <span>{{ progressPercent }}%</span>
          </div>
        </div>

        <!-- Detail -->
        <p v-if="progress.detail" class="text-xs text-muted truncate">
          {{ progress.detail }}
        </p>

        <!-- ZIP size -->
        <p v-if="progress.zip_size" class="text-xs text-muted">
          {{ t('admin.dataExport.zipSize') }}: {{ formatBytes(progress.zip_size) }}
        </p>

        <!-- Started at -->
        <p v-if="progress.started_at" class="text-xs text-muted">
          {{ t('admin.dataExport.startedAt') }}: {{ formatDate(progress.started_at) }}
        </p>

        <!-- Download button (on success) -->
        <div v-if="progress.status === 'SUCCESS' && progress.download_url" class="pt-2">
          <BaseButton size="sm" @click="handleDownload(progress.download_url!)">
            <Download class="w-4 h-4 mr-1" />
            {{ t('admin.dataExport.downloadBtn') }}
          </BaseButton>
        </div>

        <!-- Error message -->
        <p v-if="progress.status === 'FAILURE' && progress.error" class="text-sm text-red-600">
          {{ progress.error }}
        </p>
      </div>
    </BaseCard>

    <!-- History -->
    <BaseCard>
      <div class="p-5">
        <h2 class="text-sm font-semibold text-foreground uppercase tracking-wide mb-4">
          {{ t('admin.dataExport.historyTitle') }}
        </h2>

        <div v-if="loadingHistory" class="text-sm text-muted py-4">
          {{ t('common.loading') }}...
        </div>

        <div v-else-if="history.length === 0" class="text-sm text-muted py-4">
          {{ t('admin.dataExport.noHistory') }}
        </div>

        <div v-else class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="border-b border-border text-left text-muted">
                <th class="pb-2 pr-4 font-medium">{{ t('admin.dataExport.historyDate') }}</th>
                <th class="pb-2 pr-4 font-medium">{{ t('admin.dataExport.historyStatus') }}</th>
                <th class="pb-2 pr-4 font-medium">{{ t('admin.dataExport.historyType') }}</th>
                <th class="pb-2 pr-4 font-medium">{{ t('admin.dataExport.historySize') }}</th>
                <th class="pb-2 font-medium">{{ t('admin.dataExport.historyActions') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="item in history"
                :key="item.task_id"
                class="border-b border-border/50 last:border-0"
              >
                <td class="py-2.5 pr-4 text-foreground whitespace-nowrap">
                  {{ formatDate(item.created_at) }}
                </td>
                <td class="py-2.5 pr-4">
                  <span
                    class="text-xs font-medium px-2 py-0.5 rounded-full"
                    :class="{
                      'bg-green-100 text-green-700': item.status === 'SUCCESS',
                      'bg-red-100 text-red-700': item.status === 'FAILURE',
                    }"
                  >
                    {{ item.status }}
                  </span>
                </td>
                <td class="py-2.5 pr-4 text-muted whitespace-nowrap">
                  <span v-if="item.options.include_database && item.options.include_files">
                    {{ t('admin.dataExport.typeFull') }}
                  </span>
                  <span v-else-if="item.options.include_database">
                    {{ t('admin.dataExport.typeDbOnly') }}
                  </span>
                  <span v-else>
                    {{ t('admin.dataExport.typeFilesOnly') }}
                  </span>
                </td>
                <td class="py-2.5 pr-4 text-muted whitespace-nowrap">
                  {{ item.file_size ? formatBytes(item.file_size) : '-' }}
                </td>
                <td class="py-2.5">
                  <div class="flex items-center gap-2">
                    <button
                      v-if="item.download_url"
                      class="text-brand-600 hover:text-brand-700 transition"
                      :title="t('admin.dataExport.downloadBtn')"
                      @click="handleDownload(item.download_url!)"
                    >
                      <Download class="w-4 h-4" />
                    </button>
                    <span v-else-if="item.status === 'SUCCESS'" class="text-xs text-muted">
                      {{ t('admin.dataExport.expired') }}
                    </span>
                    <button
                      class="text-red-500 hover:text-red-600 transition"
                      :title="t('common.delete')"
                      @click="handleDelete(item.task_id)"
                    >
                      <Trash2 class="w-4 h-4" />
                    </button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </BaseCard>
  </div>
</template>

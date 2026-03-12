<script setup lang="ts">
import { ref, onMounted, computed, inject, watch, nextTick, onUnmounted, type Ref } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@/stores/auth'
import { useToastStore } from '@/stores/toast'
import { getSigForms } from '@/api/sigs'
import { deleteForm as deleteFormApi, listFormResponses, getForm, exportForm } from '@/api/forms'
import { getTaskStatus } from '@/api/tasks'
import { getErrorMessage } from '@/utils/error'
import { computeFormStats, filterResponses, type QuestionStats } from '@/utils/formStats'
import type { SigForm, FormResponse, Question, Sig } from '@/types'
import BaseCard from '@/components/base/BaseCard.vue'
import BaseBreadcrumb from '@/components/base/BaseBreadcrumb.vue'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseBadge from '@/components/base/BaseBadge.vue'
import BaseModal from '@/components/base/BaseModal.vue'
import BasePagination from '@/components/base/BasePagination.vue'
import SkeletonLoader from '@/components/SkeletonLoader.vue'
import EmptyState from '@/components/EmptyState.vue'

const { t } = useI18n()
const route = useRoute()
const auth = useAuthStore()
const toastStore = useToastStore()

const sigId = computed(() => route.params.id as string)
const sig = inject<Ref<Sig | null>>('sig', ref(null))
const userSigRole = inject<Ref<string | null>>('userSigRole', ref(null))

const forms = ref<SigForm[]>([])
const total = ref(0)
const loading = ref(true)

const canCreateForm = computed(() => {
  if (auth.isAdmin) return true
  return userSigRole?.value === 'ADMIN' || userSigRole?.value === 'SUB_ADMIN'
})

async function fetchForms() {
  loading.value = true
  try {
    const data = await getSigForms(sigId.value)
    forms.value = data.forms
    total.value = data.total
  } catch (e: unknown) {
    toastStore.show(getErrorMessage(e, t('sigs.forms.fetchError')), 'error')
  } finally {
    loading.value = false
  }
}

// ── Feature 4: Card Description Expand ──
const expandedDescriptions = ref<Set<string>>(new Set())
const truncatedDescriptions = ref<Set<string>>(new Set())
const descriptionRefs = ref<Record<string, HTMLElement | null>>({})

function setDescriptionRef(formId: string, el: HTMLElement | null) {
  if (el) {
    descriptionRefs.value[formId] = el
  }
}

function checkTruncation(formId: string) {
  const el = descriptionRefs.value[formId]
  if (!el) return
  if (el.scrollHeight > el.clientHeight) {
    truncatedDescriptions.value.add(formId)
  } else {
    truncatedDescriptions.value.delete(formId)
  }
}

function toggleDescription(formId: string) {
  if (expandedDescriptions.value.has(formId)) {
    expandedDescriptions.value.delete(formId)
  } else {
    expandedDescriptions.value.add(formId)
  }
}

function isDescriptionExpanded(formId: string): boolean {
  return expandedDescriptions.value.has(formId)
}

function isDescriptionTruncated(formId: string): boolean {
  return truncatedDescriptions.value.has(formId)
}

watch(forms, async () => {
  await nextTick()
  for (const f of forms.value) {
    if (f.description) {
      checkTruncation(f.id)
    }
  }
})

// ── Feature 5: Delete Warning with Response Count ──
const showFormDeleteConfirm = ref(false)
const formToDelete = ref<SigForm | null>(null)

function confirmDeleteForm(form: SigForm) {
  formToDelete.value = form
  showFormDeleteConfirm.value = true
}

function cancelDelete() {
  showFormDeleteConfirm.value = false
}

const deleteWarningMessage = computed(() => {
  if (!formToDelete.value) return ''
  const count = formToDelete.value.response_count
  if (count === 0) {
    return t('sigs.forms.deleteConfirm.messageNoResponses')
  }
  return t('sigs.forms.deleteConfirm.messageWithCount', { count })
})

async function handleDeleteForm() {
  if (!formToDelete.value) return
  try {
    await deleteFormApi(formToDelete.value.id)
    await fetchForms()
    toastStore.show(t('sigs.forms.deleteSuccess'), 'success')
  } catch (e: unknown) {
    toastStore.show(getErrorMessage(e, t('sigs.forms.deleteError')), 'error')
  } finally {
    showFormDeleteConfirm.value = false
    formToDelete.value = null
  }
}

// ── Feature 6: Share Link Copy Feedback ──
const copyFeedbackFormId = ref<string | null>(null)
let copyFeedbackTimer: ReturnType<typeof setTimeout> | null = null

async function handleShareForm(formId: string) {
  const url = `${window.location.origin}/forms/${formId}`
  try {
    await navigator.clipboard.writeText(url)
    copyFeedbackFormId.value = formId
    if (copyFeedbackTimer) clearTimeout(copyFeedbackTimer)
    copyFeedbackTimer = setTimeout(() => {
      copyFeedbackFormId.value = null
    }, 2000)
  } catch {
    toastStore.show(t('common.copyFailed'), 'error')
  }
}

onUnmounted(() => {
  if (copyFeedbackTimer) clearTimeout(copyFeedbackTimer)
  if (exportTimerInterval) clearInterval(exportTimerInterval)
})

// ── Responses Modal ──
const showResponsesModal = ref(false)
const responsesFormId = ref('')
const responsesFormTitle = ref('')
const allResponses = ref<FormResponse[]>([])
const responsesPage = ref(1)
const responsesTotalPages = ref(1)
const responsesTotal = ref(0)
const responsesLoading = ref(false)
const responsesQuestions = ref<Question[]>([])

// ── Feature 1: Statistics Tab ──
const responsesTab = ref<'individual' | 'statistics'>('individual')
const formStats = ref<QuestionStats[]>([])
const expandedTextQuestions = ref<Set<string>>(new Set())

function switchToIndividualTab() {
  responsesTab.value = 'individual'
}

function switchToStatisticsTab() {
  responsesTab.value = 'statistics'
}

function toggleTextExpand(questionId: string) {
  if (expandedTextQuestions.value.has(questionId)) {
    expandedTextQuestions.value.delete(questionId)
  } else {
    expandedTextQuestions.value.add(questionId)
  }
}

function isTextExpanded(questionId: string): boolean {
  return expandedTextQuestions.value.has(questionId)
}

// ── Feature 2: Search/Filter in Responses Modal ──
const searchQuery = ref('')
const dateFrom = ref('')
const dateTo = ref('')

const filteredResponses = computed(() => {
  return filterResponses(allResponses.value, searchQuery.value, dateFrom.value, dateTo.value)
})

const filteredCount = computed(() => filteredResponses.value.length)

// ── Feature 3: Export UX Improvement ──
const exporting = ref(false)
const exportingFormId = ref<string | null>(null)
const exportElapsed = ref(0)
let exportTimerInterval: ReturnType<typeof setInterval> | null = null
const exportCancelled = ref(false)

function startExportTimer() {
  exportElapsed.value = 0
  exportCancelled.value = false
  if (exportTimerInterval) clearInterval(exportTimerInterval)
  exportTimerInterval = setInterval(() => {
    exportElapsed.value++
  }, 1000)
}

function stopExportTimer() {
  if (exportTimerInterval) {
    clearInterval(exportTimerInterval)
    exportTimerInterval = null
  }
}

function cancelExport() {
  exportCancelled.value = true
  exporting.value = false
  exportingFormId.value = null
  stopExportTimer()
}

async function startExport(formId: string): Promise<void> {
  exportingFormId.value = formId
  exporting.value = true
  startExportTimer()
  try {
    const data = await exportForm(formId)
    let attempts = 0
    const pollTimer = setInterval(async () => {
      if (exportCancelled.value) {
        clearInterval(pollTimer)
        return
      }
      attempts++
      if (attempts > 60) {
        clearInterval(pollTimer)
        stopExportTimer()
        exporting.value = false
        exportingFormId.value = null
        toastStore.show(t('forms.view.exportTimeout'), 'error')
        return
      }
      try {
        const status = await getTaskStatus(data.task_id)
        if (status.status === 'SUCCESS' && status.download_url) {
          clearInterval(pollTimer)
          stopExportTimer()
          exporting.value = false
          exportingFormId.value = null
          window.open(status.download_url, '_blank')
        } else if (status.status === 'FAILURE') {
          clearInterval(pollTimer)
          stopExportTimer()
          exporting.value = false
          exportingFormId.value = null
          toastStore.show(t('forms.view.exportFailed'), 'error')
        }
      } catch {
        /* continue polling */
      }
    }, 1000)
  } catch (e: unknown) {
    if (!exportCancelled.value) {
      toastStore.show(getErrorMessage(e, t('forms.view.exportError')), 'error')
    }
    exporting.value = false
    exportingFormId.value = null
    stopExportTimer()
  }
}

function resolveQuestionLabel(questionId: string): string {
  const q = responsesQuestions.value.find((q) => q.id === questionId)
  return q?.label || questionId
}

function resolveAnswerValue(questionId: string, value: unknown): string {
  const q = responsesQuestions.value.find((q) => q.id === questionId)
  if (!q) return String(value ?? '(None)')

  const optionMap = new Map((q.options || []).map((o) => [o.id, o.label]))

  if (Array.isArray(value)) {
    return value.map((v) => optionMap.get(String(v)) ?? String(v)).join(', ') || '(None)'
  }
  if (typeof value === 'string' && optionMap.has(value)) {
    return optionMap.get(value)!
  }
  if (typeof value === 'object' && value !== null) {
    const obj = value as Record<string, unknown>
    if (obj.filename) return String(obj.filename)
    return JSON.stringify(value)
  }
  return String(value ?? '(None)')
}

async function fetchResponses(formId: string, title: string, page = 1) {
  responsesFormId.value = formId
  responsesFormTitle.value = title
  responsesPage.value = page
  responsesLoading.value = true
  showResponsesModal.value = true
  responsesTab.value = 'individual'
  searchQuery.value = ''
  dateFrom.value = ''
  dateTo.value = ''
  expandedTextQuestions.value = new Set()
  try {
    const [formData, respData] = await Promise.all([
      page === 1 ? getForm(formId) : Promise.resolve(null),
      listFormResponses(formId, page, 200),
    ])
    if (formData) {
      responsesQuestions.value = formData.questions
    }
    allResponses.value = respData.responses || []
    responsesTotal.value = respData.total || 0
    responsesTotalPages.value = Math.ceil(responsesTotal.value / 200) || 1

    // Compute stats client-side
    if (responsesQuestions.value.length > 0) {
      formStats.value = computeFormStats(responsesQuestions.value, allResponses.value)
    }
  } catch (e: unknown) {
    toastStore.show(getErrorMessage(e, t('sigs.forms.fetchResponsesError')), 'error')
  } finally {
    responsesLoading.value = false
  }
}

function handleResponsesPageChange(p: number) {
  fetchResponses(responsesFormId.value, responsesFormTitle.value, p)
}

onMounted(fetchForms)
onUnmounted(() => {
  if (copyFeedbackTimer) clearTimeout(copyFeedbackTimer)
  if (exportTimerInterval) clearInterval(exportTimerInterval)
})
</script>

<template>
  <div class="space-y-4">
    <BaseBreadcrumb
      :items="[
        { label: t('breadcrumb.home'), to: '/' },
        { label: t('breadcrumb.sigs'), to: '/sigs' },
        { label: sig?.name || '...', to: `/sigs/${sigId}` },
        { label: t('breadcrumb.forms') },
      ]"
    />
    <!-- Header -->
    <div class="flex items-center justify-between">
      <h2 class="text-lg font-semibold text-foreground">
        {{ t('sigs.forms.title') }} ({{ total }})
      </h2>
      <router-link v-if="canCreateForm" :to="`/sigs/${sigId}/forms/new`">
        <BaseButton size="md">{{ t('sigs.forms.createBtn') }}</BaseButton>
      </router-link>
    </div>

    <!-- Content -->
    <div v-if="loading" class="grid gap-4 sm:grid-cols-2">
      <SkeletonLoader v-for="i in 2" :key="i" variant="card" :lines="3" />
    </div>

    <EmptyState
      v-else-if="forms.length === 0"
      :title="t('sigs.forms.emptyTitle')"
      :message="t('sigs.forms.emptyMessage')"
    />

    <div v-else class="grid gap-4 sm:grid-cols-2">
      <BaseCard
        v-for="f in forms"
        :key="f.id"
        class="h-full group hover:border-brand-300 transition-all flex flex-col"
      >
        <div class="flex items-start justify-between mb-3">
          <router-link
            :to="`/forms/${f.id}`"
            class="font-bold text-foreground group-hover:text-brand-600 transition-colors leading-tight"
          >
            {{ f.title }}
          </router-link>
          <BaseBadge :variant="f.is_active ? 'success' : 'neutral'" size="sm" class="shrink-0 ml-2">
            {{ f.is_active ? t('common.active') : t('common.closed') }}
          </BaseBadge>
        </div>

        <!-- Feature 4: Description with expand/collapse -->
        <div v-if="f.description" class="mb-4">
          <p
            :ref="(el) => setDescriptionRef(f.id, el as HTMLElement | null)"
            :class="[
              'text-xs text-muted transition-all duration-300',
              isDescriptionExpanded(f.id) ? '' : 'line-clamp-3',
            ]"
          >
            {{ f.description }}
          </p>
          <button
            v-if="isDescriptionTruncated(f.id) || isDescriptionExpanded(f.id)"
            class="text-xs text-brand-600 hover:text-brand-700 font-medium mt-1"
            :aria-label="
              isDescriptionExpanded(f.id) ? t('sigs.forms.showLess') : t('sigs.forms.showMore')
            "
            @click="toggleDescription(f.id)"
          >
            {{ isDescriptionExpanded(f.id) ? t('sigs.forms.showLess') : t('sigs.forms.showMore') }}
          </button>
        </div>

        <div class="mt-auto space-y-2">
          <div
            class="flex items-center flex-wrap gap-x-4 gap-y-1 text-[10px] text-muted font-medium uppercase tracking-tight"
          >
            <span class="flex items-center gap-1"
              >{{ f.response_count }} {{ t('sigs.forms.responses') }}</span
            >
            <span v-if="f.deadline"
              >{{ t('sigs.forms.ends') }} {{ new Date(f.deadline).toLocaleDateString() }}</span
            >
            <span>{{ t('common.by') }} {{ f.created_by_name || 'Admin' }}</span>
          </div>

          <div
            v-if="f.user_is_sig_admin || auth.isAdmin"
            class="flex items-center gap-4 pt-3 mt-2 border-t border-border"
          >
            <router-link
              :to="`/forms/${f.id}/edit`"
              class="text-xs text-brand-600 hover:text-brand-700 font-medium hover:underline"
            >
              {{ t('sigs.forms.editBtn') }}
            </router-link>
            <button
              @click="fetchResponses(f.id, f.title)"
              class="text-xs text-brand-600 hover:text-brand-700 font-medium hover:underline"
            >
              {{ t('sigs.forms.responsesBtn') }}
            </button>
            <!-- Feature 6: Share with copy feedback -->
            <span class="relative">
              <button
                :aria-label="t('sigs.forms.shareBtn')"
                class="text-xs text-brand-600 hover:text-brand-700 font-medium hover:underline"
                @click="handleShareForm(f.id)"
              >
                {{ t('sigs.forms.shareBtn') }}
              </button>
              <Transition name="copy-fade">
                <span
                  v-if="copyFeedbackFormId === f.id"
                  class="absolute -top-8 left-1/2 -translate-x-1/2 bg-foreground text-surface text-xs rounded px-2 py-1 whitespace-nowrap pointer-events-none"
                  role="status"
                >
                  {{ t('sigs.forms.linkCopied') }}
                </span>
              </Transition>
            </span>
            <button
              @click="startExport(f.id)"
              :disabled="exportingFormId !== null"
              class="text-xs text-brand-600 hover:text-brand-700 font-medium hover:underline disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {{
                exportingFormId === f.id
                  ? t('forms.view.exportStarting')
                  : t('forms.view.exportCSVBtn')
              }}
            </button>
            <button
              v-if="f.created_by === auth.user?.id || auth.isAdmin"
              @click="confirmDeleteForm(f)"
              class="text-xs text-danger-600 hover:text-danger-700 font-medium hover:underline ml-auto"
            >
              {{ t('sigs.forms.deleteBtn') }}
            </button>
          </div>
        </div>
      </BaseCard>
    </div>

    <!-- Feature 5: Delete Confirmation with Response Count -->
    <BaseModal
      v-model="showFormDeleteConfirm"
      :title="t('sigs.forms.deleteConfirm.title')"
      size="sm"
    >
      <p class="text-sm text-muted mb-4 leading-relaxed">
        {{ deleteWarningMessage }}
      </p>
      <template #footer>
        <BaseButton variant="secondary" @click="cancelDelete">{{ t('common.cancel') }}</BaseButton>
        <BaseButton variant="danger" @click="handleDeleteForm">{{
          t('sigs.forms.deleteConfirm.confirmBtn')
        }}</BaseButton>
      </template>
    </BaseModal>

    <!-- Responses Modal with Tabs, Search/Filter, Statistics -->
    <BaseModal
      v-model="showResponsesModal"
      :title="`${t('sigs.forms.responsesBtn')}: ${responsesFormTitle}`"
      size="xl"
    >
      <div v-if="responsesLoading" class="py-12 flex justify-center">
        <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-600"></div>
      </div>
      <template v-else>
        <!-- Tab Toggle -->
        <div class="flex border-b border-border mb-4">
          <button
            :class="[
              'px-4 py-2 text-sm font-medium border-b-2 transition-colors',
              responsesTab === 'individual'
                ? 'border-brand-600 text-brand-600'
                : 'border-transparent text-muted hover:text-foreground',
            ]"
            :aria-label="t('sigs.forms.tabIndividual')"
            @click="switchToIndividualTab"
          >
            {{ t('sigs.forms.tabIndividual') }}
          </button>
          <button
            :class="[
              'px-4 py-2 text-sm font-medium border-b-2 transition-colors',
              responsesTab === 'statistics'
                ? 'border-brand-600 text-brand-600'
                : 'border-transparent text-muted hover:text-foreground',
            ]"
            :aria-label="t('sigs.forms.tabStatistics')"
            @click="switchToStatisticsTab"
          >
            {{ t('sigs.forms.tabStatistics') }}
          </button>
        </div>

        <!-- Individual Responses Tab -->
        <div v-if="responsesTab === 'individual'">
          <!-- Feature 2: Search/Filter -->
          <div class="mb-4 space-y-3">
            <div class="flex flex-col sm:flex-row gap-2">
              <input
                v-model="searchQuery"
                type="text"
                :placeholder="t('sigs.forms.searchPlaceholder')"
                :aria-label="t('sigs.forms.searchPlaceholder')"
                class="flex-1 text-sm border border-border rounded-lg px-3 py-2 bg-surface text-foreground placeholder:text-muted focus:outline-none focus:ring-2 focus:ring-brand-300"
              />
              <div class="flex gap-2">
                <input
                  v-model="dateFrom"
                  type="date"
                  :aria-label="t('sigs.forms.dateFrom')"
                  class="text-sm border border-border rounded-lg px-3 py-2 bg-surface text-foreground focus:outline-none focus:ring-2 focus:ring-brand-300"
                />
                <input
                  v-model="dateTo"
                  type="date"
                  :aria-label="t('sigs.forms.dateTo')"
                  class="text-sm border border-border rounded-lg px-3 py-2 bg-surface text-foreground focus:outline-none focus:ring-2 focus:ring-brand-300"
                />
              </div>
            </div>
            <p class="text-xs text-muted">
              {{
                t('sigs.forms.filteredCount', { shown: filteredCount, total: allResponses.length })
              }}
            </p>
          </div>

          <EmptyState v-if="allResponses.length === 0" :message="t('sigs.forms.noResponses')" />
          <EmptyState v-else-if="filteredResponses.length === 0" :message="t('common.noResults')" />
          <div v-else class="max-h-[60vh] overflow-y-auto pr-2 space-y-4">
            <div
              v-for="resp in filteredResponses"
              :key="resp.id"
              class="border border-border rounded-lg p-5 bg-surface-alt/30"
            >
              <div class="flex items-center justify-between mb-4 pb-2 border-b border-border/50">
                <span class="font-bold text-foreground">{{ resp.display_name }}</span>
                <span class="text-[10px] text-muted font-mono">{{
                  new Date(resp.created_at).toLocaleString()
                }}</span>
              </div>
              <div class="grid gap-3 sm:grid-cols-2">
                <div v-for="(value, key) in resp.answers" :key="key" class="space-y-1">
                  <div class="text-[10px] font-bold text-muted uppercase tracking-wider">
                    {{ resolveQuestionLabel(String(key)) }}
                  </div>
                  <div class="text-sm text-foreground">
                    {{ resolveAnswerValue(String(key), value) }}
                  </div>
                </div>
              </div>
            </div>

            <BasePagination
              v-if="responsesTotalPages > 1"
              :current-page="responsesPage"
              :total-pages="responsesTotalPages"
              class="mt-6 pt-4 border-t border-border"
              @update:current-page="handleResponsesPageChange"
            />
          </div>
        </div>

        <!-- Feature 1: Statistics Tab -->
        <div v-if="responsesTab === 'statistics'">
          <EmptyState v-if="allResponses.length === 0" :message="t('sigs.forms.noResponses')" />
          <div v-else class="max-h-[60vh] overflow-y-auto pr-2 space-y-6">
            <p class="text-sm text-muted">
              {{ t('sigs.forms.statsTotal', { count: responsesTotal }) }}
            </p>

            <div
              v-for="stat in formStats"
              :key="stat.questionId"
              class="border border-border rounded-lg p-4"
            >
              <h4 class="font-semibold text-foreground text-sm mb-3">{{ stat.label }}</h4>

              <!-- Choice Stats -->
              <template v-if="stat.type === 'choice'">
                <p class="text-xs text-muted mb-2">
                  {{ t('sigs.forms.statsTotalResponses', { count: stat.totalResponses }) }}
                </p>
                <div class="space-y-2">
                  <div v-for="opt in stat.options" :key="opt.id" class="flex items-center gap-2">
                    <span class="text-xs text-foreground w-24 shrink-0 truncate" :title="opt.label">
                      {{ opt.label }}
                    </span>
                    <div class="flex-1 bg-gray-100 rounded-full h-5 overflow-hidden">
                      <div
                        class="bg-brand-500 h-full rounded-full transition-all duration-500"
                        :style="{ width: opt.percentage + '%' }"
                        role="progressbar"
                        :aria-valuenow="opt.percentage"
                        aria-valuemin="0"
                        aria-valuemax="100"
                        :aria-label="opt.label + ': ' + opt.percentage + '%'"
                      ></div>
                    </div>
                    <span class="text-xs text-muted w-16 text-right shrink-0">
                      {{ opt.count }} ({{ opt.percentage }}%)
                    </span>
                  </div>
                </div>
              </template>

              <!-- Rating Stats -->
              <template v-if="stat.type === 'rating'">
                <div class="flex items-baseline gap-4 mb-3">
                  <span class="text-2xl font-bold text-brand-600">{{ stat.average }}</span>
                  <span class="text-xs text-muted">
                    {{ t('sigs.forms.statsAverage') }}
                    ({{ stat.min }}-{{ stat.max }}, {{ stat.totalResponses }}
                    {{ t('sigs.forms.responses') }})
                  </span>
                </div>
                <div class="space-y-1">
                  <div
                    v-for="item in stat.distribution"
                    :key="item.value"
                    class="flex items-center gap-2"
                  >
                    <span class="text-xs text-foreground w-6 text-right shrink-0">
                      {{ item.value }}
                    </span>
                    <div class="flex-1 bg-gray-100 rounded-full h-4 overflow-hidden">
                      <div
                        class="bg-amber-400 h-full rounded-full transition-all duration-500"
                        :style="{ width: item.percentage + '%' }"
                        role="progressbar"
                        :aria-valuenow="item.percentage"
                        aria-valuemin="0"
                        aria-valuemax="100"
                        :aria-label="item.value + ': ' + item.percentage + '%'"
                      ></div>
                    </div>
                    <span class="text-xs text-muted w-14 text-right shrink-0">
                      {{ item.count }} ({{ item.percentage }}%)
                    </span>
                  </div>
                </div>
              </template>

              <!-- Text Stats -->
              <template v-if="stat.type === 'text'">
                <p class="text-xs text-muted mb-2">
                  {{ t('sigs.forms.statsTotalResponses', { count: stat.totalResponses }) }}
                </p>
                <button
                  v-if="stat.answers.length > 0"
                  class="text-xs text-brand-600 hover:text-brand-700 font-medium"
                  :aria-label="t('sigs.forms.statsViewTextResponses')"
                  @click="toggleTextExpand(stat.questionId)"
                >
                  {{
                    isTextExpanded(stat.questionId)
                      ? t('sigs.forms.statsHideResponses')
                      : t('sigs.forms.statsViewTextResponses')
                  }}
                </button>
                <div
                  v-if="isTextExpanded(stat.questionId)"
                  class="mt-2 space-y-2 max-h-48 overflow-y-auto"
                >
                  <div
                    v-for="(answer, idx) in stat.answers"
                    :key="idx"
                    class="text-sm text-foreground p-2 bg-surface-alt/30 rounded border border-border/50"
                  >
                    {{ answer }}
                  </div>
                </div>
              </template>

              <!-- File Stats -->
              <template v-if="stat.type === 'file'">
                <p class="text-xs text-muted mb-2">
                  {{ t('sigs.forms.statsUploads', { count: stat.totalUploads }) }}
                </p>
                <ul v-if="stat.filenames.length > 0" class="text-sm text-foreground space-y-1">
                  <li v-for="(name, idx) in stat.filenames" :key="idx" class="truncate">
                    {{ name }}
                  </li>
                </ul>
              </template>
            </div>
          </div>
        </div>
      </template>
    </BaseModal>

    <!-- Feature 3: Export modal (overlay) -->
    <BaseModal v-model="exporting" :title="t('sigs.forms.exportTitle')" size="sm" persistent>
      <div class="text-center py-4 space-y-3">
        <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-600 mx-auto"></div>
        <p class="text-sm text-foreground">
          {{ t('sigs.forms.exportProgress', { seconds: exportElapsed }) }}
        </p>
        <p v-if="exportElapsed >= 60" class="text-xs text-danger-600">
          {{ t('sigs.forms.exportTimeoutHint') }}
        </p>
      </div>
      <template #footer>
        <BaseButton variant="secondary" @click="cancelExport">
          {{ t('common.cancel') }}
        </BaseButton>
      </template>
    </BaseModal>
  </div>
</template>

<style scoped>
.copy-fade-enter-active {
  transition: opacity 0.2s ease;
}
.copy-fade-leave-active {
  transition: opacity 0.5s ease;
}
.copy-fade-enter-from,
.copy-fade-leave-to {
  opacity: 0;
}
</style>

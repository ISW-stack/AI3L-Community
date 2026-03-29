<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { useLocale } from '@/composables/useLocale'
import { useAuthStore } from '@/stores/auth'
import { useToastStore } from '@/stores/toast'
import { listStandaloneForms, deleteForm as deleteFormApi } from '@/api/forms'
import { useFormResponseViewer } from '@/composables/useFormResponseViewer'
import { useFormExport } from '@/composables/useFormExport'
import { getErrorMessage } from '@/utils/error'
import { stripHtml } from '@/utils/html'
import { formatDate } from '@/utils/date'
import { usePagination } from '@/composables/usePagination'
import type { FormData } from '@/types'
import SkeletonLoader from '@/components/SkeletonLoader.vue'
import EmptyState from '@/components/EmptyState.vue'
import BaseCard from '@/components/base/BaseCard.vue'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseBadge from '@/components/base/BaseBadge.vue'
import BaseInput from '@/components/base/BaseInput.vue'
import BaseBreadcrumb from '@/components/base/BaseBreadcrumb.vue'
import BasePagination from '@/components/base/BasePagination.vue'
import BaseModal from '@/components/base/BaseModal.vue'

const { t, currentLocale } = useLocale()
const auth = useAuthStore()
const toast = useToastStore()

const forms = ref<FormData[]>([])
const loading = ref(false)
const initialLoading = ref(true)
const PAGE_SIZE = 12
const searchQuery = ref('')
let searchTimeout: ReturnType<typeof setTimeout> | null = null
let _fetchId = 0

const { page, total, totalPages, setPage, updateFromResponse } = usePagination(PAGE_SIZE)

const canCreate = computed(() => auth.isAuthenticated && !auth.isGuest)

function handleSearchInput(value: string) {
  searchQuery.value = value
  if (searchTimeout) clearTimeout(searchTimeout)
  searchTimeout = setTimeout(() => {
    setPage(1)
    fetchForms()
  }, 300)
}

async function fetchForms() {
  const fetchId = ++_fetchId
  loading.value = true
  try {
    const trimmed = searchQuery.value.trim()
    const data = await listStandaloneForms(page.value, PAGE_SIZE, trimmed || undefined)
    if (fetchId !== _fetchId) return // stale response
    forms.value = data.forms
    updateFromResponse(data.total)
  } catch (e: unknown) {
    if (fetchId !== _fetchId) return
    toast.show(getErrorMessage(e, t('formsDirectory.loadError')), 'error')
  } finally {
    if (fetchId === _fetchId) {
      loading.value = false
      initialLoading.value = false
    }
  }
}

function handlePageChange(p: number) {
  setPage(p)
}

function isFormOwnerOrAdmin(form: FormData): boolean {
  return form.created_by === auth.user?.id || auth.isAdmin
}

// ── Description Expand/Collapse ──
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

// ── Delete Confirmation ──
const showFormDeleteConfirm = ref(false)
const formToDelete = ref<FormData | null>(null)

function confirmDeleteForm(form: FormData) {
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
    toast.show(t('sigs.forms.deleteSuccess'), 'success')
  } catch (e: unknown) {
    toast.show(getErrorMessage(e, t('sigs.forms.deleteError')), 'error')
  } finally {
    showFormDeleteConfirm.value = false
    formToDelete.value = null
  }
}

// ── Share Link Copy Feedback ──
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
    toast.show(t('common.copyFailed'), 'error')
  }
}

// ── Response Viewer ──
const {
  searchQuery: rvSearchQuery,
  dateFrom: rvDateFrom,
  dateTo: rvDateTo,
  viewMode: rvViewMode,
  ...responseViewer
} = useFormResponseViewer({
  pageSize: 100,
  onError: (msg) => toast.show(msg || t('sigs.forms.fetchResponsesError'), 'error'),
})

const showResponsesModal = ref(false)
const responsesFormId = ref('')
const responsesFormTitle = ref('')

async function openResponsesModal(formId: string, title: string, pg = 1) {
  responsesFormId.value = formId
  responsesFormTitle.value = title
  showResponsesModal.value = true
  responseViewer.resetFilters()
  await responseViewer.fetchResponses(formId, pg)
}

function handleResponsesPageChange(p: number) {
  responseViewer.fetchResponses(responsesFormId.value, p)
}

// ── Export ──
const formExport = useFormExport({
  onError: (msg) => toast.show(msg || t('forms.view.exportFailed'), 'error'),
  onTimeout: () => toast.show(t('forms.view.exportTimeout'), 'error'),
})

function handleStartExport(formId: string) {
  formExport.startExport(formId, {
    starting: t('forms.view.exportStarting'),
    statusPrefix: t('forms.view.exportStatus'),
    timeout: t('forms.view.exportTimeout'),
    failed: t('forms.view.exportFailed'),
    error: t('forms.view.exportError'),
  })
}

const exporting = computed(() => formExport.exportStatus.value === 'pending')

onMounted(fetchForms)
onUnmounted(() => {
  if (searchTimeout) clearTimeout(searchTimeout)
  if (copyFeedbackTimer) clearTimeout(copyFeedbackTimer)
})
watch(page, fetchForms)
</script>

<template>
  <div class="flex-1 flex flex-col">
    <BaseBreadcrumb
      :items="[{ label: t('breadcrumb.home'), to: '/' }, { label: t('breadcrumb.formsDirectory') }]"
    />
    <div class="flex flex-col gap-2 sm:flex-row sm:justify-between sm:items-center mb-2">
      <h1 class="text-2xl font-bold text-foreground">{{ t('formsDirectory.title') }}</h1>
      <router-link v-if="canCreate" to="/forms/new" class="shrink-0">
        <BaseButton>{{ t('formsDirectory.createForm') }}</BaseButton>
      </router-link>
    </div>
    <p class="text-sm text-muted mb-6">{{ t('formsDirectory.privateNotice') }}</p>

    <div class="mb-4">
      <BaseInput
        :model-value="searchQuery"
        :placeholder="t('formsDirectory.searchPlaceholder')"
        @update:model-value="handleSearchInput"
      />
    </div>

    <SkeletonLoader v-if="initialLoading" :lines="3" variant="card" />

    <div v-else class="min-h-[400px]">
      <div
        :class="{ 'opacity-50 pointer-events-none': loading }"
        class="transition-opacity duration-150"
      >
        <EmptyState
          v-if="forms.length === 0 && !searchQuery"
          :title="t('formsDirectory.noForms')"
          :message="t('formsDirectory.noFormsMessage')"
        />

        <EmptyState
          v-else-if="forms.length === 0 && searchQuery"
          :title="t('formsDirectory.noSearchResults')"
          :message="t('formsDirectory.noSearchResultsMessage')"
        />

        <template v-else>
          <div class="grid gap-4 sm:grid-cols-2" data-testid="forms-grid">
            <BaseCard
              v-for="form in forms"
              :key="form.id"
              class="h-full group hover:border-brand-300 transition-all flex flex-col"
            >
              <div class="flex items-start justify-between mb-3">
                <router-link
                  :to="`/forms/${form.id}`"
                  class="font-bold text-foreground group-hover:text-brand-600 transition-colors leading-tight"
                >
                  {{ form.title }}
                </router-link>
                <BaseBadge
                  :variant="form.is_active ? 'success' : 'neutral'"
                  size="sm"
                  class="shrink-0 ml-2"
                >
                  {{ form.is_active ? t('common.active') : t('common.closed') }}
                </BaseBadge>
              </div>

              <!-- Description with expand/collapse -->
              <div v-if="form.description" class="mb-4">
                <p
                  :ref="(el) => setDescriptionRef(form.id, el as HTMLElement | null)"
                  :class="[
                    'text-xs text-muted transition-all duration-300',
                    isDescriptionExpanded(form.id) ? '' : 'line-clamp-3',
                  ]"
                >
                  {{ stripHtml(form.description) }}
                </p>
                <button
                  v-if="isDescriptionTruncated(form.id) || isDescriptionExpanded(form.id)"
                  class="text-xs text-brand-600 hover:text-brand-700 font-medium mt-1"
                  :aria-label="
                    isDescriptionExpanded(form.id)
                      ? t('sigs.forms.showLess')
                      : t('sigs.forms.showMore')
                  "
                  @click="toggleDescription(form.id)"
                >
                  {{
                    isDescriptionExpanded(form.id)
                      ? t('sigs.forms.showLess')
                      : t('sigs.forms.showMore')
                  }}
                </button>
              </div>

              <div class="mt-auto space-y-2">
                <div
                  class="flex items-center flex-wrap gap-x-4 gap-y-1 text-[10px] text-muted font-medium uppercase tracking-tight"
                >
                  <span class="flex items-center gap-1">
                    {{ form.response_count }} {{ t('formsDirectory.responses') }}
                  </span>
                  <span v-if="form.deadline">
                    {{
                      t('formsDirectory.due', { date: formatDate(form.deadline, currentLocale) })
                    }}
                  </span>
                  <span>{{ t('common.by') }} {{ form.created_by_name }}</span>
                </div>

                <!-- Admin toolbar -->
                <div
                  v-if="isFormOwnerOrAdmin(form)"
                  class="flex items-center gap-x-2 sm:gap-x-4 gap-y-2 flex-wrap pt-3 mt-2 border-t border-border"
                >
                  <router-link
                    :to="`/forms/${form.id}/edit`"
                    class="text-xs text-brand-600 hover:text-brand-700 font-medium hover:underline"
                  >
                    {{ t('sigs.forms.editBtn') }}
                  </router-link>
                  <button
                    class="text-xs text-brand-600 hover:text-brand-700 font-medium hover:underline"
                    @click="openResponsesModal(form.id, form.title)"
                  >
                    {{ t('sigs.forms.responsesBtn') }}
                  </button>
                  <!-- Share with copy feedback -->
                  <span class="relative">
                    <button
                      :aria-label="t('sigs.forms.shareBtn')"
                      class="text-xs text-brand-600 hover:text-brand-700 font-medium hover:underline"
                      @click="handleShareForm(form.id)"
                    >
                      {{ t('sigs.forms.shareBtn') }}
                    </button>
                    <Transition name="copy-fade">
                      <span
                        v-if="copyFeedbackFormId === form.id"
                        class="absolute -top-8 left-1/2 -translate-x-1/2 bg-foreground text-surface text-xs rounded px-2 py-1 whitespace-nowrap pointer-events-none"
                        role="status"
                      >
                        {{ t('sigs.forms.linkCopied') }}
                      </span>
                    </Transition>
                  </span>
                  <button
                    :disabled="formExport.exportingFormId.value !== null"
                    class="text-xs text-brand-600 hover:text-brand-700 font-medium hover:underline disabled:opacity-50 disabled:cursor-not-allowed"
                    @click="handleStartExport(form.id)"
                  >
                    {{
                      formExport.exportingFormId.value === form.id
                        ? t('forms.view.exportStarting')
                        : t('forms.view.exportCSVBtn')
                    }}
                  </button>
                  <button
                    @click="confirmDeleteForm(form)"
                    class="text-xs text-danger-600 hover:text-danger-700 font-medium hover:underline ml-auto"
                  >
                    {{ t('sigs.forms.deleteBtn') }}
                  </button>
                </div>
              </div>
            </BaseCard>
          </div>

          <div class="mt-6">
            <BasePagination
              :current-page="page"
              :total-pages="totalPages"
              :page-size="PAGE_SIZE"
              :total="total"
              @update:current-page="handlePageChange"
            />
          </div>
        </template>
      </div>
    </div>

    <p class="mt-4 text-xs text-muted">{{ t('formsDirectory.totalForms', { count: total }) }}</p>

    <!-- Delete Confirmation Modal -->
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

    <!-- Responses Modal -->
    <BaseModal
      v-model="showResponsesModal"
      :title="`${t('sigs.forms.responsesBtn')}: ${responsesFormTitle}`"
      size="xl"
    >
      <div v-if="responseViewer.loading.value" class="py-12 flex justify-center">
        <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-600"></div>
      </div>
      <template v-else>
        <!-- Tab Toggle -->
        <div class="flex border-b border-border mb-4">
          <button
            :class="[
              'px-4 py-2 text-sm font-medium border-b-2 transition-colors',
              rvViewMode === 'individual'
                ? 'border-brand-600 text-brand-600'
                : 'border-transparent text-muted hover:text-foreground',
            ]"
            :aria-label="t('sigs.forms.tabIndividual')"
            @click="rvViewMode = 'individual' as const"
          >
            {{ t('sigs.forms.tabIndividual') }}
          </button>
          <button
            :class="[
              'px-4 py-2 text-sm font-medium border-b-2 transition-colors',
              rvViewMode === 'statistics'
                ? 'border-brand-600 text-brand-600'
                : 'border-transparent text-muted hover:text-foreground',
            ]"
            :aria-label="t('sigs.forms.tabStatistics')"
            @click="rvViewMode = 'statistics' as const"
          >
            {{ t('sigs.forms.tabStatistics') }}
          </button>
        </div>

        <!-- Individual Responses Tab -->
        <div v-if="rvViewMode === 'individual'">
          <div class="mb-4 space-y-3">
            <div class="flex flex-col sm:flex-row gap-2">
              <input
                v-model="rvSearchQuery"
                type="text"
                name="response-search"
                :placeholder="t('sigs.forms.searchPlaceholder')"
                :aria-label="t('sigs.forms.searchPlaceholder')"
                class="flex-1 text-sm border border-border rounded-lg px-3 py-2 bg-surface text-foreground placeholder:text-muted focus:outline-none focus:ring-2 focus:ring-brand-300"
              />
              <div class="flex gap-2">
                <input
                  v-model="rvDateFrom"
                  type="date"
                  name="response-date-from"
                  :aria-label="t('sigs.forms.dateFrom')"
                  class="flex-1 min-w-0 text-sm border border-border rounded-lg px-3 py-2 bg-surface text-foreground focus:outline-none focus:ring-2 focus:ring-brand-300"
                />
                <input
                  v-model="rvDateTo"
                  type="date"
                  name="response-date-to"
                  :aria-label="t('sigs.forms.dateTo')"
                  class="flex-1 min-w-0 text-sm border border-border rounded-lg px-3 py-2 bg-surface text-foreground focus:outline-none focus:ring-2 focus:ring-brand-300"
                />
              </div>
            </div>
            <p class="text-xs text-muted">
              {{
                t('sigs.forms.filteredCount', {
                  shown: responseViewer.filteredCount.value,
                  total: responseViewer.responses.value.length,
                })
              }}
            </p>
          </div>

          <EmptyState
            v-if="responseViewer.responses.value.length === 0"
            :message="t('sigs.forms.noResponses')"
          />
          <EmptyState
            v-else-if="responseViewer.filteredResponses.value.length === 0"
            :message="t('common.noResults')"
          />
          <div v-else class="max-h-[60vh] overflow-y-auto pr-2 space-y-4">
            <div
              v-for="resp in responseViewer.filteredResponses.value"
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
                    {{ responseViewer.resolveQuestionLabel(String(key)) }}
                  </div>
                  <div class="text-sm text-foreground">
                    {{ responseViewer.resolveAnswerValue(String(key), value) }}
                  </div>
                </div>
              </div>
            </div>

            <BasePagination
              v-if="responseViewer.pagination.totalPages.value > 1"
              :current-page="responseViewer.pagination.page.value"
              :total-pages="responseViewer.pagination.totalPages.value"
              class="mt-6 pt-4 border-t border-border"
              @update:current-page="handleResponsesPageChange"
            />
          </div>
        </div>

        <!-- Statistics Tab -->
        <div v-if="rvViewMode === 'statistics'">
          <EmptyState
            v-if="responseViewer.responses.value.length === 0"
            :message="t('sigs.forms.noResponses')"
          />
          <div v-else class="max-h-[60vh] overflow-y-auto pr-2 space-y-6">
            <p class="text-sm text-muted">
              {{ t('sigs.forms.statsTotal', { count: responseViewer.pagination.total.value }) }}
            </p>

            <div
              v-for="stat in responseViewer.formStats.value"
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
                    <div class="flex-1 bg-surface-alt rounded-full h-5 overflow-hidden">
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
                    <div class="flex-1 bg-surface-alt rounded-full h-4 overflow-hidden">
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
                  @click="responseViewer.toggleTextExpand(stat.questionId)"
                >
                  {{
                    responseViewer.isTextExpanded(stat.questionId)
                      ? t('sigs.forms.statsHideResponses')
                      : t('sigs.forms.statsViewTextResponses')
                  }}
                </button>
                <div
                  v-if="responseViewer.isTextExpanded(stat.questionId)"
                  class="mt-2 space-y-2 max-h-32 sm:max-h-48 overflow-y-auto"
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

    <!-- Export progress modal -->
    <BaseModal v-model="exporting" :title="t('sigs.forms.exportTitle')" size="sm" persistent>
      <div class="text-center py-4 space-y-3">
        <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-600 mx-auto"></div>
        <p class="text-sm text-foreground">
          {{ t('sigs.forms.exportProgress', { seconds: formExport.exportElapsed.value }) }}
        </p>
        <p v-if="formExport.exportElapsed.value >= 60" class="text-xs text-danger-600">
          {{ t('sigs.forms.exportTimeoutHint') }}
        </p>
      </div>
      <template #footer>
        <BaseButton variant="secondary" @click="formExport.cancelExport()">
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

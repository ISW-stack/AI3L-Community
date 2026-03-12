<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@/stores/auth'
import { getErrorMessage } from '@/utils/error'
import type { Question, FormData, FormResponse } from '@/types'
import { getForm, submitForm as apiSubmitForm, exportForm, getMyResponse } from '@/api/forms'
import { getSig } from '@/api/sigs'
import { getTaskStatus } from '@/api/tasks'
import { uploadEditorFile } from '@/api/files'
import { useFormResponseDraft } from '@/composables/useFormResponseDraft'
import BaseCard from '@/components/base/BaseCard.vue'
import BaseBreadcrumb from '@/components/base/BaseBreadcrumb.vue'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseAlert from '@/components/base/BaseAlert.vue'
import BaseBadge from '@/components/base/BaseBadge.vue'
import SkeletonLoader from '@/components/SkeletonLoader.vue'
import CopyShareLinkButton from '@/components/CopyShareLinkButton.vue'
import BackToTop from '@/components/BackToTop.vue'

const { t } = useI18n()
const route = useRoute()
const auth = useAuthStore()

// ── Core State ──
const formId = computed(() => route.params.formId as string)
const form = ref<FormData | null>(null)
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const answers = ref<Record<string, any>>({})
const loading = ref(true)
const submitting = ref(false)
const submitted = ref(false)
const message = ref('')
const error = ref('')
const sigName = ref('')
const exporting = ref(false)
const exportStatus = ref('')
let exportPollTimer: ReturnType<typeof setInterval> | null = null
let isUnmounted = false

// ── View Submitted Response State (Feature 6) ──
const previousResponse = ref<FormResponse | null>(null)
const submittedAnswers = ref<Record<string, unknown>>({})

// ── Validation Error State (Feature 2) ──
const validationErrors = ref<Record<string, string>>({})
const highlightedQuestions = ref<Set<string>>(new Set())
const questionRefs = ref<Record<string, HTMLElement>>({})
let highlightTimers: Record<string, ReturnType<typeof setTimeout>> = {}

// ── File Upload State (Feature 4) ──
const dragOverQuestions = ref<Set<string>>(new Set())
const filePreviews = ref<Record<string, string>>({})
const uploadingFiles = ref<string[]>([])

// ── Question type map for draft skipping ──
const questionTypeMap = computed(() => {
  const map: Record<string, string> = {}
  if (form.value) {
    for (const q of form.value.questions) {
      map[q.id] = q.type
    }
  }
  return map
})

// ── Draft Composable (Feature 3) ──
const { draftRestored, loadDraft, clearDraft, startAutoSave, stopAutoSave } = useFormResponseDraft({
  formId,
  answers,
  skipTypes: questionTypeMap,
})

// ── Computed ──
const canEdit = computed(() => {
  if (!form.value) return false
  return auth.isAdmin || form.value.user_is_sig_admin || auth.user?.id === form.value.created_by
})
const canExport = computed(() => {
  if (!form.value) return false
  return auth.isAdmin || form.value.user_is_sig_admin
})
const formShareUrl = computed(() => `${window.location.origin}/forms/${formId.value}`)

// ── Progress Indicator (Feature 1) ──
const totalQuestions = computed(() => form.value?.questions.length ?? 0)
const answeredCount = computed(() => {
  if (!form.value) return 0
  let count = 0
  for (const q of form.value.questions) {
    const val = answers.value[q.id]
    if (val === null || val === undefined || val === '') continue
    if (Array.isArray(val) && val.length === 0) continue
    count++
  }
  return count
})
const progressPercent = computed(() => {
  if (totalQuestions.value === 0) return 0
  return Math.round((answeredCount.value / totalQuestions.value) * 100)
})

// ── Show form or read-only view ──
const showForm = computed(() => {
  return (
    !submitted.value &&
    !previousResponse.value &&
    form.value?.is_active &&
    auth.isAuthenticated &&
    !auth.isGuest
  )
})

// ── Fetch Form ──
async function fetchForm() {
  loading.value = true
  try {
    const data = await getForm(formId.value)
    form.value = data
    for (const q of data.questions) {
      answers.value[q.id] = q.type === 'multiple_choice' ? [] : q.type === 'rating' ? null : ''
    }
    try {
      const sigData = await getSig(data.sig_id)
      sigName.value = sigData.name
    } catch {
      /* breadcrumb will show fallback */
    }

    // Feature 6: Check for previous response
    if (auth.isAuthenticated && !auth.isGuest) {
      try {
        const resp = await getMyResponse(formId.value)
        if (resp) {
          previousResponse.value = resp
        }
      } catch {
        // No previous response, show the form
      }
    }

    // Feature 3: Restore draft if no previous response
    if (!previousResponse.value) {
      loadDraft()
      startAutoSave()
    }
  } catch {
    error.value = t('forms.view.loadError')
  } finally {
    loading.value = false
  }
}

// ── Validation (Feature 2) ──
function validateAnswers(): string | null {
  if (!form.value) return t('forms.view.loadError')
  validationErrors.value = {}
  let firstError: string | null = null
  let firstErrorQuestionId: string | null = null

  for (const q of form.value.questions) {
    const val = answers.value[q.id]
    if (q.required) {
      if (val === null || val === undefined || val === '') {
        const msg = `"${q.label}" ${t('common.required').toLowerCase()}.`
        validationErrors.value[q.id] = msg
        if (!firstError) {
          firstError = msg
          firstErrorQuestionId = q.id
        }
        continue
      }
      if (Array.isArray(val) && val.length === 0) {
        const msg = `"${q.label}" ${t('common.required').toLowerCase()}.`
        validationErrors.value[q.id] = msg
        if (!firstError) {
          firstError = msg
          firstErrorQuestionId = q.id
        }
        continue
      }
    }
    if (val === null || val === undefined || val === '' || (Array.isArray(val) && val.length === 0))
      continue
    if (
      (q.type === 'text' || q.type === 'textarea') &&
      q.max_length &&
      typeof val === 'string' &&
      val.length > q.max_length
    ) {
      const msg = `"${q.label}" exceeds maximum length of ${q.max_length}.`
      validationErrors.value[q.id] = msg
      if (!firstError) {
        firstError = msg
        firstErrorQuestionId = q.id
      }
    }
  }

  // Scroll to first error and highlight
  if (firstErrorQuestionId) {
    scrollToQuestion(firstErrorQuestionId)
    for (const qId of Object.keys(validationErrors.value)) {
      addHighlight(qId)
    }
  }

  return firstError
}

function scrollToQuestion(questionId: string) {
  nextTick(() => {
    const el = questionRefs.value[questionId]
    if (el && typeof el.scrollIntoView === 'function') {
      el.scrollIntoView({ behavior: 'smooth', block: 'center' })
    }
  })
}

function addHighlight(questionId: string) {
  highlightedQuestions.value.add(questionId)
  // Clear existing timer for this question
  if (highlightTimers[questionId]) {
    clearTimeout(highlightTimers[questionId])
  }
  highlightTimers[questionId] = setTimeout(() => {
    highlightedQuestions.value.delete(questionId)
  }, 3000)
}

function clearQuestionError(questionId: string) {
  if (validationErrors.value[questionId]) {
    delete validationErrors.value[questionId]
  }
  highlightedQuestions.value.delete(questionId)
  if (highlightTimers[questionId]) {
    clearTimeout(highlightTimers[questionId])
    delete highlightTimers[questionId]
  }
}

function setQuestionRef(questionId: string, el: unknown) {
  if (el instanceof HTMLElement) {
    questionRefs.value[questionId] = el
  } else if (el != null && typeof el === 'object' && '$el' in el) {
    const root = (el as { $el: HTMLElement }).$el
    if (root instanceof HTMLElement) {
      questionRefs.value[questionId] = root
    }
  }
}

// ── Submit Form ──
async function submitForm() {
  error.value = ''
  const validationError = validateAnswers()
  if (validationError) {
    error.value = validationError
    return
  }
  submitting.value = true
  try {
    const cleanAnswers: Record<string, unknown> = {}
    for (const [key, val] of Object.entries(answers.value)) {
      if (
        val !== null &&
        val !== undefined &&
        val !== '' &&
        !(Array.isArray(val) && val.length === 0)
      )
        cleanAnswers[key] = val
    }

    // Upload any pending files before submitting
    for (const [key, val] of Object.entries(cleanAnswers)) {
      if (val instanceof File) {
        uploadingFiles.value = [...uploadingFiles.value, key]
        try {
          const data = await uploadEditorFile(val)
          cleanAnswers[key] = { key: data.key || data.url, filename: val.name }
        } finally {
          uploadingFiles.value = uploadingFiles.value.filter((id) => id !== key)
        }
      }
    }

    await apiSubmitForm(formId.value, cleanAnswers)
    submitted.value = true
    message.value = t('forms.view.successMessage')
    // Feature 6: save submitted answers for read-only view
    submittedAnswers.value = { ...cleanAnswers }
    // Feature 3: clear draft after successful submission
    stopAutoSave()
    clearDraft()
  } catch (e: unknown) {
    if (
      e != null &&
      typeof e === 'object' &&
      'response' in e &&
      (e as { response?: { status?: number } }).response?.status === 409
    ) {
      submitted.value = true
      message.value = t('forms.view.alreadySubmitted')
      // Try to fetch existing response
      try {
        const resp = await getMyResponse(formId.value)
        if (resp) {
          previousResponse.value = resp
        }
      } catch {
        // ignore
      }
    } else {
      error.value = getErrorMessage(e, t('forms.view.submitError'))
    }
  } finally {
    submitting.value = false
  }
}

// ── File Upload (Feature 4) ──
function handleFileUpload(questionId: string, event: Event): void {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  processFile(questionId, file)
  // Reset so user can re-select the same file
  input.value = ''
}

function processFile(questionId: string, file: File) {
  const question = form.value?.questions.find((q) => q.id === questionId)
  if (!question) return

  // Validate file type
  if (question.allowed_types && question.allowed_types.length > 0) {
    const ext = file.name.split('.').pop()?.toLowerCase() ?? ''
    const allowed = question.allowed_types.map((t) => t.toLowerCase().trim())
    if (!allowed.includes(ext)) {
      validationErrors.value[questionId] = t('forms.view.fileTypeError', {
        types: question.allowed_types.join(', '),
      })
      addHighlight(questionId)
      return
    }
  }

  // Validate file size
  if (question.max_size_mb) {
    const maxBytes = question.max_size_mb * 1024 * 1024
    if (file.size > maxBytes) {
      validationErrors.value[questionId] = t('forms.view.fileSizeError', {
        max: question.max_size_mb,
      })
      addHighlight(questionId)
      return
    }
  }

  clearQuestionError(questionId)
  answers.value[questionId] = file

  // Generate preview for image files
  if (file.type.startsWith('image/')) {
    const url = URL.createObjectURL(file)
    filePreviews.value[questionId] = url
  } else {
    // Remove any stale preview
    revokePreview(questionId)
  }
}

function handleDrop(questionId: string, event: DragEvent) {
  event.preventDefault()
  dragOverQuestions.value.delete(questionId)
  const file = event.dataTransfer?.files?.[0]
  if (file) {
    processFile(questionId, file)
  }
}

function handleDragOver(questionId: string, event: DragEvent) {
  event.preventDefault()
  dragOverQuestions.value.add(questionId)
}

function handleDragLeave(questionId: string) {
  dragOverQuestions.value.delete(questionId)
}

function triggerFileInput(questionId: string) {
  const input = document.getElementById(`file-input-${questionId}`) as HTMLInputElement | null
  if (input) input.click()
}

function removeFile(questionId: string) {
  answers.value[questionId] = ''
  revokePreview(questionId)
  clearQuestionError(questionId)
  // Reset file input
  const input = document.getElementById(`file-input-${questionId}`) as HTMLInputElement | null
  if (input) input.value = ''
}

function revokePreview(questionId: string) {
  if (filePreviews.value[questionId]) {
    URL.revokeObjectURL(filePreviews.value[questionId])
    delete filePreviews.value[questionId]
  }
}

function isFileObject(val: unknown): val is File {
  return val instanceof File
}

function getFileName(val: unknown): string {
  if (val instanceof File) return val.name
  if (val && typeof val === 'object' && 'filename' in val)
    return (val as { filename: string }).filename
  return ''
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

// ── Multiple Choice Toggle ──
function toggleMultipleChoice(questionId: string, optionId: string) {
  if (!Array.isArray(answers.value[questionId])) {
    answers.value[questionId] = []
  }
  const arr = answers.value[questionId] as string[]
  const idx = arr.indexOf(optionId)
  if (idx === -1) arr.push(optionId)
  else arr.splice(idx, 1)
  clearQuestionError(questionId)
}

// ── Rating (Feature 5) ──
function ratingRange(q: Question): number[] {
  const min = q.min ?? 1
  const max = q.max ?? 5
  const range: number[] = []
  for (let i = min; i <= max; i++) range.push(i)
  return range
}

function ratingCount(q: Question): number {
  return (q.max ?? 5) - (q.min ?? 1) + 1
}

function selectRating(questionId: string, value: number) {
  answers.value[questionId] = value
  clearQuestionError(questionId)
}

// ── Answer Change Handlers (clear validation) ──
function onTextInput(questionId: string) {
  clearQuestionError(questionId)
}

function onSelectChange(questionId: string) {
  clearQuestionError(questionId)
}

function onRadioChange(questionId: string) {
  clearQuestionError(questionId)
}

// ── Export ──
async function startExport() {
  exporting.value = true
  exportStatus.value = t('forms.view.exportStarting')
  try {
    const data = await exportForm(formId.value)
    pollExportStatus(data.task_id)
  } catch (e: unknown) {
    error.value = getErrorMessage(e, t('forms.view.exportError'))
    exporting.value = false
    exportStatus.value = ''
  }
}

function pollExportStatus(taskId: string) {
  let attempts = 0
  exportPollTimer = setInterval(async () => {
    if (isUnmounted) {
      clearInterval(exportPollTimer!)
      exportPollTimer = null
      return
    }
    attempts++
    if (attempts > 30) {
      clearInterval(exportPollTimer!)
      exportPollTimer = null
      exporting.value = false
      exportStatus.value = ''
      error.value = t('forms.view.exportTimeout')
      return
    }
    try {
      const data = await getTaskStatus(taskId)
      exportStatus.value = `${t('forms.view.exportStatus')} ${data.status}`
      if (data.status === 'SUCCESS' && data.download_url) {
        clearInterval(exportPollTimer!)
        exportPollTimer = null
        exporting.value = false
        exportStatus.value = ''
        window.open(data.download_url, '_blank')
      } else if (data.status === 'FAILURE') {
        clearInterval(exportPollTimer!)
        exportPollTimer = null
        exporting.value = false
        exportStatus.value = ''
        error.value = t('forms.view.exportFailed')
      }
    } catch {
      /* continue */
    }
  }, 2000)
}

// ── View Submitted Response helpers (Feature 6) ──
function getDisplayAnswer(question: Question, answerVal: unknown): string {
  if (answerVal === null || answerVal === undefined || answerVal === '') {
    return t('forms.view.noAnswer')
  }

  if (question.type === 'single_choice' || question.type === 'dropdown') {
    const opt = question.options?.find((o) => o.id === answerVal)
    return opt?.label ?? String(answerVal)
  }

  if (question.type === 'multiple_choice' && Array.isArray(answerVal)) {
    if (answerVal.length === 0) return t('forms.view.noAnswer')
    return answerVal
      .map((id) => {
        const opt = question.options?.find((o) => o.id === id)
        return opt?.label ?? String(id)
      })
      .join(', ')
  }

  if (question.type === 'rating') {
    return String(answerVal)
  }

  if (question.type === 'file_upload') {
    if (typeof answerVal === 'object' && answerVal !== null && 'filename' in answerVal) {
      return (answerVal as { filename: string }).filename
    }
    return t('forms.view.fileUploaded')
  }

  return String(answerVal)
}

function getResponseAnswers(): Record<string, unknown> {
  if (previousResponse.value) {
    return previousResponse.value.answers
  }
  return submittedAnswers.value
}

function handleClearDraft() {
  clearDraft()
  // Reset answers to defaults
  if (form.value) {
    for (const q of form.value.questions) {
      answers.value[q.id] = q.type === 'multiple_choice' ? [] : q.type === 'rating' ? null : ''
    }
  }
}

function goBackToSig() {
  if (form.value) {
    window.location.href = `/sigs/${form.value.sig_id}`
  }
}

// ── Lifecycle ──
onMounted(() => fetchForm())
onUnmounted(() => {
  isUnmounted = true
  stopAutoSave()
  if (exportPollTimer) clearInterval(exportPollTimer)
  // Clean up highlight timers
  for (const timer of Object.values(highlightTimers)) {
    clearTimeout(timer)
  }
  highlightTimers = {}
  // Revoke all file preview URLs
  for (const url of Object.values(filePreviews.value)) {
    URL.revokeObjectURL(url)
  }
})
</script>

<template>
  <div class="max-w-3xl mx-auto">
    <BaseBreadcrumb
      :items="[
        { label: t('breadcrumb.home'), to: '/' },
        { label: t('breadcrumb.sigs'), to: '/sigs' },
        {
          label: sigName || '...',
          to: form ? `/sigs/${form.sig_id}` : '/sigs',
        },
        {
          label: t('breadcrumb.forms'),
          to: form ? `/sigs/${form.sig_id}/forms` : '/sigs',
        },
        { label: form?.title || '...' },
      ]"
    />

    <SkeletonLoader v-if="loading" :lines="2" variant="card" />
    <div v-else-if="!form" class="text-center py-12">
      <p class="text-muted mb-4">{{ t('forms.view.notFound') }}</p>
    </div>

    <template v-else>
      <div v-if="form.banner_url" class="mb-6">
        <img
          :src="form.banner_url"
          alt="Form banner"
          loading="lazy"
          class="w-full h-48 object-cover rounded-lg"
          width="768"
          height="192"
        />
      </div>

      <!-- Feature 1: Progress Indicator -->
      <div
        v-if="showForm"
        class="sticky top-0 z-30 bg-white/95 backdrop-blur-sm border-b border-border py-2 px-4 mb-4 rounded-lg shadow-sm"
      >
        <div class="flex items-center gap-3">
          <div class="flex-1">
            <div class="w-full h-2 bg-gray-200 rounded-full overflow-hidden">
              <div
                class="h-full bg-brand-600 rounded-full transition-all duration-500 ease-out"
                :style="{ width: `${progressPercent}%` }"
                role="progressbar"
                :aria-valuenow="answeredCount"
                :aria-valuemin="0"
                :aria-valuemax="totalQuestions"
                :aria-label="
                  t('forms.view.progressLabel', { current: answeredCount, total: totalQuestions })
                "
              ></div>
            </div>
          </div>
          <span class="hidden sm:inline text-xs text-muted whitespace-nowrap">
            {{ t('forms.view.progressText', { current: answeredCount, total: totalQuestions }) }}
          </span>
          <span class="sm:hidden text-xs text-muted whitespace-nowrap">
            {{ answeredCount }}/{{ totalQuestions }}
          </span>
        </div>
      </div>

      <BaseCard padding="lg" class="mb-6">
        <div class="flex items-start justify-between">
          <div>
            <h1 class="text-2xl font-bold text-foreground mb-2">{{ form.title }}</h1>
            <div
              v-if="form.description"
              class="prose prose-sm max-w-none text-muted mb-3"
              v-html="form.description"
            ></div>
          </div>
          <BaseBadge :variant="form.is_active ? 'success' : 'danger'">{{
            form.is_active ? t('common.active') : t('common.closed')
          }}</BaseBadge>
        </div>
        <div class="flex items-center gap-4 text-xs text-muted mt-2">
          <span>{{ t('common.by') }} {{ form.created_by_name }}</span>
          <span>{{ form.response_count }} {{ t('forms.view.response') }}</span>
          <span v-if="form.deadline"
            >{{ t('forms.view.deadline') }} {{ new Date(form.deadline).toLocaleString() }}</span
          >
          <span v-if="form.max_respondents"
            >{{ t('forms.view.max') }} {{ form.max_respondents }}</span
          >
        </div>
        <div v-if="auth.isAuthenticated" class="flex items-center gap-2 mt-4">
          <CopyShareLinkButton :url="formShareUrl" />
          <router-link
            v-if="canEdit"
            :to="`/forms/${form.id}/edit`"
            class="text-sm text-brand-600 hover:underline"
            >{{ t('forms.view.editFormBtn') }}</router-link
          >
          <BaseButton
            v-if="canExport"
            variant="secondary"
            size="sm"
            :loading="exporting"
            @click="startExport"
            >{{ t('forms.view.exportCSVBtn') }}</BaseButton
          >
          <span v-if="exportStatus" class="text-xs text-muted">{{ exportStatus }}</span>
        </div>
      </BaseCard>

      <BaseAlert v-if="!form.is_active" type="error" class="mb-6 text-center">{{
        t('forms.view.closedAlert')
      }}</BaseAlert>

      <!-- Feature 3: Draft restored info bar -->
      <BaseAlert
        v-if="draftRestored && showForm"
        type="info"
        dismissible
        class="mb-4"
        @dismiss="handleClearDraft"
      >
        <div class="flex items-center justify-between">
          <span>{{ t('forms.view.draftRestored') }}</span>
          <button
            type="button"
            class="text-xs text-brand-600 hover:underline ml-3 font-medium"
            @click="handleClearDraft"
          >
            {{ t('forms.view.clearDraft') }}
          </button>
        </div>
      </BaseAlert>

      <BaseAlert v-if="error" type="error" class="mb-4">{{ error }}</BaseAlert>

      <!-- Feature 6: Read-only view of submitted / previous response -->
      <template v-if="submitted || previousResponse">
        <BaseAlert v-if="previousResponse && !submitted" type="info" class="mb-6 text-center">
          {{ t('forms.view.alreadySubmitted') }}
        </BaseAlert>
        <BaseAlert v-else-if="submitted" type="success" class="mb-6 text-center">
          {{ message }}
        </BaseAlert>

        <BaseCard padding="lg" class="mb-6">
          <h2 class="text-lg font-semibold text-foreground mb-4">
            {{ t('forms.view.responseSummary') }}
          </h2>
          <div class="divide-y divide-border">
            <div v-for="q in form.questions" :key="q.id" class="py-3">
              <div class="text-sm font-medium text-foreground mb-1">{{ q.label }}</div>
              <div class="text-sm text-muted">
                {{ getDisplayAnswer(q, getResponseAnswers()[q.id]) }}
              </div>
            </div>
          </div>
        </BaseCard>

        <div class="flex justify-center">
          <BaseButton variant="secondary" size="md" @click="goBackToSig">
            {{ t('forms.view.backToSig') }}
          </BaseButton>
        </div>
      </template>

      <!-- Form Questions -->
      <div v-if="showForm" class="space-y-4">
        <BaseCard
          v-for="q in form.questions"
          :key="q.id"
          :ref="(el) => setQuestionRef(q.id, el)"
          :class="[
            'transition-all duration-300',
            highlightedQuestions.has(q.id)
              ? 'ring-2 ring-danger-500 border-l-4 border-l-danger-500'
              : '',
          ]"
        >
          <label class="block text-sm font-medium text-foreground mb-2">
            {{ q.label
            }}<span v-if="q.required" aria-hidden="true" class="text-danger-500"> *</span>
          </label>

          <!-- Text input -->
          <input
            v-if="q.type === 'text'"
            v-model="answers[q.id]"
            type="text"
            :placeholder="q.placeholder || ''"
            :maxlength="q.max_length || undefined"
            :aria-required="q.required"
            class="w-full border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 text-foreground"
            @input="onTextInput(q.id)"
          />

          <!-- Textarea -->
          <textarea
            v-else-if="q.type === 'textarea'"
            v-model="answers[q.id]"
            rows="4"
            :placeholder="q.placeholder || ''"
            :maxlength="q.max_length || undefined"
            :aria-required="q.required"
            class="w-full border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 text-foreground"
            @input="onTextInput(q.id)"
          ></textarea>

          <!-- Single Choice -->
          <div v-else-if="q.type === 'single_choice'" class="space-y-2">
            <label
              v-for="opt in q.options"
              :key="opt.id"
              class="flex items-center gap-2 text-sm text-foreground"
            >
              <input
                type="radio"
                :name="formId + '-' + q.id"
                :value="opt.id"
                v-model="answers[q.id]"
                class="text-brand-600"
                @change="onRadioChange(q.id)"
              />{{ opt.label }}
            </label>
          </div>

          <!-- Multiple Choice -->
          <div v-else-if="q.type === 'multiple_choice'" class="space-y-2">
            <label
              v-for="opt in q.options"
              :key="opt.id"
              class="flex items-center gap-2 text-sm text-foreground"
            >
              <input
                type="checkbox"
                :value="opt.id"
                :checked="(answers[q.id] as string[]).includes(opt.id)"
                @change="toggleMultipleChoice(q.id, opt.id)"
                class="rounded text-brand-600"
              />{{ opt.label }}
            </label>
          </div>

          <!-- Dropdown -->
          <select
            v-else-if="q.type === 'dropdown'"
            v-model="answers[q.id]"
            :aria-required="q.required"
            class="w-full border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 text-foreground"
            @change="onSelectChange(q.id)"
          >
            <option value="">{{ t('forms.view.selectOptionPlaceholder') }}</option>
            <option v-for="opt in q.options" :key="opt.id" :value="opt.id">{{ opt.label }}</option>
          </select>

          <!-- Rating (Feature 5) -->
          <div v-else-if="q.type === 'rating'">
            <div
              class="flex items-center gap-2"
              :class="ratingCount(q) > 7 ? 'flex-wrap' : ''"
              role="group"
              :aria-label="q.label"
            >
              <span class="text-xs text-muted shrink-0">{{ q.labels?.min ?? q.min ?? 1 }}</span>
              <div class="flex flex-wrap gap-2">
                <button
                  v-for="n in ratingRange(q)"
                  :key="n"
                  type="button"
                  @click="selectRating(q.id, n)"
                  :aria-label="t('accessibility.rateNOutOfM', { n, m: q.max ?? 5 })"
                  :aria-pressed="answers[q.id] === n"
                  class="rounded-lg text-sm font-medium transition"
                  :class="[
                    ratingCount(q) > 7 ? 'w-8 h-8 text-xs' : 'w-10 h-10',
                    answers[q.id] === n
                      ? 'bg-brand-600 text-white'
                      : 'bg-surface-alt text-muted hover:bg-gray-100',
                  ]"
                >
                  {{ n }}
                </button>
              </div>
              <span class="text-xs text-muted shrink-0">{{ q.labels?.max ?? q.max ?? 5 }}</span>
            </div>
          </div>

          <!-- File Upload (Feature 4) -->
          <div v-else-if="q.type === 'file_upload'">
            <input
              :id="`file-input-${q.id}`"
              type="file"
              class="sr-only"
              :accept="q.allowed_types?.map((t) => `.${t}`).join(',') || undefined"
              @change="handleFileUpload(q.id, $event)"
            />

            <!-- Drop zone (no file selected) -->
            <div
              v-if="!isFileObject(answers[q.id]) && !answers[q.id]"
              class="border-2 border-dashed rounded-lg p-6 text-center cursor-pointer transition-colors"
              :class="
                dragOverQuestions.has(q.id)
                  ? 'border-brand-500 bg-brand-50'
                  : 'border-border hover:border-brand-400'
              "
              role="button"
              :aria-label="t('forms.view.dropZoneLabel')"
              tabindex="0"
              @click="triggerFileInput(q.id)"
              @drop="handleDrop(q.id, $event)"
              @dragover="handleDragOver(q.id, $event)"
              @dragleave="handleDragLeave(q.id)"
              @keydown.enter="triggerFileInput(q.id)"
              @keydown.space.prevent="triggerFileInput(q.id)"
            >
              <svg
                xmlns="http://www.w3.org/2000/svg"
                class="mx-auto h-8 w-8 text-muted mb-2"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                aria-hidden="true"
              >
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  stroke-width="2"
                  d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
                />
              </svg>
              <p class="text-sm text-muted">{{ t('forms.view.dropZoneText') }}</p>
            </div>

            <!-- File selected: preview -->
            <div
              v-else-if="isFileObject(answers[q.id])"
              class="border border-border rounded-lg p-4"
            >
              <div class="flex items-center gap-3">
                <!-- Image preview thumbnail -->
                <img
                  v-if="filePreviews[q.id]"
                  :src="filePreviews[q.id]"
                  alt="Preview"
                  class="w-12 h-12 object-cover rounded"
                />
                <div
                  v-else
                  class="w-12 h-12 rounded bg-surface-alt flex items-center justify-center"
                >
                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    class="h-6 w-6 text-muted"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                    aria-hidden="true"
                  >
                    <path
                      stroke-linecap="round"
                      stroke-linejoin="round"
                      stroke-width="2"
                      d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                    />
                  </svg>
                </div>
                <div class="flex-1 min-w-0">
                  <p class="text-sm font-medium text-foreground truncate">
                    {{ getFileName(answers[q.id]) }}
                  </p>
                  <p class="text-xs text-muted">
                    {{ formatFileSize((answers[q.id] as File).size) }}
                  </p>
                </div>
                <button
                  type="button"
                  class="text-danger-500 hover:text-danger-700 text-sm font-medium"
                  :aria-label="t('forms.view.removeFile')"
                  @click="removeFile(q.id)"
                >
                  {{ t('forms.view.removeFile') }}
                </button>
              </div>
            </div>

            <!-- Upload spinner -->
            <div v-if="uploadingFiles.includes(q.id)" class="flex items-center gap-2 mt-2">
              <div
                class="animate-spin rounded-full h-4 w-4 border-2 border-brand-600 border-t-transparent"
              ></div>
              <span class="text-xs text-muted">{{ t('forms.view.uploading') }}</span>
            </div>

            <p v-if="q.allowed_types && q.allowed_types.length" class="text-xs text-muted mt-2">
              {{ t('forms.view.allowedTypes') }} {{ q.allowed_types.join(', ') }}
            </p>
            <p v-if="q.max_size_mb" class="text-xs text-muted mt-1">
              {{ t('forms.view.maxFileSize', { max: q.max_size_mb }) }}
            </p>
          </div>

          <!-- Character count for text fields -->
          <p
            v-if="(q.type === 'text' || q.type === 'textarea') && q.max_length"
            class="text-xs text-muted mt-1 text-right"
          >
            {{ (answers[q.id] as string)?.length || 0 }} / {{ q.max_length }}
          </p>

          <!-- Feature 2: Per-question validation error -->
          <p v-if="validationErrors[q.id]" class="text-xs text-danger-600 mt-1" role="alert">
            {{ validationErrors[q.id] }}
          </p>
        </BaseCard>

        <div class="flex justify-end pt-4">
          <BaseButton size="lg" :loading="submitting" @click="submitForm">{{
            t('forms.view.submitBtn')
          }}</BaseButton>
        </div>
      </div>

      <BaseAlert v-if="!auth.isAuthenticated && form.is_active" type="info" class="text-center">
        {{ t('forms.view.loginPrompt') }}
        <router-link to="/login" class="text-brand-600 hover:underline font-medium">{{
          t('forms.view.loginLink')
        }}</router-link>
        {{ t('forms.view.submitPromptSuffix') }}
      </BaseAlert>
    </template>

    <!-- Feature 7: Back to Top -->
    <BackToTop />
  </div>
</template>

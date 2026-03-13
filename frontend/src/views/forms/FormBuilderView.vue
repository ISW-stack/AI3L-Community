<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import DOMPurify from 'dompurify'
import type { Question, QuestionOption } from '@/types'
import { getErrorMessage } from '@/utils/error'
import { getForm, createForm, updateForm } from '@/api/forms'
import { getSig } from '@/api/sigs'
import { uploadEditorFile } from '@/api/files'
import { useFormHistory } from '@/composables/useFormHistory'
import { useFormDraft } from '@/composables/useFormDraft'
import BaseCard from '@/components/base/BaseCard.vue'
import BaseBreadcrumb from '@/components/base/BaseBreadcrumb.vue'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseAlert from '@/components/base/BaseAlert.vue'
import BaseInput from '@/components/base/BaseInput.vue'
import BaseModal from '@/components/base/BaseModal.vue'
import TiptapEditor from '@/components/TiptapEditor.vue'
import SkeletonLoader from '@/components/SkeletonLoader.vue'
import EmptyState from '@/components/EmptyState.vue'

const { t } = useI18n()

const QUESTION_TYPES = [
  { value: 'text', key: 'forms.builder.questionType.shortText' },
  { value: 'textarea', key: 'forms.builder.questionType.longText' },
  { value: 'single_choice', key: 'forms.builder.questionType.singleChoice' },
  { value: 'multiple_choice', key: 'forms.builder.questionType.multipleChoice' },
  { value: 'dropdown', key: 'forms.builder.questionType.dropdown' },
  { value: 'rating', key: 'forms.builder.questionType.rating' },
  { value: 'file_upload', key: 'forms.builder.questionType.fileUpload' },
]

const route = useRoute()
const router = useRouter()
const isEdit = computed(() => !!route.params.formId)
const formId = computed(() => route.params.formId as string)
const sigId = computed(() => route.params.sigId as string)

const title = ref('')
const description = ref('')
const bannerUrl = ref('')
const deadline = ref('')
const maxRespondents = ref<number | null>(null)
const questions = ref<Question[]>([])
const isSchemaLocked = ref(false)
const allowNonMembers = ref(false)
const loading = ref(false)
const saving = ref(false)
const message = ref('')
const error = ref('')
const showPreview = ref(false)
const sigName = ref('')
const breadcrumbSigId = ref('')

// Feature 4: Collapse/Expand
const collapsedQuestions = ref<Set<string>>(new Set())

// Feature 8: Mobile preview toggle
const previewMode = ref<'desktop' | 'mobile'>('desktop')

// Feature 2: Drag-and-drop state
const dragIndex = ref<number | null>(null)
const dropTargetIndex = ref<number | null>(null)

// Feature 6: Undo/Redo
const history = useFormHistory()

// Feature 7: Auto-save draft
// Pass getter functions so the draft key is computed lazily in onMounted,
// after route params are guaranteed to be resolved.
const draft = useFormDraft(
  () => (isEdit.value ? undefined : sigId.value),
  () => (isEdit.value ? formId.value : undefined),
)
const showDraftBanner = ref(false)
let autoSaveTimer: ReturnType<typeof setInterval> | null = null

const hasInvalidRating = computed(() =>
  questions.value.some((q) => q.type === 'rating' && (q.min ?? 1) >= (q.max ?? 5)),
)

const minDeadline = computed(() => {
  const now = new Date()
  now.setMinutes(now.getMinutes() - now.getTimezoneOffset())
  return now.toISOString().slice(0, 16)
})

// ── Question CRUD ──

function createQuestion(): Question {
  return {
    id: crypto.randomUUID(),
    type: 'text',
    label: '',
    required: true,
    placeholder: '',
    max_length: undefined,
    options: [],
    min: 1,
    max: 5,
    labels: undefined,
    allowed_types: [],
    max_size_mb: undefined,
  }
}

function addQuestion(): void {
  questions.value.push(createQuestion())
  recordHistory()
  scrollToQuestion(questions.value.length - 1)
}

function insertQuestionAt(index: number): void {
  const newQ = createQuestion()
  questions.value.splice(index, 0, newQ)
  // Update collapsed set — IDs don't change, so no adjustment needed
  recordHistory()
  scrollToQuestion(index)
}

function removeQuestion(index: number): void {
  const qId = questions.value[index].id
  collapsedQuestions.value.delete(qId)
  questions.value.splice(index, 1)
  recordHistory()
}

function moveQuestion(index: number, direction: -1 | 1): void {
  const target = index + direction
  if (target < 0 || target >= questions.value.length) return
  const temp = questions.value[index]
  questions.value[index] = questions.value[target]
  questions.value[target] = temp
  recordHistory()
}

// Feature 3: Duplicate question
function duplicateQuestion(index: number): void {
  const original = questions.value[index]
  const cloned: Question = JSON.parse(JSON.stringify(original))
  cloned.id = crypto.randomUUID()
  if (cloned.options) {
    cloned.options = cloned.options.map((opt: QuestionOption) => ({
      ...opt,
      id: crypto.randomUUID(),
    }))
  }
  questions.value.splice(index + 1, 0, cloned)
  recordHistory()
  scrollToQuestion(index + 1)
}

function addOption(question: Question): void {
  if (!question.options) question.options = []
  question.options.push({ id: crypto.randomUUID(), label: '' })
  recordHistory()
}

function removeOption(question: Question, optIndex: number): void {
  question.options?.splice(optIndex, 1)
  recordHistory()
}

// Feature 5: Option reordering
function moveOption(question: Question, optIndex: number, direction: -1 | 1): void {
  if (!question.options) return
  const target = optIndex + direction
  if (target < 0 || target >= question.options.length) return
  const temp = question.options[optIndex]
  question.options[optIndex] = question.options[target]
  question.options[target] = temp
  recordHistory()
}

function updateAllowedTypes(question: Question, event: Event): void {
  question.allowed_types = (event.target as HTMLInputElement).value
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean)
}

// Feature 4: Collapse/Expand
function toggleCollapse(questionId: string): void {
  if (collapsedQuestions.value.has(questionId)) {
    collapsedQuestions.value.delete(questionId)
  } else {
    collapsedQuestions.value.add(questionId)
  }
}

function collapseAll(): void {
  for (const q of questions.value) {
    collapsedQuestions.value.add(q.id)
  }
}

function expandAll(): void {
  collapsedQuestions.value.clear()
}

function isCollapsed(questionId: string): boolean {
  return collapsedQuestions.value.has(questionId)
}

function getTypeBadgeText(type: string): string {
  const found = QUESTION_TYPES.find((qt) => qt.value === type)
  return found ? t(found.key) : type
}

// ── Feature 2: Drag and Drop ──

function handleDragStart(event: DragEvent, index: number): void {
  dragIndex.value = index
  if (event.dataTransfer) {
    event.dataTransfer.effectAllowed = 'move'
    event.dataTransfer.setData('text/plain', String(index))
  }
}

function handleDragOver(event: DragEvent, index: number): void {
  event.preventDefault()
  if (event.dataTransfer) {
    event.dataTransfer.dropEffect = 'move'
  }
  dropTargetIndex.value = index
}

function handleDragLeave(): void {
  dropTargetIndex.value = null
}

function handleDrop(event: DragEvent, targetIndex: number): void {
  event.preventDefault()
  if (dragIndex.value === null || dragIndex.value === targetIndex) {
    dragIndex.value = null
    dropTargetIndex.value = null
    return
  }
  const moved = questions.value.splice(dragIndex.value, 1)[0]
  const insertAt = targetIndex > dragIndex.value ? targetIndex - 1 : targetIndex
  questions.value.splice(insertAt, 0, moved)
  dragIndex.value = null
  dropTargetIndex.value = null
  recordHistory()
}

function handleDragEnd(): void {
  dragIndex.value = null
  dropTargetIndex.value = null
}

// Touch drag support
let touchStartY = 0
let touchDragIndex: number | null = null

function handleTouchStart(event: TouchEvent, index: number): void {
  touchStartY = event.touches[0].clientY
  touchDragIndex = index
}

function handleTouchMove(event: TouchEvent): void {
  if (touchDragIndex === null) return
  event.preventDefault()
}

function handleTouchEnd(event: TouchEvent): void {
  if (touchDragIndex === null) return
  const endY = event.changedTouches[0].clientY
  const diff = endY - touchStartY
  if (Math.abs(diff) > 50) {
    const direction = diff > 0 ? 1 : -1
    moveQuestion(touchDragIndex, direction as -1 | 1)
  }
  touchDragIndex = null
}

// ── Feature 6: Undo/Redo ──

function recordHistory(): void {
  history.pushState(questions.value)
  saveDraftNow()
}

function handleUndo(): void {
  const state = history.undo()
  if (state) {
    questions.value = state
  }
}

function handleRedo(): void {
  const state = history.redo()
  if (state) {
    questions.value = state
  }
}

function handleKeyboardShortcut(event: KeyboardEvent): void {
  if ((event.ctrlKey || event.metaKey) && event.key === 'z') {
    if (event.shiftKey) {
      event.preventDefault()
      handleRedo()
    } else {
      event.preventDefault()
      handleUndo()
    }
  }
}

// ── Feature 7: Auto-save ──

function getDraftData() {
  return {
    title: title.value,
    description: description.value,
    bannerUrl: bannerUrl.value,
    deadline: deadline.value,
    maxRespondents: maxRespondents.value,
    allowNonMembers: allowNonMembers.value,
    questions: questions.value,
  }
}

function saveDraftNow(): void {
  draft.saveDraft(getDraftData())
}

function restoreDraft(): void {
  const data = draft.loadDraft()
  if (!data) return
  title.value = data.title
  description.value = data.description
  bannerUrl.value = data.bannerUrl
  deadline.value = data.deadline
  maxRespondents.value = data.maxRespondents
  allowNonMembers.value = data.allowNonMembers
  questions.value = data.questions
  showDraftBanner.value = false
  history.pushState(questions.value)
}

function discardDraft(): void {
  draft.discardDraft()
  showDraftBanner.value = false
}

function startAutoSave(): void {
  autoSaveTimer = setInterval(saveDraftNow, 30000)
}

function stopAutoSave(): void {
  if (autoSaveTimer !== null) {
    clearInterval(autoSaveTimer)
    autoSaveTimer = null
  }
}

// ── Scroll helpers ──

function scrollToQuestion(index: number): void {
  nextTick(() => {
    const el = document.getElementById(`question-card-${index}`)
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'center' })
    }
  })
}

// Feature 8: Preview toggle
function setPreviewDesktop(): void {
  previewMode.value = 'desktop'
}

function setPreviewMobile(): void {
  previewMode.value = 'mobile'
}

// ── Banner upload ──

async function uploadBanner(event: Event): Promise<void> {
  const file = (event.target as HTMLInputElement).files?.[0]
  if (!file) return
  try {
    const data = await uploadEditorFile(file)
    bannerUrl.value = data.url
  } catch {
    error.value = t('forms.builder.uploadBannerError')
  }
}

// ── Fetch/Save ──

async function fetchForm(): Promise<void> {
  if (!isEdit.value) return
  loading.value = true
  try {
    const data = await getForm(formId.value)
    title.value = data.title
    description.value = data.description || ''
    bannerUrl.value = data.banner_url || ''
    deadline.value = data.deadline ? data.deadline.slice(0, 16) : ''
    maxRespondents.value = data.max_respondents
    isSchemaLocked.value = data.is_schema_locked
    allowNonMembers.value = data.allow_non_members ?? false
    questions.value = data.questions.map((q: Question) => ({
      id: q.id,
      type: q.type,
      label: q.label || '',
      required: q.required ?? true,
      placeholder: q.placeholder || '',
      max_length: q.max_length ?? undefined,
      options: q.options || [],
      min: q.min ?? 1,
      max: q.max ?? 5,
      labels: q.labels ?? undefined,
      allowed_types: q.allowed_types || [],
      max_size_mb: q.max_size_mb ?? undefined,
    }))
    breadcrumbSigId.value = data.sig_id
    // Collapse existing questions in edit mode
    for (const q of questions.value) {
      collapsedQuestions.value.add(q.id)
    }
    history.pushState(questions.value)
    try {
      const sigData = await getSig(data.sig_id)
      sigName.value = sigData.name
    } catch {
      /* breadcrumb will show fallback */
    }
  } catch {
    error.value = t('forms.builder.loadError')
  } finally {
    loading.value = false
  }
}

function serializeQuestion(q: Question) {
  const base: Record<string, unknown> = {
    id: q.id,
    type: q.type,
    label: q.label.trim(),
    required: q.required,
  }
  if (q.type === 'text' || q.type === 'textarea') {
    if (q.placeholder) base.placeholder = q.placeholder
    if (q.max_length) base.max_length = q.max_length
  }
  if (['single_choice', 'multiple_choice', 'dropdown'].includes(q.type)) {
    base.options = (q.options ?? [])
      .filter((o) => o.label.trim())
      .map((o) => ({ id: o.id, label: o.label.trim() }))
  }
  if (q.type === 'rating') {
    base.min = q.min ?? 1
    base.max = q.max ?? 5
  }
  if (q.type === 'file_upload') {
    if ((q.allowed_types?.length ?? 0) > 0) base.allowed_types = q.allowed_types
    if (q.max_size_mb) base.max_size_mb = q.max_size_mb
  }
  return base
}

async function saveForm(): Promise<void> {
  error.value = ''
  message.value = ''
  if (!title.value.trim()) {
    error.value = t('forms.builder.validation.titleRequired')
    return
  }
  if (deadline.value && new Date(deadline.value) <= new Date()) {
    error.value = t('forms.builder.validation.deadlineInFuture')
    return
  }
  if (questions.value.length === 0) {
    error.value = t('forms.builder.validation.questionRequired')
    return
  }
  for (const q of questions.value) {
    if (!q.label.trim()) {
      error.value = t('forms.builder.validation.labelRequired')
      return
    }
    if (
      ['single_choice', 'multiple_choice', 'dropdown'].includes(q.type) &&
      (q.options?.length ?? 0) < 2
    ) {
      error.value = t('forms.builder.validation.optionsRequired', { label: q.label })
      return
    }
    if (q.type === 'rating' && (q.min ?? 1) >= (q.max ?? 5)) {
      error.value = t('forms.builder.validation.ratingError', { label: q.label })
      return
    }
  }
  saving.value = true
  try {
    const payload: {
      title: string
      description: string | null
      banner_url: string | null
      deadline: string | null
      max_respondents: number | null
      allow_non_members: boolean
      questions?: unknown[]
    } = {
      title: title.value.trim(),
      description: description.value.trim() || null,
      banner_url: bannerUrl.value.trim() || null,
      deadline: deadline.value ? new Date(deadline.value).toISOString() : null,
      max_respondents: maxRespondents.value || null,
      allow_non_members: allowNonMembers.value,
    }
    if (isEdit.value) {
      if (!isSchemaLocked.value) payload.questions = questions.value.map(serializeQuestion)
      await updateForm(formId.value, payload)
      message.value = t('forms.builder.updateSuccess')
    } else {
      const serialized = questions.value.map(serializeQuestion)
      const data = await createForm(sigId.value, { ...payload, questions: serialized })
      message.value = t('forms.builder.successMessage')
      router.replace(`/forms/${data.id}`)
    }
    // Clear draft on successful save
    draft.discardDraft()
  } catch (e: unknown) {
    error.value = getErrorMessage(e, t('forms.builder.saveError'))
  } finally {
    saving.value = false
  }
}

async function fetchSigName(id: string): Promise<void> {
  breadcrumbSigId.value = id
  try {
    const sigData = await getSig(id)
    sigName.value = sigData.name
  } catch {
    /* breadcrumb will show fallback */
  }
}

// NOTE: The broad watch on question properties was removed to prevent triple-saves.
// History is now recorded explicitly in each discrete mutation function (addQuestion,
// insertQuestionAt, removeQuestion, moveQuestion, duplicateQuestion, addOption,
// removeOption, moveOption, handleDrop). The 30-second auto-save timer is the safety net.

onMounted(() => {
  // Re-check draft now that route params are guaranteed to be resolved.
  // The composable uses lazy getter functions, so this reads from the correct key.
  draft.checkForDraft()

  if (isEdit.value) {
    fetchForm()
  } else {
    // Check for draft before adding default question
    if (draft.hasDraft.value) {
      showDraftBanner.value = true
      // Still add a default question in case user dismisses draft
      addQuestion()
    } else {
      addQuestion()
    }
    if (sigId.value) fetchSigName(sigId.value)
  }
  document.addEventListener('keydown', handleKeyboardShortcut)
  startAutoSave()
})

onUnmounted(() => {
  document.removeEventListener('keydown', handleKeyboardShortcut)
  stopAutoSave()
})
</script>

<template>
  <div class="max-w-3xl mx-auto pb-24 overflow-x-hidden">
    <BaseBreadcrumb
      :items="[
        { label: t('breadcrumb.home'), to: '/' },
        { label: t('breadcrumb.sigs'), to: '/sigs' },
        {
          label: sigName || '...',
          to: breadcrumbSigId ? `/sigs/${breadcrumbSigId}` : '/sigs',
        },
        {
          label: t('breadcrumb.forms'),
          to: breadcrumbSigId ? `/sigs/${breadcrumbSigId}/forms` : '/sigs',
        },
        { label: isEdit ? title || t('forms.builder.editTitle') : t('forms.builder.createTitle') },
      ]"
    />

    <h1 class="text-2xl font-bold text-foreground mb-6">
      {{ isEdit ? t('forms.builder.editTitle') : t('forms.builder.createTitle') }}
    </h1>

    <SkeletonLoader v-if="loading" :lines="3" variant="card" />

    <template v-else>
      <!-- Feature 7: Draft restoration banner -->
      <BaseAlert v-if="showDraftBanner" type="warning" class="mb-4">
        <div class="flex flex-wrap items-center gap-2">
          <span>{{
            t('forms.builder.draftFound', {
              time: new Date(draft.draftTime.value).toLocaleString(),
            })
          }}</span>
          <button class="text-sm font-medium text-brand-600 hover:underline" @click="restoreDraft">
            {{ t('forms.builder.draftRestore') }}
          </button>
          <button class="text-sm font-medium text-danger-500 hover:underline" @click="discardDraft">
            {{ t('forms.builder.draftDiscard') }}
          </button>
        </div>
      </BaseAlert>

      <BaseAlert v-if="message" type="success" class="mb-4">{{ message }}</BaseAlert>
      <BaseAlert v-if="error" type="error" class="mb-4">{{ error }}</BaseAlert>

      <BaseCard padding="lg" class="mb-6 space-y-4">
        <div>
          <label class="block text-sm font-medium text-foreground mb-1">{{
            t('forms.builder.bannerLabel')
          }}</label>
          <div v-if="bannerUrl" class="mb-2">
            <img
              :src="bannerUrl"
              alt="Banner"
              loading="lazy"
              class="w-full h-40 object-cover rounded-lg"
              width="768"
              height="160"
            />
          </div>
          <input
            type="file"
            accept="image/png,image/jpeg,image/webp"
            @change="uploadBanner"
            class="text-sm text-muted"
          />
        </div>
        <BaseInput
          v-model="title"
          :label="t('forms.builder.titleLabel')"
          :placeholder="t('forms.builder.titlePlaceholder')"
        />
        <div>
          <label class="block text-sm font-medium text-foreground mb-1">{{
            t('forms.builder.descLabel')
          }}</label>
          <TiptapEditor v-model="description" />
        </div>
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label class="block text-sm font-medium text-foreground mb-1">{{
              t('forms.builder.deadlineLabel')
            }}</label>
            <input
              v-model="deadline"
              type="datetime-local"
              :min="minDeadline"
              class="w-full border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 text-foreground"
            />
          </div>
          <div>
            <label class="block text-sm font-medium text-foreground mb-1">{{
              t('forms.builder.maxRespondentsLabel')
            }}</label>
            <input
              v-model.number="maxRespondents"
              type="number"
              min="1"
              :placeholder="t('forms.builder.maxRespondentsPlaceholder')"
              class="w-full border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 text-foreground"
            />
          </div>
        </div>
        <label class="flex items-center gap-2 text-sm text-foreground mt-4">
          <input type="checkbox" v-model="allowNonMembers" class="rounded" />
          {{ t('forms.builder.allowNonMembers') }}
        </label>
        <p class="text-xs text-muted mt-1">
          {{ t('forms.builder.allowNonMembersHint') }}
        </p>
      </BaseCard>

      <div class="mb-6">
        <!-- Toolbar: title + actions -->
        <div class="flex items-center justify-between mb-3 flex-wrap gap-2">
          <h2 class="text-lg font-semibold text-foreground">
            {{ t('forms.builder.questionsTitle') }}
          </h2>
          <div class="flex items-center gap-2 flex-wrap">
            <!-- Feature 6: Undo/Redo buttons -->
            <button
              :disabled="!history.canUndo.value"
              :aria-label="t('forms.builder.undoBtn')"
              :title="t('forms.builder.undoBtn')"
              class="text-sm px-2 py-1 rounded border border-border text-muted hover:text-foreground disabled:opacity-30 transition"
              @click="handleUndo"
            >
              &#x21B6;
            </button>
            <button
              :disabled="!history.canRedo.value"
              :aria-label="t('forms.builder.redoBtn')"
              :title="t('forms.builder.redoBtn')"
              class="text-sm px-2 py-1 rounded border border-border text-muted hover:text-foreground disabled:opacity-30 transition"
              @click="handleRedo"
            >
              &#x21B7;
            </button>
            <!-- Feature 4: Collapse/Expand all -->
            <button
              v-if="questions.length > 1"
              class="text-sm px-2 py-1 rounded border border-border text-muted hover:text-foreground transition"
              :aria-label="t('forms.builder.collapseAllBtn')"
              @click="collapseAll"
            >
              {{ t('forms.builder.collapseAllBtn') }}
            </button>
            <button
              v-if="questions.length > 1"
              class="text-sm px-2 py-1 rounded border border-border text-muted hover:text-foreground transition"
              :aria-label="t('forms.builder.expandAllBtn')"
              @click="expandAll"
            >
              {{ t('forms.builder.expandAllBtn') }}
            </button>
            <BaseButton v-if="!isSchemaLocked" size="sm" @click="addQuestion">{{
              t('forms.builder.addQuestionBtn')
            }}</BaseButton>
          </div>
        </div>

        <BaseAlert v-if="isSchemaLocked" type="warning" class="mb-4">{{
          t('forms.builder.schemaLockedWarning')
        }}</BaseAlert>

        <div class="space-y-1">
          <template v-for="(q, i) in questions" :key="q.id">
            <!-- Feature 1: Insert question divider (between questions) -->
            <div
              v-if="i > 0 && !isSchemaLocked"
              class="group relative flex items-center justify-center py-1"
              @dragover="handleDragOver($event, i)"
              @dragleave="handleDragLeave"
              @drop="handleDrop($event, i)"
            >
              <div
                class="w-full border-t border-dashed transition-colors"
                :class="
                  dropTargetIndex === i
                    ? 'border-brand-500 border-2'
                    : 'border-transparent group-hover:border-border'
                "
              ></div>
              <button
                class="absolute opacity-0 group-hover:opacity-100 transition-opacity bg-surface border border-border rounded-full w-6 h-6 flex items-center justify-center text-xs text-muted hover:text-brand-600 hover:border-brand-500 shadow-sm z-10"
                :aria-label="t('forms.builder.insertQuestionHere')"
                @click="insertQuestionAt(i)"
              >
                +
              </button>
            </div>

            <!-- Question card -->
            <div
              :id="`question-card-${i}`"
              :draggable="!isSchemaLocked"
              class="bg-surface rounded-lg shadow p-5 border-l-4 transition-all duration-200"
              :class="[
                isSchemaLocked ? 'border-gray-300 opacity-75' : 'border-brand-500',
                dragIndex === i ? 'opacity-50 scale-95' : '',
              ]"
              @dragstart="handleDragStart($event, i)"
              @dragover="handleDragOver($event, i)"
              @dragleave="handleDragLeave"
              @drop="handleDrop($event, i)"
              @dragend="handleDragEnd"
            >
              <!-- Question header row -->
              <div class="flex items-center justify-between mb-1">
                <div class="flex items-center gap-2">
                  <!-- Feature 2: Drag handle -->
                  <span
                    v-if="!isSchemaLocked"
                    class="cursor-grab active:cursor-grabbing text-muted hover:text-foreground select-none text-lg leading-none"
                    :aria-label="t('forms.builder.dragHandle')"
                    @touchstart="handleTouchStart($event, i)"
                    @touchmove="handleTouchMove($event)"
                    @touchend="handleTouchEnd($event)"
                    >&#x2261;</span
                  >
                  <!-- Feature 4: Collapse toggle -->
                  <button
                    class="text-muted hover:text-foreground transition text-sm px-1"
                    :aria-label="
                      isCollapsed(q.id)
                        ? t('forms.builder.expandQuestion')
                        : t('forms.builder.collapseQuestion')
                    "
                    @click="toggleCollapse(q.id)"
                  >
                    <span v-if="isCollapsed(q.id)">&#x25B6;</span>
                    <span v-else>&#x25BC;</span>
                  </button>
                  <span class="text-sm font-medium text-muted">
                    {{ t('forms.builder.questionLabel') }} {{ i + 1 }}
                  </span>
                  <!-- Collapsed: show type badge + label + required -->
                  <template v-if="isCollapsed(q.id)">
                    <span class="text-xs bg-brand-50 text-brand-700 px-1.5 py-0.5 rounded">
                      {{ getTypeBadgeText(q.type) }}
                    </span>
                    <span class="text-sm text-foreground truncate max-w-xs">
                      {{ q.label || t('forms.builder.untitledQuestion') }}
                    </span>
                    <span v-if="q.required" class="text-danger-500 text-xs">*</span>
                  </template>
                </div>
                <div v-if="!isSchemaLocked" class="flex items-center gap-1">
                  <button
                    @click="moveQuestion(i, -1)"
                    :disabled="i === 0"
                    :aria-label="t('accessibility.moveQuestionUp')"
                    class="text-muted hover:text-foreground disabled:opacity-30 px-1"
                  >
                    &uarr;
                  </button>
                  <button
                    @click="moveQuestion(i, 1)"
                    :disabled="i === questions.length - 1"
                    :aria-label="t('accessibility.moveQuestionDown')"
                    class="text-muted hover:text-foreground disabled:opacity-30 px-1"
                  >
                    &darr;
                  </button>
                  <!-- Feature 3: Duplicate button -->
                  <button
                    @click="duplicateQuestion(i)"
                    :aria-label="t('forms.builder.duplicateQuestion')"
                    class="text-muted hover:text-brand-600 px-1"
                    :title="t('forms.builder.duplicateQuestion')"
                  >
                    &#x2398;
                  </button>
                  <button
                    @click="removeQuestion(i)"
                    :aria-label="t('accessibility.deleteQuestion')"
                    class="text-danger-500 hover:text-danger-600 px-1 ml-2"
                  >
                    &times;
                  </button>
                </div>
              </div>

              <!-- Expanded content -->
              <div v-if="!isCollapsed(q.id)" class="mt-2">
                <div class="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-3">
                  <div>
                    <label class="block text-xs text-muted mb-1">{{
                      t('forms.builder.typeLabel')
                    }}</label>
                    <select
                      v-model="q.type"
                      :disabled="isSchemaLocked"
                      class="w-full border border-border rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                    >
                      <option v-for="qt in QUESTION_TYPES" :key="qt.value" :value="qt.value">
                        {{ t(qt.key) }}
                      </option>
                    </select>
                  </div>
                  <div class="sm:col-span-2">
                    <label class="block text-xs text-muted mb-1">{{
                      t('forms.builder.labelRequired')
                    }}</label>
                    <input
                      v-model="q.label"
                      :disabled="isSchemaLocked"
                      type="text"
                      :placeholder="t('forms.builder.labelPlaceholder')"
                      class="w-full border border-border rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                    />
                  </div>
                </div>

                <label class="flex items-center gap-2 text-sm text-foreground mb-3">
                  <input
                    type="checkbox"
                    v-model="q.required"
                    :disabled="isSchemaLocked"
                    class="rounded"
                  />
                  {{ t('forms.builder.requiredCheckbox') }}
                </label>

                <div v-if="q.type === 'text' || q.type === 'textarea'" class="space-y-2">
                  <input
                    v-model="q.placeholder"
                    :disabled="isSchemaLocked"
                    type="text"
                    :placeholder="t('forms.builder.placeholderLabel')"
                    class="w-full border border-border rounded-lg px-2 py-1.5 text-sm"
                  />
                  <div class="flex items-center gap-2">
                    <label class="text-xs text-muted">{{
                      t('forms.builder.maxLengthLabel')
                    }}</label>
                    <input
                      v-model.number="q.max_length"
                      :disabled="isSchemaLocked"
                      type="number"
                      min="1"
                      :placeholder="t('forms.builder.maxLengthPlaceholder')"
                      class="w-24 border border-border rounded-lg px-2 py-1.5 text-sm"
                    />
                  </div>
                </div>

                <div
                  v-if="['single_choice', 'multiple_choice', 'dropdown'].includes(q.type)"
                  class="space-y-2"
                >
                  <div v-for="(opt, oi) in q.options" :key="opt.id" class="flex items-center gap-2">
                    <!-- Feature 5: Option reorder arrows -->
                    <div v-if="!isSchemaLocked" class="flex flex-col">
                      <button
                        :disabled="oi === 0"
                        :aria-label="t('forms.builder.moveOptionUp')"
                        class="text-xs text-muted hover:text-foreground disabled:opacity-30 leading-none"
                        @click="moveOption(q, oi, -1)"
                      >
                        &#x25B2;
                      </button>
                      <button
                        :disabled="oi === (q.options?.length ?? 0) - 1"
                        :aria-label="t('forms.builder.moveOptionDown')"
                        class="text-xs text-muted hover:text-foreground disabled:opacity-30 leading-none"
                        @click="moveOption(q, oi, 1)"
                      >
                        &#x25BC;
                      </button>
                    </div>
                    <input
                      v-model="opt.label"
                      :disabled="isSchemaLocked"
                      type="text"
                      :placeholder="`Option ${oi + 1}`"
                      :aria-label="t('accessibility.optionN', { n: oi + 1 })"
                      class="flex-1 border border-border rounded-lg px-2 py-1.5 text-sm"
                    />
                    <button
                      v-if="!isSchemaLocked"
                      @click="removeOption(q, oi)"
                      :aria-label="t('accessibility.removeOption')"
                      class="text-danger-500 hover:text-danger-600 text-sm"
                    >
                      &times;
                    </button>
                  </div>
                  <button
                    v-if="!isSchemaLocked"
                    @click="addOption(q)"
                    class="text-sm text-brand-600 hover:underline"
                  >
                    {{ t('forms.builder.addOptionBtn') }}
                  </button>
                </div>

                <div v-if="q.type === 'rating'">
                  <div class="flex items-center gap-4">
                    <div class="flex items-center gap-2">
                      <label class="text-xs text-muted">{{ t('forms.builder.minLabel') }}</label
                      ><input
                        v-model.number="q.min"
                        :disabled="isSchemaLocked"
                        type="number"
                        class="w-16 border border-border rounded-lg px-2 py-1.5 text-sm"
                      />
                    </div>
                    <div class="flex items-center gap-2">
                      <label class="text-xs text-muted">{{ t('forms.builder.maxLabel') }}</label
                      ><input
                        v-model.number="q.max"
                        :disabled="isSchemaLocked"
                        type="number"
                        class="w-16 border border-border rounded-lg px-2 py-1.5 text-sm"
                      />
                    </div>
                  </div>
                  <p v-if="(q.min ?? 1) >= (q.max ?? 5)" class="text-sm text-danger-600 mt-1">
                    {{ t('forms.builder.minMaxError') }}
                  </p>
                </div>

                <div v-if="q.type === 'file_upload'" class="space-y-2">
                  <div class="flex items-center gap-2">
                    <label class="text-xs text-muted">{{
                      t('forms.builder.allowedTypesLabel')
                    }}</label>
                    <input
                      :value="(q.allowed_types ?? []).join(', ')"
                      @input="updateAllowedTypes(q, $event)"
                      :disabled="isSchemaLocked"
                      type="text"
                      :placeholder="t('forms.builder.allowedTypesPlaceholder')"
                      class="flex-1 border border-border rounded-lg px-2 py-1.5 text-sm"
                    />
                  </div>
                  <div class="flex items-center gap-2">
                    <label class="text-xs text-muted">{{ t('forms.builder.maxSizeLabel') }}</label>
                    <input
                      v-model.number="q.max_size_mb"
                      :disabled="isSchemaLocked"
                      type="number"
                      min="1"
                      :placeholder="t('forms.builder.maxSizePlaceholder')"
                      class="w-24 border border-border rounded-lg px-2 py-1.5 text-sm"
                    />
                  </div>
                </div>
              </div>
            </div>
          </template>
        </div>
      </div>

      <div class="flex justify-end gap-3">
        <BaseButton variant="secondary" size="lg" @click="showPreview = true">{{
          t('forms.builder.previewBtn')
        }}</BaseButton>
        <BaseButton size="lg" :loading="saving" :disabled="hasInvalidRating" @click="saveForm">{{
          isEdit ? t('forms.builder.updateBtn') : t('forms.builder.createBtn')
        }}</BaseButton>
      </div>
    </template>

    <!-- Feature 1: Floating Action Button -->
    <button
      v-if="!isSchemaLocked && !loading"
      class="fixed z-40 bg-brand-600 hover:bg-brand-700 text-white rounded-full shadow-lg flex items-center justify-center transition-all"
      style="
        bottom: calc(2rem + env(safe-area-inset-bottom, 0px));
        right: calc(2rem + env(safe-area-inset-right, 0px));
      "
      :class="['w-12 h-12 sm:w-auto sm:h-auto sm:px-4 sm:py-3']"
      :aria-label="t('forms.builder.addQuestionBtn')"
      @click="addQuestion"
    >
      <span class="text-xl leading-none sm:hidden">+</span>
      <span class="hidden sm:inline text-sm font-medium">{{
        t('forms.builder.addQuestionBtn')
      }}</span>
    </button>

    <!-- Preview modal -->
    <BaseModal v-model="showPreview" :title="title || t('forms.builder.createTitle')" size="xl">
      <div class="space-y-4">
        <!-- Feature 8: Preview mode toggle -->
        <div class="flex items-center justify-center gap-2 mb-2">
          <button
            class="px-3 py-1 text-sm rounded-l-lg border transition"
            :class="
              previewMode === 'desktop'
                ? 'bg-brand-600 text-white border-brand-600'
                : 'bg-surface text-muted border-border hover:text-foreground'
            "
            @click="setPreviewDesktop"
          >
            {{ t('forms.builder.previewDesktop') }}
          </button>
          <button
            class="px-3 py-1 text-sm rounded-r-lg border transition"
            :class="
              previewMode === 'mobile'
                ? 'bg-brand-600 text-white border-brand-600'
                : 'bg-surface text-muted border-border hover:text-foreground'
            "
            @click="setPreviewMobile"
          >
            {{ t('forms.builder.previewMobile') }}
          </button>
        </div>

        <BaseAlert type="info" class="text-center">
          {{ t('forms.builder.previewMode') }}
        </BaseAlert>

        <!-- Phone frame for mobile preview -->
        <div
          :class="
            previewMode === 'mobile'
              ? 'mx-auto border-2 border-gray-400 rounded-[2rem] p-3 bg-gray-50'
              : ''
          "
          :style="previewMode === 'mobile' ? 'max-width: 375px' : ''"
        >
          <div :class="previewMode === 'mobile' ? 'rounded-xl overflow-hidden bg-surface' : ''">
            <div class="space-y-4" :class="previewMode === 'mobile' ? 'p-3' : ''">
              <div v-if="bannerUrl" class="rounded-lg overflow-hidden">
                <img
                  :src="bannerUrl"
                  alt="Banner"
                  loading="lazy"
                  class="w-full h-32 object-cover"
                  width="768"
                  height="128"
                />
              </div>
              <div
                v-if="description"
                class="prose prose-sm max-w-none text-muted"
                v-html="DOMPurify.sanitize(description)"
              ></div>

              <div
                v-for="(q, i) in questions"
                :key="q.id"
                class="bg-surface-alt rounded-lg p-4 border border-border"
              >
                <p class="text-sm font-medium text-foreground mb-2">
                  {{ i + 1 }}. {{ q.label || t('forms.builder.untitledQuestion') }}
                  <span v-if="q.required" class="text-danger-500">*</span>
                </p>

                <!-- Text -->
                <input
                  v-if="q.type === 'text'"
                  type="text"
                  disabled
                  :placeholder="q.placeholder || t('forms.builder.shortTextPlaceholder')"
                  class="w-full border border-border rounded-lg px-3 py-2 text-sm bg-surface opacity-60"
                />

                <!-- Textarea -->
                <textarea
                  v-else-if="q.type === 'textarea'"
                  disabled
                  :placeholder="q.placeholder || t('forms.builder.longTextPlaceholder')"
                  :rows="3"
                  class="w-full border border-border rounded-lg px-3 py-2 text-sm bg-surface opacity-60"
                />

                <!-- Single choice -->
                <div v-else-if="q.type === 'single_choice'" class="space-y-2">
                  <label
                    v-for="opt in q.options"
                    :key="opt.id"
                    class="flex items-center gap-2 text-sm text-foreground"
                  >
                    <input type="radio" disabled class="text-brand-600" />
                    {{ opt.label || 'Option' }}
                  </label>
                </div>

                <!-- Multiple choice -->
                <div v-else-if="q.type === 'multiple_choice'" class="space-y-2">
                  <label
                    v-for="opt in q.options"
                    :key="opt.id"
                    class="flex items-center gap-2 text-sm text-foreground"
                  >
                    <input type="checkbox" disabled class="rounded" />
                    {{ opt.label || 'Option' }}
                  </label>
                </div>

                <!-- Dropdown -->
                <select
                  v-else-if="q.type === 'dropdown'"
                  disabled
                  class="w-full border border-border rounded-lg px-3 py-2 text-sm bg-surface opacity-60"
                >
                  <option value="">{{ t('forms.builder.selectPlaceholder') }}</option>
                  <option v-for="opt in q.options" :key="opt.id">{{ opt.label }}</option>
                </select>

                <!-- Rating -->
                <div v-else-if="q.type === 'rating'" class="flex gap-2">
                  <button
                    v-for="n in (q.max ?? 5) - (q.min ?? 1) + 1"
                    :key="n"
                    disabled
                    class="w-8 h-8 rounded bg-surface border border-border text-sm text-muted"
                  >
                    {{ (q.min ?? 1) + n - 1 }}
                  </button>
                </div>

                <!-- File upload -->
                <div v-else-if="q.type === 'file_upload'" class="text-sm text-muted opacity-60">
                  <input type="file" disabled />
                </div>
              </div>

              <EmptyState
                v-if="questions.length === 0"
                :message="t('forms.builder.noQuestionsAdded')"
              />
            </div>
          </div>
        </div>
      </div>
    </BaseModal>
  </div>
</template>

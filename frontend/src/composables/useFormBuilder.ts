import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import type { Router } from 'vue-router'
import type { Question, QuestionOption } from '@/types'
import { getErrorMessage } from '@/utils/error'
import { getForm, createForm, createStandaloneForm, updateForm } from '@/api/forms'
import { getSig } from '@/api/sigs'
import { uploadEditorFile } from '@/api/files'
import { useFormHistory } from '@/composables/useFormHistory'
import { useFormDraft } from '@/composables/useFormDraft'

export interface FormBuilderOptions {
  sigId: () => string | undefined
  formId: () => string
  router: Router
  t: (key: string, values?: Record<string, unknown>) => string
}

export function useFormBuilder({ sigId, formId, router, t }: FormBuilderOptions) {
  const isEdit = computed(() => !!formId())
  const isStandalone = computed(() => !sigId())

  // ── Reactive state ──
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

  // Collapse/Expand
  const collapsedQuestions = ref<Set<string>>(new Set())

  // Preview device toggle
  const previewMode = ref<'desktop' | 'mobile'>('desktop')

  // Drag-and-drop state
  const dragIndex = ref<number | null>(null)
  const dropTargetIndex = ref<number | null>(null)

  // Draft banner
  const showDraftBanner = ref(false)

  // ── Composables ──
  const history = useFormHistory()

  // Pass getter functions so the draft key is computed lazily in onMounted,
  // after route params are guaranteed to be resolved.
  const draft = useFormDraft(
    () => (isEdit.value ? undefined : sigId()),
    () => (isEdit.value ? formId() : undefined),
  )

  let autoSaveTimer: ReturnType<typeof setInterval> | null = null

  // ── Computed ──
  const hasInvalidRating = computed(() =>
    questions.value.some((q) => q.type === 'rating' && (q.min ?? 1) >= (q.max ?? 5)),
  )

  const minDeadline = computed(() => {
    const now = new Date()
    now.setMinutes(now.getMinutes() - now.getTimezoneOffset())
    return now.toISOString().slice(0, 16)
  })

  // ── Helpers ──
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

  function scrollToQuestion(index: number): void {
    nextTick(() => {
      const el = document.getElementById(`question-card-${index}`)
      if (el) {
        el.scrollIntoView({ behavior: 'smooth', block: 'center' })
      }
    })
  }

  // ── History helpers ──
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

  // ── Question CRUD ──
  function addQuestion(): void {
    questions.value.push(createQuestion())
    recordHistory()
    scrollToQuestion(questions.value.length - 1)
  }

  function insertQuestionAt(index: number): void {
    const newQ = createQuestion()
    questions.value.splice(index, 0, newQ)
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

  // ── Collapse/Expand ──
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

  // ── Drag and Drop ──
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

  // ── Draft ──
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
    if (autoSaveTimer !== null) return
    autoSaveTimer = setInterval(saveDraftNow, 30000)
  }

  function stopAutoSave(): void {
    if (autoSaveTimer !== null) {
      clearInterval(autoSaveTimer)
      autoSaveTimer = null
    }
  }

  // ── Preview ──
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
  function serializeQuestion(q: Question): Record<string, unknown> {
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

  async function fetchSigName(id: string): Promise<void> {
    breadcrumbSigId.value = id
    try {
      const sigData = await getSig(id)
      sigName.value = sigData.name
    } catch {
      /* breadcrumb will show fallback */
    }
  }

  async function fetchForm(): Promise<void> {
    if (!isEdit.value) return
    loading.value = true
    try {
      const data = await getForm(formId())
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
      breadcrumbSigId.value = data.sig_id || ''
      for (const q of questions.value) {
        collapsedQuestions.value.add(q.id)
      }
      history.pushState(questions.value)
      if (data.sig_id) {
        try {
          const sigData = await getSig(data.sig_id)
          sigName.value = sigData.name
        } catch {
          /* breadcrumb will show fallback */
        }
      }
    } catch {
      error.value = t('forms.builder.loadError')
    } finally {
      loading.value = false
    }
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
        await updateForm(formId(), payload)
        message.value = t('forms.builder.updateSuccess')
      } else if (isStandalone.value) {
        const serialized = questions.value.map(serializeQuestion)
        const data = await createStandaloneForm({ ...payload, questions: serialized })
        message.value = t('forms.builder.successMessage')
        router.replace(`/forms/${data.id}`)
      } else {
        const serialized = questions.value.map(serializeQuestion)
        const data = await createForm(sigId()!, { ...payload, questions: serialized })
        message.value = t('forms.builder.successMessage')
        router.replace(`/forms/${data.id}`)
      }
      draft.discardDraft()
    } catch (e: unknown) {
      error.value = getErrorMessage(e, t('forms.builder.saveError'))
    } finally {
      saving.value = false
    }
  }

  // ── Lifecycle ──
  onMounted(() => {
    showDraftBanner.value = false // Reset on mount
    draft.checkForDraft()

    if (isEdit.value) {
      fetchForm()
    } else {
      if (draft.hasDraft.value) {
        showDraftBanner.value = true
        addQuestion()
      } else {
        addQuestion()
      }
      if (sigId()) fetchSigName(sigId()!)
    }
    document.addEventListener('keydown', handleKeyboardShortcut)
    startAutoSave()
  })

  onUnmounted(() => {
    document.removeEventListener('keydown', handleKeyboardShortcut)
    stopAutoSave()
  })

  return {
    // State
    title,
    description,
    bannerUrl,
    deadline,
    maxRespondents,
    questions,
    isSchemaLocked,
    allowNonMembers,
    loading,
    saving,
    message,
    error,
    showPreview,
    sigName,
    breadcrumbSigId,
    collapsedQuestions,
    previewMode,
    dragIndex,
    dropTargetIndex,
    showDraftBanner,
    // Computed
    isEdit,
    isStandalone,
    hasInvalidRating,
    minDeadline,
    // Draft refs (for template access)
    draftTime: draft.draftTime,
    hasDraft: draft.hasDraft,
    // History refs (for template access)
    canUndo: history.canUndo,
    canRedo: history.canRedo,
    // Question methods
    addQuestion,
    insertQuestionAt,
    removeQuestion,
    moveQuestion,
    duplicateQuestion,
    addOption,
    removeOption,
    moveOption,
    updateAllowedTypes,
    // Collapse/Expand
    toggleCollapse,
    collapseAll,
    expandAll,
    isCollapsed,
    // Drag and drop
    handleDragStart,
    handleDragOver,
    handleDragLeave,
    handleDrop,
    handleDragEnd,
    handleTouchStart,
    handleTouchMove,
    handleTouchEnd,
    // Undo/Redo
    handleUndo,
    handleRedo,
    // Draft actions
    restoreDraft,
    discardDraft,
    saveDraftNow,
    // Preview
    setPreviewDesktop,
    setPreviewMobile,
    // Banner
    uploadBanner,
    // Form CRUD
    saveForm,
  }
}

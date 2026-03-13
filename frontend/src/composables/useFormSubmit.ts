import { ref, computed, onUnmounted, type Ref } from 'vue'
import type { Router } from 'vue-router'
import type { FormData, FormResponse, Question } from '@/types'
import { getForm, submitForm as apiSubmitForm, getMyResponse } from '@/api/forms'
import { getSig } from '@/api/sigs'
import { uploadEditorFile } from '@/api/files'
import { getErrorMessage } from '@/utils/error'
import { useFormResponseDraft } from '@/composables/useFormResponseDraft'
import { useAuthStore } from '@/stores/auth'

type AuthStore = ReturnType<typeof useAuthStore>

export interface UseFormSubmitOptions {
  formId: Ref<string>
  auth: AuthStore
  router: Router
  t: (key: string, values?: Record<string, unknown>) => string
}

export function useFormSubmit(options: UseFormSubmitOptions) {
  const { formId, auth, router, t } = options

  // ── Core State ──
  const form = ref<FormData | null>(null)
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const answers = ref<Record<string, any>>({})
  const loading = ref(true)
  const submitting = ref(false)
  const submitted = ref(false)
  const error = ref('')
  const message = ref('')
  const sigName = ref('')

  // ── View Submitted Response State ──
  const previousResponse = ref<FormResponse | null>(null)
  const submittedAnswers = ref<Record<string, unknown>>({})

  // ── Validation State ──
  const validationErrors = ref<Record<string, string>>({})
  const highlightedQuestions = ref<Set<string>>(new Set())
  const questionRefs = ref<Record<string, HTMLElement>>({})
  let highlightTimers: Record<string, ReturnType<typeof setTimeout>> = {}

  // ── File Upload State ──
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

  // ── Draft Composable ──
  const { draftRestored, loadDraft, clearDraft, startAutoSave, stopAutoSave } =
    useFormResponseDraft({
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

  const showForm = computed(() => {
    return (
      !submitted.value &&
      !previousResponse.value &&
      form.value?.is_active &&
      auth.isAuthenticated &&
      !auth.isGuest
    )
  })

  // ── Validation helpers ──
  function scrollToQuestion(questionId: string) {
    // Uses nextTick indirectly via the caller; called after DOM is ready
    const el = questionRefs.value[questionId]
    if (el && typeof el.scrollIntoView === 'function') {
      el.scrollIntoView({ behavior: 'smooth', block: 'center' })
    }
  }

  function addHighlight(questionId: string) {
    highlightedQuestions.value.add(questionId)
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

  // ── Load Form ──
  async function loadForm() {
    loading.value = true
    error.value = ''
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

      if (auth.isAuthenticated && !auth.isGuest) {
        try {
          const resp = await getMyResponse(formId.value)
          if (resp) {
            previousResponse.value = resp
          }
        } catch {
          // No previous response — show the form
        }
      }

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

  // ── Validation ──
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
      if (
        val === null ||
        val === undefined ||
        val === '' ||
        (Array.isArray(val) && val.length === 0)
      )
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

    if (firstErrorQuestionId) {
      scrollToQuestion(firstErrorQuestionId)
      for (const qId of Object.keys(validationErrors.value)) {
        addHighlight(qId)
      }
    }

    return firstError
  }

  // ── Submit ──
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

      // Upload any pending File objects before submitting
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
      submittedAnswers.value = { ...cleanAnswers }
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

  // ── File Upload ──
  function processFile(questionId: string, file: File) {
    const question = form.value?.questions.find((q) => q.id === questionId)
    if (!question) return

    if (question.allowed_types && question.allowed_types.length > 0) {
      const ext = file.name.split('.').pop()?.toLowerCase() ?? ''
      const allowed = question.allowed_types.map((type) => type.toLowerCase().trim())
      if (!allowed.includes(ext)) {
        validationErrors.value[questionId] = t('forms.view.fileTypeError', {
          types: question.allowed_types.join(', '),
        })
        addHighlight(questionId)
        return
      }
    }

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

    if (file.type.startsWith('image/')) {
      const url = URL.createObjectURL(file)
      filePreviews.value[questionId] = url
    } else {
      revokePreview(questionId)
    }
  }

  function handleFileUpload(questionId: string, event: Event): void {
    const input = event.target as HTMLInputElement
    const file = input.files?.[0]
    if (!file) return
    processFile(questionId, file)
    input.value = ''
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

  function revokePreview(questionId: string) {
    if (filePreviews.value[questionId]) {
      URL.revokeObjectURL(filePreviews.value[questionId])
      delete filePreviews.value[questionId]
    }
  }

  function removeFile(questionId: string) {
    answers.value[questionId] = ''
    revokePreview(questionId)
    clearQuestionError(questionId)
    const input = document.getElementById(`file-input-${questionId}`) as HTMLInputElement | null
    if (input) input.value = ''
  }

  // ── Multiple Choice ──
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

  // ── Rating ──
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

  // ── Answer change handlers ──
  function onTextInput(questionId: string) {
    clearQuestionError(questionId)
  }

  function onSelectChange(questionId: string) {
    clearQuestionError(questionId)
  }

  function onRadioChange(questionId: string) {
    clearQuestionError(questionId)
  }

  // ── Response display helpers ──
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

  // ── Draft clear + reset ──
  function handleClearDraft() {
    clearDraft()
    if (form.value) {
      for (const q of form.value.questions) {
        answers.value[q.id] = q.type === 'multiple_choice' ? [] : q.type === 'rating' ? null : ''
      }
    }
  }

  // ── Navigation ──
  function goBackToSig() {
    if (form.value) {
      router.push(`/sigs/${form.value.sig_id}`)
    }
  }

  // ── Utilities ──
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

  // ── Cleanup ──
  onUnmounted(() => {
    stopAutoSave()
    for (const timer of Object.values(highlightTimers)) {
      clearTimeout(timer)
    }
    highlightTimers = {}
    for (const url of Object.values(filePreviews.value)) {
      URL.revokeObjectURL(url)
    }
  })

  return {
    // state
    form,
    answers,
    loading,
    submitting,
    submitted,
    error,
    message,
    sigName,
    previousResponse,
    submittedAnswers,
    validationErrors,
    highlightedQuestions,
    dragOverQuestions,
    filePreviews,
    uploadingFiles,
    // draft
    draftRestored,
    // computed
    canEdit,
    canExport,
    totalQuestions,
    answeredCount,
    progressPercent,
    showForm,
    // methods
    loadForm,
    submitForm,
    handleFileUpload,
    handleDrop,
    handleDragOver,
    handleDragLeave,
    triggerFileInput,
    removeFile,
    toggleMultipleChoice,
    ratingRange,
    ratingCount,
    selectRating,
    onTextInput,
    onSelectChange,
    onRadioChange,
    getDisplayAnswer,
    getResponseAnswers,
    handleClearDraft,
    goBackToSig,
    setQuestionRef,
    isFileObject,
    getFileName,
    formatFileSize,
  }
}

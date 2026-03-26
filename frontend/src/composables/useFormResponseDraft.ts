import { ref, watch, onUnmounted, type Ref } from 'vue'

const DRAFT_PREFIX = 'form-response-draft-'
const DEBOUNCE_MS = 2000

export type FormAnswerValue = string | string[] | number | boolean | null
export type FormAnswers = Record<string, FormAnswerValue>

export interface FormDraftOptions {
  formId: Ref<string>
  answers: Ref<FormAnswers>
  /** Question types that should not be saved (e.g. file_upload) */
  skipTypes?: Ref<Record<string, string>>
}

export function useFormResponseDraft(options: FormDraftOptions) {
  const { formId, answers, skipTypes } = options
  const draftRestored = ref(false)
  let debounceTimer: ReturnType<typeof setTimeout> | null = null
  let stopWatcher: (() => void) | null = null

  function draftKey(): string {
    return `${DRAFT_PREFIX}${formId.value}`
  }

  function serializableAnswers(): FormAnswers {
    const result: FormAnswers = {}
    const typeMap = skipTypes?.value
    for (const [key, val] of Object.entries(answers.value)) {
      // Skip File objects (file_upload type)
      if (val instanceof File) continue
      // Only apply type-based filtering when skipTypes ref is provided and has a value
      if (typeMap != null && typeMap[key] === 'file_upload') continue
      result[key] = val
    }
    return result
  }

  function saveDraft(): void {
    try {
      const data = serializableAnswers()
      localStorage.setItem(draftKey(), JSON.stringify(data))
    } catch {
      // localStorage may be full or unavailable
    }
  }

  function loadDraft(): boolean {
    try {
      const raw = localStorage.getItem(draftKey())
      if (!raw) return false
      const data = JSON.parse(raw) as FormAnswers
      for (const [key, val] of Object.entries(data)) {
        if (key in answers.value) {
          answers.value[key] = val
        }
      }
      draftRestored.value = true
      return true
    } catch {
      return false
    }
  }

  function clearDraft(): void {
    try {
      localStorage.removeItem(draftKey())
    } catch {
      // ignore
    }
    draftRestored.value = false
  }

  function startAutoSave(): void {
    // Guard: don't create duplicate watchers
    if (stopWatcher) return
    stopWatcher = watch(
      answers,
      () => {
        if (debounceTimer) clearTimeout(debounceTimer)
        debounceTimer = setTimeout(() => {
          saveDraft()
        }, DEBOUNCE_MS)
      },
      { deep: true },
    )
  }

  function stopAutoSave(): void {
    if (debounceTimer) {
      clearTimeout(debounceTimer)
      debounceTimer = null
    }
    if (stopWatcher) {
      stopWatcher()
      stopWatcher = null
    }
  }

  onUnmounted(() => {
    stopAutoSave()
  })

  return {
    draftRestored,
    loadDraft,
    clearDraft,
    saveDraft,
    startAutoSave,
    stopAutoSave,
  }
}

import { ref, watch, type Ref } from 'vue'

const DRAFT_PREFIX = 'form-response-draft-'
const DEBOUNCE_MS = 2000

export interface FormDraftOptions {
  formId: Ref<string>
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  answers: Ref<Record<string, any>>
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

  function serializableAnswers(): Record<string, unknown> {
    const result: Record<string, unknown> = {}
    for (const [key, val] of Object.entries(answers.value)) {
      // Skip File objects (file_upload type)
      if (val instanceof File) continue
      // Skip if the question type is file_upload
      if (skipTypes?.value && skipTypes.value[key] === 'file_upload') continue
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
      const data = JSON.parse(raw) as Record<string, unknown>
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

  return {
    draftRestored,
    loadDraft,
    clearDraft,
    saveDraft,
    startAutoSave,
    stopAutoSave,
  }
}

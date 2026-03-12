import { ref, type Ref } from 'vue'
import type { Question } from '@/types'

export interface FormDraftData {
  title: string
  description: string
  bannerUrl: string
  deadline: string
  maxRespondents: number | null
  allowNonMembers: boolean
  questions: Question[]
  savedAt: string
}

export interface FormDraftState {
  hasDraft: Ref<boolean>
  draftTime: Ref<string>
  checkForDraft: () => void
  saveDraft: (data: Omit<FormDraftData, 'savedAt'>) => void
  loadDraft: () => FormDraftData | null
  discardDraft: () => void
}

function getDraftKey(sigId?: string, formId?: string): string {
  if (formId) return `form-draft-edit-${formId}`
  if (sigId) return `form-draft-${sigId}`
  return 'form-draft-unknown'
}

type StringOrGetter = string | (() => string | undefined) | undefined

function resolve(v: StringOrGetter): string | undefined {
  if (typeof v === 'function') return v()
  return v
}

/**
 * Manages per-form draft persistence in localStorage.
 *
 * Accepts either plain strings or getter functions for sigId/formId.
 * Using getter functions defers key computation to call time, which prevents
 * a race condition when the composable is instantiated before route params
 * are resolved. Call `checkForDraft()` in `onMounted` to read the correct key.
 */
export function useFormDraft(
  sigId?: StringOrGetter,
  formId?: StringOrGetter,
): FormDraftState {
  const hasDraft = ref(false)
  const draftTime = ref('')

  function getKey(): string {
    return getDraftKey(resolve(sigId), resolve(formId))
  }

  function checkForDraft(): void {
    try {
      const raw = localStorage.getItem(getKey())
      if (raw) {
        const data = JSON.parse(raw) as FormDraftData
        hasDraft.value = true
        draftTime.value = data.savedAt
      } else {
        hasDraft.value = false
        draftTime.value = ''
      }
    } catch {
      hasDraft.value = false
      draftTime.value = ''
    }
  }

  function saveDraft(data: Omit<FormDraftData, 'savedAt'>): void {
    try {
      const draftData: FormDraftData = {
        ...data,
        savedAt: new Date().toISOString(),
      }
      localStorage.setItem(getKey(), JSON.stringify(draftData))
      hasDraft.value = true
      draftTime.value = draftData.savedAt
    } catch {
      // localStorage might be full or unavailable
    }
  }

  function loadDraft(): FormDraftData | null {
    try {
      const raw = localStorage.getItem(getKey())
      if (!raw) return null
      return JSON.parse(raw) as FormDraftData
    } catch {
      return null
    }
  }

  function discardDraft(): void {
    try {
      localStorage.removeItem(getKey())
    } catch {
      // ignore
    }
    hasDraft.value = false
    draftTime.value = ''
  }

  // Check on creation (handles the string API case where key is known immediately)
  checkForDraft()

  return {
    hasDraft,
    draftTime,
    checkForDraft,
    saveDraft,
    loadDraft,
    discardDraft,
  }
}

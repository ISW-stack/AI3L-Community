import { ref, type Ref } from 'vue'
import type { Question } from '@/types'
import { useDraft } from './useDraft'

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
  return 'form-draft-standalone'
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
 *
 * Internally delegates to the generic `useDraft` composable while preserving
 * the existing storage format and external API for backward compatibility.
 */
export function useFormDraft(sigId?: StringOrGetter, formId?: StringOrGetter): FormDraftState {
  const keyFn = () => getDraftKey(resolve(sigId), resolve(formId))

  const defaultValue: FormDraftData = {
    title: '',
    description: '',
    bannerUrl: '',
    deadline: '',
    maxRespondents: null,
    allowNonMembers: false,
    questions: [],
    savedAt: '',
  }

  const {
    data,
    hasDraft,
    loadDraft: coreLoad,
    clearDraft: coreClear,
    checkForDraft: coreCheck,
  } = useDraft<FormDraftData>({
    key: keyFn,
    defaultValue,
    debounceMs: 0,
    autoSave: false,
  })

  // draftTime tracks the savedAt field from the stored data itself.
  // This preserves the original API where savedAt is part of FormDraftData.
  const draftTime = ref('')

  function checkForDraft(): void {
    const exists = coreCheck()
    if (exists) {
      // Validate that the stored data is valid JSON (backward compat).
      // The old implementation parsed the JSON during check and treated
      // parse failures as "no draft".
      try {
        const raw = localStorage.getItem(keyFn())
        if (raw) {
          const parsed = JSON.parse(raw) as FormDraftData
          hasDraft.value = true
          draftTime.value = parsed.savedAt || ''
        }
      } catch {
        hasDraft.value = false
        draftTime.value = ''
      }
    } else {
      draftTime.value = ''
    }
  }

  function saveDraft(formData: Omit<FormDraftData, 'savedAt'>): void {
    const now = new Date().toISOString()
    data.value = { ...formData, savedAt: now }
    // Write directly to localStorage to preserve the existing format
    // (FormDraftData with embedded savedAt, stored as plain JSON).
    try {
      localStorage.setItem(keyFn(), JSON.stringify(data.value))
      hasDraft.value = true
      draftTime.value = now
    } catch {
      // localStorage might be full or unavailable
    }
  }

  function loadDraft(): FormDraftData | null {
    const loaded = coreLoad()
    if (!loaded) return null
    // Sync draftTime from the loaded data
    draftTime.value = data.value.savedAt || ''
    return data.value
  }

  function discardDraft(): void {
    coreClear()
    draftTime.value = ''
  }

  // Check on creation (handles the string API case where key is known immediately)
  // Only auto-check if key resolves to something meaningful
  const initialKey = keyFn()
  if (initialKey && !initialKey.includes('undefined') && initialKey !== 'form-draft-standalone') {
    checkForDraft()
  }

  return {
    hasDraft,
    draftTime,
    checkForDraft,
    saveDraft,
    loadDraft,
    discardDraft,
  }
}

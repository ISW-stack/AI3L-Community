import { ref, watch, onUnmounted, type Ref, type WatchStopHandle } from 'vue'

export interface UseDraftOptions<T> {
  /** Storage key or getter function for dynamic keys */
  key: string | (() => string)
  /** Default/initial value (used when no draft exists) */
  defaultValue: T
  /** Debounce interval in ms (default: 1000). Set to 0 to disable auto-save. */
  debounceMs?: number
  /** Custom serializer (default: JSON.stringify) */
  serialize?: (data: T) => string
  /** Custom deserializer (default: JSON.parse) */
  deserialize?: (raw: string) => T
  /** Auto-start watching for changes (default: true) */
  autoSave?: boolean
}

export interface UseDraftReturn<T> {
  /** The reactive draft data */
  data: Ref<T>
  /** Whether unsaved changes exist */
  isDirty: Ref<boolean>
  /** Whether a draft exists in storage */
  hasDraft: Ref<boolean>
  /** Timestamp when draft was last saved */
  savedAt: Ref<string>
  /** Save current data to storage immediately */
  saveDraft: () => void
  /** Load draft from storage, returns true if found */
  loadDraft: () => boolean
  /** Clear draft from storage */
  clearDraft: () => void
  /** Check if draft exists (without loading) */
  checkForDraft: () => boolean
  /** Start auto-save (watch + debounce) */
  startAutoSave: () => void
  /** Stop auto-save */
  stopAutoSave: () => void
}

export function useDraft<T>(options: UseDraftOptions<T>): UseDraftReturn<T> {
  const {
    key,
    defaultValue,
    debounceMs = 1000,
    serialize = JSON.stringify,
    deserialize = JSON.parse as (raw: string) => T,
    autoSave = true,
  } = options

  const data = ref(structuredClone(defaultValue)) as Ref<T>
  const isDirty = ref(false)
  const hasDraft = ref(false)
  const savedAt = ref('')

  let debounceTimer: ReturnType<typeof setTimeout> | null = null
  let stopWatcher: WatchStopHandle | null = null

  function resolveKey(): string {
    return typeof key === 'function' ? key() : key
  }

  function metaKey(): string {
    return `${resolveKey()}__meta`
  }

  function saveDraft(): void {
    try {
      const raw = serialize(data.value)
      localStorage.setItem(resolveKey(), raw)
      const now = new Date().toISOString()
      localStorage.setItem(metaKey(), now)
      hasDraft.value = true
      savedAt.value = now
      isDirty.value = false
    } catch {
      // localStorage might be full or unavailable
    }
  }

  function loadDraft(): boolean {
    try {
      const raw = localStorage.getItem(resolveKey())
      if (!raw) return false
      // L-06: Validate deserialized value is a non-null object
      const parsed = deserialize(raw)
      if (parsed === null || typeof parsed !== 'object') return false
      data.value = parsed
      hasDraft.value = true
      isDirty.value = false
      // Load savedAt from meta key
      const meta = localStorage.getItem(metaKey())
      savedAt.value = meta || ''
      return true
    } catch {
      // Corrupt data — remove it and warn in dev mode
      if (import.meta.env.DEV) {
        console.warn(
          `[useDraft] Corrupt draft data found for key "${resolveKey()}" — removing it. A fresh draft state will be used.`,
        )
      }
      try {
        localStorage.removeItem(resolveKey())
        localStorage.removeItem(metaKey())
      } catch {
        // ignore
      }
      data.value = structuredClone(defaultValue)
      hasDraft.value = false
      return false
    }
  }

  function clearDraft(): void {
    try {
      localStorage.removeItem(resolveKey())
      localStorage.removeItem(metaKey())
    } catch {
      // ignore
    }
    hasDraft.value = false
    savedAt.value = ''
    isDirty.value = false
    data.value = structuredClone(defaultValue)
  }

  function checkForDraft(): boolean {
    try {
      const raw = localStorage.getItem(resolveKey())
      const exists = raw !== null
      hasDraft.value = exists
      if (exists) {
        const meta = localStorage.getItem(metaKey())
        savedAt.value = meta || ''
      } else {
        savedAt.value = ''
      }
      return exists
    } catch {
      hasDraft.value = false
      return false
    }
  }

  function startAutoSave(): void {
    // Guard: don't create duplicate watchers
    if (stopWatcher) return
    if (debounceMs <= 0) return

    stopWatcher = watch(
      data,
      () => {
        isDirty.value = true
        if (debounceTimer) clearTimeout(debounceTimer)
        debounceTimer = setTimeout(() => {
          saveDraft()
        }, debounceMs)
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

  // Auto-start if requested and debounce is positive
  if (autoSave && debounceMs > 0) {
    startAutoSave()
  }

  onUnmounted(() => {
    stopAutoSave()
  })

  return {
    data,
    isDirty,
    hasDraft,
    savedAt,
    saveDraft,
    loadDraft,
    clearDraft,
    checkForDraft,
    startAutoSave,
    stopAutoSave,
  }
}

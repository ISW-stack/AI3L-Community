import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { ref, nextTick } from 'vue'
import { useDraft } from '../useDraft'

describe('useDraft', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  function createSimpleDraft(
    keyVal = 'test-draft',
    opts?: Partial<Parameters<typeof useDraft>[0]>,
  ) {
    return useDraft<{ name: string; count: number }>({
      key: keyVal,
      defaultValue: { name: '', count: 0 },
      debounceMs: 1000,
      autoSave: false,
      ...opts,
    })
  }

  describe('initial state', () => {
    it('starts with default value and no draft', () => {
      const { data, hasDraft, isDirty, savedAt } = createSimpleDraft()
      expect(data.value).toEqual({ name: '', count: 0 })
      expect(hasDraft.value).toBe(false)
      expect(isDirty.value).toBe(false)
      expect(savedAt.value).toBe('')
    })

    it('deep clones defaultValue so mutations do not leak', () => {
      const defaultVal = { name: 'original', count: 1 }
      const { data } = useDraft({
        key: 'clone-test',
        defaultValue: defaultVal,
        autoSave: false,
      })
      data.value.name = 'changed'
      expect(defaultVal.name).toBe('original')
    })
  })

  describe('saveDraft', () => {
    it('writes data to localStorage', () => {
      const { data, saveDraft, hasDraft, savedAt } = createSimpleDraft()
      data.value = { name: 'Alice', count: 5 }
      saveDraft()

      expect(hasDraft.value).toBe(true)
      expect(savedAt.value).toBeTruthy()

      const stored = localStorage.getItem('test-draft')
      expect(stored).not.toBeNull()
      const parsed = JSON.parse(stored!)
      expect(parsed.name).toBe('Alice')
      expect(parsed.count).toBe(5)
    })

    it('stores savedAt in a companion __meta key', () => {
      const { data, saveDraft } = createSimpleDraft()
      data.value = { name: 'Bob', count: 1 }
      saveDraft()

      const meta = localStorage.getItem('test-draft__meta')
      expect(meta).toBeTruthy()
      // Should be a valid ISO date string
      expect(new Date(meta!).toISOString()).toBe(meta)
    })

    it('sets isDirty to false after saving', () => {
      const { data, saveDraft, isDirty } = createSimpleDraft()
      isDirty.value = true
      data.value = { name: 'test', count: 1 }
      saveDraft()
      expect(isDirty.value).toBe(false)
    })
  })

  describe('loadDraft', () => {
    it('restores data from localStorage and returns true', () => {
      localStorage.setItem('test-draft', JSON.stringify({ name: 'Loaded', count: 42 }))
      const { data, loadDraft, hasDraft } = createSimpleDraft()
      const result = loadDraft()
      expect(result).toBe(true)
      expect(data.value.name).toBe('Loaded')
      expect(data.value.count).toBe(42)
      expect(hasDraft.value).toBe(true)
    })

    it('returns false when no draft exists', () => {
      const { loadDraft, hasDraft } = createSimpleDraft()
      const result = loadDraft()
      expect(result).toBe(false)
      expect(hasDraft.value).toBe(false)
    })

    it('reads savedAt from companion meta key', () => {
      const timestamp = '2026-03-15T10:00:00.000Z'
      localStorage.setItem('test-draft', JSON.stringify({ name: 'X', count: 1 }))
      localStorage.setItem('test-draft__meta', timestamp)
      const { loadDraft, savedAt } = createSimpleDraft()
      loadDraft()
      expect(savedAt.value).toBe(timestamp)
    })

    it('sets savedAt to empty string when no meta key exists', () => {
      localStorage.setItem('test-draft', JSON.stringify({ name: 'X', count: 1 }))
      const { loadDraft, savedAt } = createSimpleDraft()
      loadDraft()
      expect(savedAt.value).toBe('')
    })
  })

  describe('clearDraft', () => {
    it('removes draft and meta key from localStorage', () => {
      localStorage.setItem('test-draft', JSON.stringify({ name: 'X', count: 1 }))
      localStorage.setItem('test-draft__meta', '2026-01-01T00:00:00.000Z')
      const { clearDraft, hasDraft, savedAt } = createSimpleDraft()

      clearDraft()

      expect(localStorage.getItem('test-draft')).toBeNull()
      expect(localStorage.getItem('test-draft__meta')).toBeNull()
      expect(hasDraft.value).toBe(false)
      expect(savedAt.value).toBe('')
    })

    it('resets data to defaultValue', () => {
      const { data, clearDraft, saveDraft } = createSimpleDraft()
      data.value = { name: 'Alice', count: 10 }
      saveDraft()
      clearDraft()
      expect(data.value).toEqual({ name: '', count: 0 })
    })

    it('sets isDirty to false', () => {
      const { isDirty, clearDraft } = createSimpleDraft()
      isDirty.value = true
      clearDraft()
      expect(isDirty.value).toBe(false)
    })
  })

  describe('checkForDraft', () => {
    it('returns true when draft exists', () => {
      localStorage.setItem('test-draft', JSON.stringify({ name: 'X', count: 1 }))
      const { checkForDraft, hasDraft } = createSimpleDraft()
      const result = checkForDraft()
      expect(result).toBe(true)
      expect(hasDraft.value).toBe(true)
    })

    it('returns false when no draft exists', () => {
      const { checkForDraft, hasDraft } = createSimpleDraft()
      const result = checkForDraft()
      expect(result).toBe(false)
      expect(hasDraft.value).toBe(false)
    })

    it('does not modify data ref', () => {
      localStorage.setItem('test-draft', JSON.stringify({ name: 'Stored', count: 99 }))
      const { data, checkForDraft } = createSimpleDraft()
      checkForDraft()
      // data should still be default
      expect(data.value).toEqual({ name: '', count: 0 })
    })

    it('reads savedAt from meta key when draft exists', () => {
      const ts = '2026-03-15T12:00:00.000Z'
      localStorage.setItem('test-draft', JSON.stringify({ name: 'X', count: 1 }))
      localStorage.setItem('test-draft__meta', ts)
      const { checkForDraft, savedAt } = createSimpleDraft()
      checkForDraft()
      expect(savedAt.value).toBe(ts)
    })
  })

  describe('auto-save with debounce', () => {
    it('saves data after debounce interval', async () => {
      const { data, startAutoSave } = createSimpleDraft('auto-test', { debounceMs: 500 })
      startAutoSave()

      data.value.name = 'typed'
      await nextTick()

      // Before debounce expires
      expect(localStorage.getItem('auto-test')).toBeNull()

      vi.advanceTimersByTime(500)

      const stored = localStorage.getItem('auto-test')
      expect(stored).not.toBeNull()
      expect(JSON.parse(stored!).name).toBe('typed')
    })

    it('debounces rapid changes', async () => {
      const { data, startAutoSave } = createSimpleDraft('debounce-test', { debounceMs: 1000 })
      startAutoSave()

      data.value.name = 'first'
      await nextTick()
      vi.advanceTimersByTime(500)

      data.value.name = 'second'
      await nextTick()
      vi.advanceTimersByTime(500)

      // First timer was cleared; only 500ms into second debounce
      expect(localStorage.getItem('debounce-test')).toBeNull()

      vi.advanceTimersByTime(500)

      const stored = JSON.parse(localStorage.getItem('debounce-test')!)
      expect(stored.name).toBe('second')
    })

    it('sets isDirty to true on change, false after save', async () => {
      const { data, isDirty, startAutoSave } = createSimpleDraft('dirty-test', {
        debounceMs: 1000,
      })
      startAutoSave()

      expect(isDirty.value).toBe(false)

      data.value.name = 'changed'
      await nextTick()
      expect(isDirty.value).toBe(true)

      vi.advanceTimersByTime(1000)
      expect(isDirty.value).toBe(false)
    })

    it('autoSave option starts watching automatically', async () => {
      const { data } = useDraft<{ val: string }>({
        key: 'auto-start-test',
        defaultValue: { val: '' },
        debounceMs: 500,
        autoSave: true,
      })

      data.value.val = 'auto'
      await nextTick()
      vi.advanceTimersByTime(500)

      expect(localStorage.getItem('auto-start-test')).not.toBeNull()
    })

    it('does not auto-start when autoSave is false', async () => {
      const { data } = createSimpleDraft('no-auto', { autoSave: false, debounceMs: 500 })

      data.value.name = 'should not save'
      await nextTick()
      vi.advanceTimersByTime(1000)

      expect(localStorage.getItem('no-auto')).toBeNull()
    })

    it('does not auto-start when debounceMs is 0', async () => {
      const { data } = useDraft<{ val: string }>({
        key: 'zero-debounce',
        defaultValue: { val: '' },
        debounceMs: 0,
        autoSave: true,
      })

      data.value.val = 'test'
      await nextTick()
      vi.advanceTimersByTime(5000)

      expect(localStorage.getItem('zero-debounce')).toBeNull()
    })
  })

  describe('stopAutoSave', () => {
    it('prevents further saves after being called', async () => {
      const { data, startAutoSave, stopAutoSave } = createSimpleDraft('stop-test', {
        debounceMs: 500,
      })
      startAutoSave()

      data.value.name = 'before-stop'
      await nextTick()
      stopAutoSave()

      vi.advanceTimersByTime(1000)
      expect(localStorage.getItem('stop-test')).toBeNull()
    })

    it('allows restart after stop', async () => {
      const { data, startAutoSave, stopAutoSave } = createSimpleDraft('restart-test', {
        debounceMs: 500,
      })
      startAutoSave()
      stopAutoSave()

      startAutoSave()
      data.value.name = 'restarted'
      await nextTick()
      vi.advanceTimersByTime(500)

      const stored = localStorage.getItem('restart-test')
      expect(stored).not.toBeNull()
      expect(JSON.parse(stored!).name).toBe('restarted')
    })
  })

  describe('dynamic key (function key)', () => {
    it('resolves key from function', () => {
      const currentKey = ref('key-a')
      const { data, saveDraft } = useDraft<{ val: string }>({
        key: () => currentKey.value,
        defaultValue: { val: '' },
        autoSave: false,
      })

      data.value.val = 'a-value'
      saveDraft()
      expect(localStorage.getItem('key-a')).not.toBeNull()

      currentKey.value = 'key-b'
      data.value.val = 'b-value'
      saveDraft()
      expect(localStorage.getItem('key-b')).not.toBeNull()

      // Both keys exist
      expect(JSON.parse(localStorage.getItem('key-a')!).val).toBe('a-value')
      expect(JSON.parse(localStorage.getItem('key-b')!).val).toBe('b-value')
    })

    it('loadDraft uses current key', () => {
      const currentKey = ref('load-key-1')
      localStorage.setItem('load-key-1', JSON.stringify({ val: 'one' }))
      localStorage.setItem('load-key-2', JSON.stringify({ val: 'two' }))

      const { data, loadDraft } = useDraft<{ val: string }>({
        key: () => currentKey.value,
        defaultValue: { val: '' },
        autoSave: false,
      })

      loadDraft()
      expect(data.value.val).toBe('one')

      currentKey.value = 'load-key-2'
      loadDraft()
      expect(data.value.val).toBe('two')
    })
  })

  describe('custom serializer/deserializer', () => {
    it('uses custom serialize and deserialize', () => {
      const { data, saveDraft, loadDraft } = useDraft<string[]>({
        key: 'custom-serial',
        defaultValue: [],
        autoSave: false,
        serialize: (arr) => arr.join(','),
        deserialize: (raw) => raw.split(',').filter(Boolean),
      })

      data.value = ['a', 'b', 'c']
      saveDraft()

      const stored = localStorage.getItem('custom-serial')
      expect(stored).toBe('a,b,c')

      // Clear data and reload
      data.value = []
      const loaded = loadDraft()
      expect(loaded).toBe(true)
      expect(data.value).toEqual(['a', 'b', 'c'])
    })
  })

  describe('corrupt localStorage data', () => {
    it('handles invalid JSON gracefully on loadDraft', () => {
      localStorage.setItem('corrupt-test', 'not-valid-json{{{')
      const { data, loadDraft } = createSimpleDraft('corrupt-test')
      const result = loadDraft()
      expect(result).toBe(false)
      expect(data.value).toEqual({ name: '', count: 0 })
      // Corrupt data should be removed
      expect(localStorage.getItem('corrupt-test')).toBeNull()
    })

    it('handles invalid JSON gracefully on checkForDraft', () => {
      localStorage.setItem('corrupt-check', 'bad json')
      const { checkForDraft, hasDraft } = createSimpleDraft('corrupt-check')
      // checkForDraft checks existence, not validity — raw string is not null
      const result = checkForDraft()
      expect(result).toBe(true)
      expect(hasDraft.value).toBe(true)
    })
  })

  describe('startAutoSave guard against duplicates', () => {
    it('calling startAutoSave twice does not create duplicate watchers', async () => {
      const { data, startAutoSave } = createSimpleDraft('dup-test', { debounceMs: 500 })
      startAutoSave()
      startAutoSave() // second call is a no-op

      data.value.name = 'once'
      await nextTick()
      vi.advanceTimersByTime(500)

      const stored = localStorage.getItem('dup-test')
      expect(stored).not.toBeNull()
      expect(JSON.parse(stored!).name).toBe('once')
    })
  })

  describe('multiple instances do not interfere', () => {
    it('separate keys are independent', () => {
      const draft1 = useDraft<{ val: string }>({
        key: 'instance-1',
        defaultValue: { val: '' },
        autoSave: false,
      })
      const draft2 = useDraft<{ val: string }>({
        key: 'instance-2',
        defaultValue: { val: '' },
        autoSave: false,
      })

      draft1.data.value.val = 'first'
      draft1.saveDraft()

      draft2.data.value.val = 'second'
      draft2.saveDraft()

      expect(JSON.parse(localStorage.getItem('instance-1')!).val).toBe('first')
      expect(JSON.parse(localStorage.getItem('instance-2')!).val).toBe('second')

      draft1.clearDraft()
      expect(localStorage.getItem('instance-1')).toBeNull()
      expect(localStorage.getItem('instance-2')).not.toBeNull()
    })
  })

  describe('save then load roundtrip', () => {
    it('preserves data through save and load cycle', () => {
      const { data, saveDraft } = createSimpleDraft('roundtrip')
      data.value = { name: 'Test User', count: 100 }
      saveDraft()

      // Create new instance and load
      const { data: data2, loadDraft } = createSimpleDraft('roundtrip')
      const loaded = loadDraft()
      expect(loaded).toBe(true)
      expect(data2.value).toEqual({ name: 'Test User', count: 100 })
    })
  })

  describe('clearDraft after saveDraft', () => {
    it('fully clears saved draft', () => {
      const { data, saveDraft, clearDraft, hasDraft } = createSimpleDraft('clear-after-save')
      data.value = { name: 'temp', count: 1 }
      saveDraft()
      expect(hasDraft.value).toBe(true)

      clearDraft()
      expect(hasDraft.value).toBe(false)
      expect(localStorage.getItem('clear-after-save')).toBeNull()
      expect(localStorage.getItem('clear-after-save__meta')).toBeNull()
    })
  })

  describe('backward compatibility with legacy format', () => {
    it('loadDraft reads plain JSON written by old code', () => {
      // Old PostCreateView stored drafts as plain JSON objects
      const legacyDraft = {
        title: 'Legacy Title',
        content: '<p>Legacy content</p>',
        categoryId: null,
        keywords: ['old'],
        allowComments: true,
      }
      localStorage.setItem('legacy-key', JSON.stringify(legacyDraft))

      const { data, loadDraft } = useDraft<typeof legacyDraft>({
        key: 'legacy-key',
        defaultValue: {
          title: '',
          content: '',
          categoryId: null,
          keywords: [],
          allowComments: true,
        },
        autoSave: false,
      })

      const loaded = loadDraft()
      expect(loaded).toBe(true)
      expect(data.value.title).toBe('Legacy Title')
      expect(data.value.content).toBe('<p>Legacy content</p>')
      expect(data.value.keywords).toEqual(['old'])
    })
  })
})

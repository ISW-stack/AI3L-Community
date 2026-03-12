import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { ref } from 'vue'
import { useFormResponseDraft } from '../useFormResponseDraft'

describe('useFormResponseDraft', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  function createDraft(formId = 'form-1', initialAnswers: Record<string, unknown> = {}) {
    const formIdRef = ref(formId)
    const answers = ref<Record<string, unknown>>(initialAnswers)
    const skipTypes = ref<Record<string, string>>({})
    return {
      ...useFormResponseDraft({ formId: formIdRef, answers, skipTypes }),
      answers,
      skipTypes,
    }
  }

  it('saves answers to localStorage', () => {
    const { saveDraft } = createDraft('form-1', { q1: 'hello', q2: 'world' })
    saveDraft()
    const stored = localStorage.getItem('form-response-draft-form-1')
    expect(stored).not.toBeNull()
    const parsed = JSON.parse(stored!)
    expect(parsed.q1).toBe('hello')
    expect(parsed.q2).toBe('world')
  })

  it('loads draft from localStorage and sets draftRestored to true', () => {
    localStorage.setItem(
      'form-response-draft-form-2',
      JSON.stringify({ q1: 'saved value', q2: 42 }),
    )
    const { loadDraft, draftRestored, answers } = createDraft('form-2', { q1: '', q2: '' })
    const loaded = loadDraft()
    expect(loaded).toBe(true)
    expect(draftRestored.value).toBe(true)
    expect(answers.value.q1).toBe('saved value')
    expect(answers.value.q2).toBe(42)
  })

  it('returns false when no draft exists', () => {
    const { loadDraft, draftRestored } = createDraft('form-3', { q1: '' })
    const loaded = loadDraft()
    expect(loaded).toBe(false)
    expect(draftRestored.value).toBe(false)
  })

  it('clears draft from localStorage', () => {
    localStorage.setItem('form-response-draft-form-4', JSON.stringify({ q1: 'test' }))
    const { clearDraft, draftRestored } = createDraft('form-4', { q1: '' })
    // Simulate that a draft was loaded
    draftRestored.value = true
    clearDraft()
    expect(localStorage.getItem('form-response-draft-form-4')).toBeNull()
    expect(draftRestored.value).toBe(false)
  })

  it('skips File objects during save', () => {
    const file = new File(['content'], 'test.pdf', { type: 'application/pdf' })
    const { saveDraft } = createDraft('form-5', { q1: 'text', q2: file })
    saveDraft()
    const stored = JSON.parse(localStorage.getItem('form-response-draft-form-5')!)
    expect(stored.q1).toBe('text')
    expect(stored.q2).toBeUndefined()
  })

  it('skips file_upload type questions during save', () => {
    const { saveDraft, skipTypes } = createDraft('form-6', {
      q1: 'text',
      q2: 'some-file-ref',
    })
    skipTypes.value = { q2: 'file_upload' }
    saveDraft()
    const stored = JSON.parse(localStorage.getItem('form-response-draft-form-6')!)
    expect(stored.q1).toBe('text')
    expect(stored.q2).toBeUndefined()
  })

  it('auto-saves with debounce after 2 seconds', async () => {
    const { startAutoSave, answers } = createDraft('form-7', { q1: '' })
    startAutoSave()

    answers.value.q1 = 'typing...'
    // Not saved yet (before debounce)
    expect(localStorage.getItem('form-response-draft-form-7')).toBeNull()

    // Advance timers by 2000ms (debounce delay)
    vi.advanceTimersByTime(2000)
    // Need to flush microtasks for Vue reactivity
    await vi.runAllTimersAsync()

    const stored = localStorage.getItem('form-response-draft-form-7')
    expect(stored).not.toBeNull()
    expect(JSON.parse(stored!).q1).toBe('typing...')
  })

  it('does not restore keys not present in answers', () => {
    localStorage.setItem(
      'form-response-draft-form-8',
      JSON.stringify({ q1: 'val', unknown_key: 'extra' }),
    )
    const { loadDraft, answers } = createDraft('form-8', { q1: '' })
    loadDraft()
    expect(answers.value.q1).toBe('val')
    expect('unknown_key' in answers.value).toBe(false)
  })

  it('handles invalid JSON in localStorage gracefully', () => {
    localStorage.setItem('form-response-draft-form-9', 'not-json!')
    const { loadDraft, draftRestored } = createDraft('form-9', { q1: '' })
    const loaded = loadDraft()
    expect(loaded).toBe(false)
    expect(draftRestored.value).toBe(false)
  })

  it('stopAutoSave clears the debounce timer', () => {
    const { startAutoSave, stopAutoSave, answers } = createDraft('form-10', { q1: '' })
    startAutoSave()
    answers.value.q1 = 'trigger'
    stopAutoSave()
    vi.advanceTimersByTime(3000)
    // Should NOT have saved because we stopped
    expect(localStorage.getItem('form-response-draft-form-10')).toBeNull()
  })

  it('calling startAutoSave() twice does not create duplicate watchers', async () => {
    const { startAutoSave, answers } = createDraft('form-11', { q1: '' })
    startAutoSave()
    startAutoSave() // second call is a no-op

    answers.value.q1 = 'once'
    await vi.runAllTimersAsync()

    const stored = localStorage.getItem('form-response-draft-form-11')
    expect(stored).not.toBeNull()
    // Verify only one save happened (not duplicate saves with stale data)
    expect(JSON.parse(stored!).q1).toBe('once')
  })

  it('after stopAutoSave, changing answers does NOT trigger a save', async () => {
    const { startAutoSave, stopAutoSave, answers } = createDraft('form-12', { q1: '' })
    startAutoSave()
    stopAutoSave()

    answers.value.q1 = 'should not save'
    await vi.runAllTimersAsync()

    expect(localStorage.getItem('form-response-draft-form-12')).toBeNull()
  })

  it('after stopAutoSave, calling startAutoSave again DOES trigger saves', async () => {
    const { startAutoSave, stopAutoSave, answers } = createDraft('form-13', { q1: '' })
    startAutoSave()
    stopAutoSave()

    // Re-start watching
    startAutoSave()
    answers.value.q1 = 'restarted'
    await vi.runAllTimersAsync()

    const stored = localStorage.getItem('form-response-draft-form-13')
    expect(stored).not.toBeNull()
    expect(JSON.parse(stored!).q1).toBe('restarted')
  })
})

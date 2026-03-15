import { describe, it, expect, beforeEach } from 'vitest'
import { useFormDraft } from '../useFormDraft'
import type { Question } from '@/types'

function makeQuestion(id: string, label: string): Question {
  return {
    id,
    type: 'text',
    label,
    required: true,
    placeholder: '',
    options: [],
    min: 1,
    max: 5,
  }
}

describe('useFormDraft', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  describe('key format', () => {
    it('uses form-draft-{sigId} for new forms', () => {
      const draft = useFormDraft('sig-123', undefined)
      draft.saveDraft({
        title: 'Test',
        description: '',
        bannerUrl: '',
        deadline: '',
        maxRespondents: null,
        allowNonMembers: false,
        questions: [],
      })
      expect(localStorage.getItem('form-draft-sig-123')).toBeTruthy()
    })

    it('uses form-draft-edit-{formId} for editing forms', () => {
      const draft = useFormDraft(undefined, 'form-456')
      draft.saveDraft({
        title: 'Test',
        description: '',
        bannerUrl: '',
        deadline: '',
        maxRespondents: null,
        allowNonMembers: false,
        questions: [],
      })
      expect(localStorage.getItem('form-draft-edit-form-456')).toBeTruthy()
    })
  })

  describe('hasDraft', () => {
    it('returns false when no draft exists', () => {
      const draft = useFormDraft('sig-1')
      expect(draft.hasDraft.value).toBe(false)
    })

    it('returns true when a draft exists', () => {
      const saved = {
        title: 'Saved title',
        description: 'desc',
        bannerUrl: '',
        deadline: '',
        maxRespondents: null,
        allowNonMembers: false,
        questions: [],
        savedAt: '2026-03-12T10:00:00Z',
      }
      localStorage.setItem('form-draft-sig-1', JSON.stringify(saved))
      const draft = useFormDraft('sig-1')
      expect(draft.hasDraft.value).toBe(true)
      expect(draft.draftTime.value).toBe('2026-03-12T10:00:00Z')
    })
  })

  describe('saveDraft and loadDraft', () => {
    it('saves and loads draft data correctly', () => {
      const draft = useFormDraft('sig-1')
      const questions = [makeQuestion('q1', 'What is your name?')]
      draft.saveDraft({
        title: 'Survey',
        description: 'A test survey',
        bannerUrl: 'http://example.com/banner.png',
        deadline: '2026-04-01T12:00',
        maxRespondents: 50,
        allowNonMembers: true,
        questions,
      })

      const loaded = draft.loadDraft()
      expect(loaded).not.toBeNull()
      expect(loaded!.title).toBe('Survey')
      expect(loaded!.description).toBe('A test survey')
      expect(loaded!.bannerUrl).toBe('http://example.com/banner.png')
      expect(loaded!.deadline).toBe('2026-04-01T12:00')
      expect(loaded!.maxRespondents).toBe(50)
      expect(loaded!.allowNonMembers).toBe(true)
      expect(loaded!.questions).toHaveLength(1)
      expect(loaded!.questions[0].label).toBe('What is your name?')
      expect(loaded!.savedAt).toBeTruthy()
    })

    it('overwrites previous draft', () => {
      const draft = useFormDraft('sig-1')
      draft.saveDraft({
        title: 'First',
        description: '',
        bannerUrl: '',
        deadline: '',
        maxRespondents: null,
        allowNonMembers: false,
        questions: [],
      })
      draft.saveDraft({
        title: 'Second',
        description: '',
        bannerUrl: '',
        deadline: '',
        maxRespondents: null,
        allowNonMembers: false,
        questions: [],
      })
      const loaded = draft.loadDraft()
      expect(loaded!.title).toBe('Second')
    })
  })

  describe('discardDraft', () => {
    it('removes the draft from localStorage', () => {
      const draft = useFormDraft('sig-1')
      draft.saveDraft({
        title: 'Test',
        description: '',
        bannerUrl: '',
        deadline: '',
        maxRespondents: null,
        allowNonMembers: false,
        questions: [],
      })
      expect(draft.hasDraft.value).toBe(true)

      draft.discardDraft()
      expect(draft.hasDraft.value).toBe(false)
      expect(localStorage.getItem('form-draft-sig-1')).toBeNull()
    })
  })

  describe('loadDraft returns null for missing draft', () => {
    it('returns null when nothing is stored', () => {
      const draft = useFormDraft('sig-nonexistent')
      expect(draft.loadDraft()).toBeNull()
    })
  })

  describe('handles corrupted localStorage data', () => {
    it('returns false for hasDraft with invalid JSON', () => {
      localStorage.setItem('form-draft-sig-1', 'not-json')
      const draft = useFormDraft('sig-1')
      // hasDraft should be false because parsing fails
      expect(draft.hasDraft.value).toBe(false)
    })
  })

  describe('auto-check guard for getter functions', () => {
    it('skips checkForDraft when getter returns undefined (unresolved route)', () => {
      // Simulate getter functions that return undefined (route params not yet resolved)
      const savedData = {
        title: 'Should not be found',
        description: '',
        bannerUrl: '',
        deadline: '',
        maxRespondents: null,
        allowNonMembers: false,
        questions: [],
        savedAt: '2026-03-12T10:00:00Z',
      }
      localStorage.setItem('form-draft-unknown', JSON.stringify(savedData))

      const draft = useFormDraft(
        () => undefined,
        () => undefined,
      )
      // Auto-check should have been skipped because key resolves to 'form-draft-unknown'
      expect(draft.hasDraft.value).toBe(false)
    })

    it('skips checkForDraft when getter produces key with undefined in it', () => {
      const draft = useFormDraft(
        () => undefined,
        () => undefined,
      )
      expect(draft.hasDraft.value).toBe(false)
    })

    it('runs checkForDraft when getter returns a valid string', () => {
      const savedData = {
        title: 'Draft',
        description: '',
        bannerUrl: '',
        deadline: '',
        maxRespondents: null,
        allowNonMembers: false,
        questions: [],
        savedAt: '2026-03-12T10:00:00Z',
      }
      localStorage.setItem('form-draft-sig-valid', JSON.stringify(savedData))

      const draft = useFormDraft(() => 'sig-valid', undefined)
      expect(draft.hasDraft.value).toBe(true)
    })
  })
})

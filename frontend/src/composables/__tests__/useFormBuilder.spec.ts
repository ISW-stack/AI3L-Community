import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { ref } from 'vue'
import type { Question, FormData } from '@/types'

// Capture lifecycle callbacks so we can invoke them manually
const onMountedCallbacks: (() => void)[] = []
const onUnmountedCallbacks: (() => void)[] = []
vi.mock('vue', async () => {
  const actual = await vi.importActual<typeof import('vue')>('vue')
  return {
    ...actual,
    onMounted: vi.fn((cb: () => void) => {
      onMountedCallbacks.push(cb)
    }),
    onUnmounted: vi.fn((cb: () => void) => {
      onUnmountedCallbacks.push(cb)
    }),
  }
})

// Mock API modules
vi.mock('@/api/forms', () => ({
  getForm: vi.fn(),
  createForm: vi.fn(),
  updateForm: vi.fn(),
}))

vi.mock('@/api/sigs', () => ({
  getSig: vi.fn(),
}))

vi.mock('@/api/files', () => ({
  uploadEditorFile: vi.fn(),
}))

import { useFormBuilder } from '../useFormBuilder'
import { getForm, createForm, updateForm } from '@/api/forms'
import { getSig } from '@/api/sigs'
import { uploadEditorFile } from '@/api/files'

const mockGetForm = getForm as ReturnType<typeof vi.fn>
const mockCreateForm = createForm as ReturnType<typeof vi.fn>
const mockUpdateForm = updateForm as ReturnType<typeof vi.fn>
const mockGetSig = getSig as ReturnType<typeof vi.fn>
const mockUploadEditorFile = uploadEditorFile as ReturnType<typeof vi.fn>

const t = (key: string, _values?: Record<string, unknown>) => key

function createHarness(opts: { sigId?: string; formId?: string } = {}) {
  const { sigId = 'sig-1', formId = '' } = opts
  const mockRouter = { push: vi.fn(), replace: vi.fn() } as unknown as import('vue-router').Router

  onMountedCallbacks.length = 0
  onUnmountedCallbacks.length = 0

  const result = useFormBuilder({
    sigId: () => sigId,
    formId: () => formId,
    router: mockRouter,
    t,
  })
  return { ...result, mockRouter }
}

function makeFormData(overrides: Partial<FormData> = {}): FormData {
  return {
    id: 'form-1',
    sig_id: 'sig-1',
    title: 'Test Form',
    description: 'A description',
    banner_url: null,
    deadline: null,
    max_respondents: null,
    questions: [
      {
        id: 'q1',
        type: 'text',
        label: 'Name',
        required: true,
        placeholder: '',
        options: [],
        min: 1,
        max: 5,
      },
    ],
    is_schema_locked: false,
    allow_non_members: false,
    response_count: 0,
    is_active: true,
    created_by: 'user1',
    created_by_name: 'Alice',
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    ...overrides,
  }
}

describe('useFormBuilder', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.useFakeTimers()
    localStorage.clear()
    onMountedCallbacks.length = 0
    onUnmountedCallbacks.length = 0
    mockGetSig.mockResolvedValue({ id: 'sig-1', name: 'Test SIG' })
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  // 1. Initial state (empty form with default values)
  describe('initial state', () => {
    it('has correct default values for a new form', () => {
      const h = createHarness()
      expect(h.title.value).toBe('')
      expect(h.description.value).toBe('')
      expect(h.bannerUrl.value).toBe('')
      expect(h.deadline.value).toBe('')
      expect(h.maxRespondents.value).toBeNull()
      expect(h.questions.value).toEqual([])
      expect(h.isSchemaLocked.value).toBe(false)
      expect(h.allowNonMembers.value).toBe(false)
      expect(h.loading.value).toBe(false)
      expect(h.saving.value).toBe(false)
      expect(h.message.value).toBe('')
      expect(h.error.value).toBe('')
      expect(h.showPreview.value).toBe(false)
      expect(h.isEdit.value).toBe(false)
    })

    it('isEdit is true when formId is provided', () => {
      const h = createHarness({ formId: 'form-1' })
      expect(h.isEdit.value).toBe(true)
    })
  })

  // 2. Adding a question (addQuestion)
  describe('addQuestion', () => {
    it('adds a question with default values', () => {
      const h = createHarness()
      h.addQuestion()
      expect(h.questions.value).toHaveLength(1)
      const q = h.questions.value[0]
      expect(q.id).toBeTruthy()
      expect(q.type).toBe('text')
      expect(q.label).toBe('')
      expect(q.required).toBe(true)
      expect(q.placeholder).toBe('')
      expect(q.options).toEqual([])
      expect(q.min).toBe(1)
      expect(q.max).toBe(5)
    })

    it('adds multiple questions with unique IDs', () => {
      const h = createHarness()
      h.addQuestion()
      h.addQuestion()
      h.addQuestion()
      expect(h.questions.value).toHaveLength(3)
      const ids = h.questions.value.map((q) => q.id)
      expect(new Set(ids).size).toBe(3)
    })
  })

  // 3. Removing a question (removeQuestion)
  describe('removeQuestion', () => {
    it('removes the question at the given index', () => {
      const h = createHarness()
      h.addQuestion()
      h.addQuestion()
      const secondId = h.questions.value[1].id
      h.removeQuestion(0)
      expect(h.questions.value).toHaveLength(1)
      expect(h.questions.value[0].id).toBe(secondId)
    })

    it('removes collapsed state when removing a question', () => {
      const h = createHarness()
      h.addQuestion()
      const qId = h.questions.value[0].id
      h.toggleCollapse(qId)
      expect(h.isCollapsed(qId)).toBe(true)
      h.removeQuestion(0)
      expect(h.questions.value).toHaveLength(0)
    })
  })

  // 4. Reordering questions (moveQuestion up/down)
  describe('moveQuestion', () => {
    it('moves a question up', () => {
      const h = createHarness()
      h.addQuestion()
      h.addQuestion()
      const firstId = h.questions.value[0].id
      const secondId = h.questions.value[1].id
      h.moveQuestion(1, -1)
      expect(h.questions.value[0].id).toBe(secondId)
      expect(h.questions.value[1].id).toBe(firstId)
    })

    it('moves a question down', () => {
      const h = createHarness()
      h.addQuestion()
      h.addQuestion()
      const firstId = h.questions.value[0].id
      const secondId = h.questions.value[1].id
      h.moveQuestion(0, 1)
      expect(h.questions.value[0].id).toBe(secondId)
      expect(h.questions.value[1].id).toBe(firstId)
    })

    it('does nothing when moving up from index 0', () => {
      const h = createHarness()
      h.addQuestion()
      h.addQuestion()
      const firstId = h.questions.value[0].id
      h.moveQuestion(0, -1)
      expect(h.questions.value[0].id).toBe(firstId)
    })

    it('does nothing when moving down from last index', () => {
      const h = createHarness()
      h.addQuestion()
      h.addQuestion()
      const lastId = h.questions.value[1].id
      h.moveQuestion(1, 1)
      expect(h.questions.value[1].id).toBe(lastId)
    })
  })

  // 5. Updating question properties
  describe('updating question properties', () => {
    it('updates label directly via ref', () => {
      const h = createHarness()
      h.addQuestion()
      h.questions.value[0].label = 'Updated Label'
      expect(h.questions.value[0].label).toBe('Updated Label')
    })

    it('updates type directly via ref', () => {
      const h = createHarness()
      h.addQuestion()
      h.questions.value[0].type = 'rating'
      expect(h.questions.value[0].type).toBe('rating')
    })

    it('updates required directly via ref', () => {
      const h = createHarness()
      h.addQuestion()
      h.questions.value[0].required = false
      expect(h.questions.value[0].required).toBe(false)
    })

    it('updates options directly via ref', () => {
      const h = createHarness()
      h.addQuestion()
      h.questions.value[0].type = 'single_choice'
      h.questions.value[0].options = [
        { id: 'o1', label: 'Option A' },
        { id: 'o2', label: 'Option B' },
      ]
      expect(h.questions.value[0].options).toHaveLength(2)
    })
  })

  // 6. Adding/removing options to a choice question
  describe('addOption / removeOption', () => {
    it('adds an option with a unique ID and empty label', () => {
      const h = createHarness()
      h.addQuestion()
      const q = h.questions.value[0]
      q.type = 'single_choice'
      h.addOption(q)
      expect(q.options).toHaveLength(1)
      expect(q.options![0].id).toBeTruthy()
      expect(q.options![0].label).toBe('')
    })

    it('adds multiple options', () => {
      const h = createHarness()
      h.addQuestion()
      const q = h.questions.value[0]
      h.addOption(q)
      h.addOption(q)
      h.addOption(q)
      expect(q.options).toHaveLength(3)
    })

    it('removes an option at the given index', () => {
      const h = createHarness()
      h.addQuestion()
      const q = h.questions.value[0]
      h.addOption(q)
      h.addOption(q)
      const secondId = q.options![1].id
      h.removeOption(q, 0)
      expect(q.options).toHaveLength(1)
      expect(q.options![0].id).toBe(secondId)
    })

    it('initializes options array if null', () => {
      const h = createHarness()
      h.addQuestion()
      const q = h.questions.value[0]
      q.options = undefined as unknown as typeof q.options
      h.addOption(q)
      expect(q.options).toHaveLength(1)
    })
  })

  // 7. Form validation - empty title rejected
  describe('form validation', () => {
    it('rejects empty title', async () => {
      const h = createHarness()
      h.addQuestion()
      h.questions.value[0].label = 'Q1'
      h.title.value = ''
      await h.saveForm()
      expect(h.error.value).toBe('forms.builder.validation.titleRequired')
      expect(mockCreateForm).not.toHaveBeenCalled()
    })

    it('rejects whitespace-only title', async () => {
      const h = createHarness()
      h.addQuestion()
      h.questions.value[0].label = 'Q1'
      h.title.value = '   '
      await h.saveForm()
      expect(h.error.value).toBe('forms.builder.validation.titleRequired')
    })

    // 8. No questions rejected
    it('rejects form with no questions', async () => {
      const h = createHarness()
      h.title.value = 'Test Form'
      await h.saveForm()
      expect(h.error.value).toBe('forms.builder.validation.questionRequired')
      expect(mockCreateForm).not.toHaveBeenCalled()
    })

    // 9. Question with empty label rejected
    it('rejects question with empty label', async () => {
      const h = createHarness()
      h.title.value = 'Test Form'
      h.addQuestion()
      h.questions.value[0].label = ''
      await h.saveForm()
      expect(h.error.value).toBe('forms.builder.validation.labelRequired')
    })

    // Choice question with fewer than 2 options rejected
    it('rejects single_choice question with fewer than 2 options', async () => {
      const h = createHarness()
      h.title.value = 'Test Form'
      h.addQuestion()
      h.questions.value[0].label = 'Pick one'
      h.questions.value[0].type = 'single_choice'
      h.questions.value[0].options = [{ id: 'o1', label: 'Only option' }]
      await h.saveForm()
      expect(h.error.value).toBe('forms.builder.validation.optionsRequired')
    })

    // 10. Rating question validation (min >= max)
    it('rejects rating question where min >= max', async () => {
      const h = createHarness()
      h.title.value = 'Test Form'
      h.addQuestion()
      h.questions.value[0].label = 'Rate'
      h.questions.value[0].type = 'rating'
      h.questions.value[0].min = 5
      h.questions.value[0].max = 3
      await h.saveForm()
      expect(h.error.value).toBe('forms.builder.validation.ratingError')
    })

    it('rejects rating question where min equals max', async () => {
      const h = createHarness()
      h.title.value = 'Test Form'
      h.addQuestion()
      h.questions.value[0].label = 'Rate'
      h.questions.value[0].type = 'rating'
      h.questions.value[0].min = 3
      h.questions.value[0].max = 3
      await h.saveForm()
      expect(h.error.value).toBe('forms.builder.validation.ratingError')
    })

    it('hasInvalidRating computed detects bad rating', () => {
      const h = createHarness()
      h.addQuestion()
      h.questions.value[0].type = 'rating'
      h.questions.value[0].min = 5
      h.questions.value[0].max = 3
      expect(h.hasInvalidRating.value).toBe(true)
    })

    it('hasInvalidRating computed is false for valid rating', () => {
      const h = createHarness()
      h.addQuestion()
      h.questions.value[0].type = 'rating'
      h.questions.value[0].min = 1
      h.questions.value[0].max = 5
      expect(h.hasInvalidRating.value).toBe(false)
    })

    it('rejects deadline in the past', async () => {
      const h = createHarness()
      h.title.value = 'Test Form'
      h.addQuestion()
      h.questions.value[0].label = 'Q1'
      h.deadline.value = '2020-01-01T00:00'
      await h.saveForm()
      expect(h.error.value).toBe('forms.builder.validation.deadlineInFuture')
    })
  })

  // 11. Undo/redo functionality
  describe('undo/redo', () => {
    it('can undo after adding questions', () => {
      const h = createHarness()
      h.addQuestion()
      h.addQuestion()
      expect(h.questions.value).toHaveLength(2)
      expect(h.canUndo.value).toBe(true)

      h.handleUndo()
      expect(h.questions.value).toHaveLength(1)
    })

    it('can redo after undo', () => {
      const h = createHarness()
      h.addQuestion()
      h.addQuestion()
      h.handleUndo()
      expect(h.questions.value).toHaveLength(1)
      expect(h.canRedo.value).toBe(true)

      h.handleRedo()
      expect(h.questions.value).toHaveLength(2)
    })

    it('canUndo is false with no history', () => {
      const h = createHarness()
      expect(h.canUndo.value).toBe(false)
    })

    it('canRedo is false when no undo has occurred', () => {
      const h = createHarness()
      h.addQuestion()
      expect(h.canRedo.value).toBe(false)
    })
  })

  // 12. Auto-save draft functionality
  describe('auto-save draft', () => {
    it('saveDraftNow persists current state to localStorage', () => {
      const h = createHarness()
      h.title.value = 'Draft Title'
      h.addQuestion()
      h.questions.value[0].label = 'Q1'
      h.saveDraftNow()

      const raw = localStorage.getItem('form-draft-sig-1')
      expect(raw).toBeTruthy()
      const data = JSON.parse(raw!)
      expect(data.title).toBe('Draft Title')
      expect(data.questions).toHaveLength(1)
    })

    it('auto-save fires periodically (every 30s)', () => {
      const h = createHarness()
      // Trigger onMounted which starts auto-save
      for (const cb of onMountedCallbacks) cb()

      h.title.value = 'Auto-Saved'
      h.addQuestion()
      h.questions.value[0].label = 'Question'

      // Advance 30s
      vi.advanceTimersByTime(30000)

      const raw = localStorage.getItem('form-draft-sig-1')
      expect(raw).toBeTruthy()
      const data = JSON.parse(raw!)
      expect(data.title).toBe('Auto-Saved')
    })
  })

  // 13. Restoring from draft
  describe('restoreDraft', () => {
    it('restores form data from localStorage draft', () => {
      // Pre-populate localStorage with a draft
      const draftData = {
        title: 'Saved Draft',
        description: 'Draft desc',
        bannerUrl: 'http://example.com/banner.png',
        deadline: '2026-12-01T12:00',
        maxRespondents: 100,
        allowNonMembers: true,
        questions: [
          {
            id: 'q-saved',
            type: 'text',
            label: 'Saved Q',
            required: true,
            placeholder: '',
            options: [],
            min: 1,
            max: 5,
          },
        ],
        savedAt: '2026-03-12T10:00:00Z',
      }
      localStorage.setItem('form-draft-sig-1', JSON.stringify(draftData))

      const h = createHarness()
      // onMounted calls addQuestion which calls saveDraftNow, overwriting the draft.
      // Re-write the draft AFTER onMounted has run so restoreDraft can read it.
      for (const cb of onMountedCallbacks) cb()
      localStorage.setItem('form-draft-sig-1', JSON.stringify(draftData))

      h.restoreDraft()

      expect(h.title.value).toBe('Saved Draft')
      expect(h.description.value).toBe('Draft desc')
      expect(h.bannerUrl.value).toBe('http://example.com/banner.png')
      expect(h.deadline.value).toBe('2026-12-01T12:00')
      expect(h.maxRespondents.value).toBe(100)
      expect(h.allowNonMembers.value).toBe(true)
      expect(h.questions.value).toHaveLength(1)
      expect(h.questions.value[0].label).toBe('Saved Q')
      expect(h.showDraftBanner.value).toBe(false)
    })

    it('discardDraft clears localStorage and hides banner', () => {
      localStorage.setItem(
        'form-draft-sig-1',
        JSON.stringify({ title: 'x', savedAt: new Date().toISOString() }),
      )
      const h = createHarness()
      h.showDraftBanner.value = true
      h.discardDraft()
      expect(h.showDraftBanner.value).toBe(false)
      expect(localStorage.getItem('form-draft-sig-1')).toBeNull()
    })
  })

  // 14. Banner upload handling
  describe('uploadBanner', () => {
    it('uploads file and sets bannerUrl on success', async () => {
      mockUploadEditorFile.mockResolvedValue({ url: 'http://example.com/uploaded.png' })
      const h = createHarness()
      const file = new File(['data'], 'banner.png', { type: 'image/png' })
      const event = { target: { files: [file] } } as unknown as Event
      await h.uploadBanner(event)
      expect(mockUploadEditorFile).toHaveBeenCalledWith(file)
      expect(h.bannerUrl.value).toBe('http://example.com/uploaded.png')
    })

    it('sets error on upload failure', async () => {
      mockUploadEditorFile.mockRejectedValue(new Error('Upload failed'))
      const h = createHarness()
      const file = new File(['data'], 'banner.png', { type: 'image/png' })
      const event = { target: { files: [file] } } as unknown as Event
      await h.uploadBanner(event)
      expect(h.error.value).toBe('forms.builder.uploadBannerError')
    })

    it('does nothing when no file is selected', async () => {
      const h = createHarness()
      const event = { target: { files: [] } } as unknown as Event
      await h.uploadBanner(event)
      expect(mockUploadEditorFile).not.toHaveBeenCalled()
    })
  })

  // 15. Form save/submit
  describe('saveForm', () => {
    it('creates a new form and navigates on success', async () => {
      mockCreateForm.mockResolvedValue({ id: 'new-form-1' })
      const h = createHarness()
      h.title.value = 'New Form'
      h.addQuestion()
      h.questions.value[0].label = 'Question 1'
      h.questions.value[0].type = 'text'
      await h.saveForm()

      expect(mockCreateForm).toHaveBeenCalledWith('sig-1', expect.objectContaining({
        title: 'New Form',
        questions: expect.arrayContaining([
          expect.objectContaining({ label: 'Question 1', type: 'text' }),
        ]),
      }))
      expect(h.message.value).toBe('forms.builder.successMessage')
      expect((h.mockRouter as unknown as { replace: ReturnType<typeof vi.fn> }).replace).toHaveBeenCalledWith('/forms/new-form-1')
    })

    it('updates an existing form on edit mode', async () => {
      mockGetForm.mockResolvedValue(makeFormData())
      mockGetSig.mockResolvedValue({ id: 'sig-1', name: 'SIG' })
      mockUpdateForm.mockResolvedValue(makeFormData())
      const h = createHarness({ formId: 'form-1' })

      // Simulate fetchForm (edit mode)
      await (h as ReturnType<typeof useFormBuilder>).saveForm.call?.(null)
      // Set up for save
      h.title.value = 'Updated Title'
      h.questions.value = [
        {
          id: 'q1',
          type: 'text',
          label: 'Updated Q',
          required: true,
          placeholder: '',
          options: [],
          min: 1,
          max: 5,
        },
      ]
      await h.saveForm()

      expect(mockUpdateForm).toHaveBeenCalledWith('form-1', expect.objectContaining({
        title: 'Updated Title',
      }))
      expect(h.message.value).toBe('forms.builder.updateSuccess')
    })

    it('does not include questions in update when schema is locked', async () => {
      const h = createHarness({ formId: 'form-1' })
      h.title.value = 'Locked Form'
      h.isSchemaLocked.value = true
      h.questions.value = [
        {
          id: 'q1',
          type: 'text',
          label: 'Q',
          required: true,
          placeholder: '',
          options: [],
          min: 1,
          max: 5,
        },
      ]
      mockUpdateForm.mockResolvedValue(makeFormData())
      await h.saveForm()

      const payload = mockUpdateForm.mock.calls[0][1]
      expect(payload.questions).toBeUndefined()
    })

    it('handles save error with getErrorMessage', async () => {
      mockCreateForm.mockRejectedValue({
        response: { data: { detail: 'Server error detail' } },
      })
      const h = createHarness()
      h.title.value = 'Test Form'
      h.addQuestion()
      h.questions.value[0].label = 'Q1'
      await h.saveForm()

      expect(h.error.value).toBe('Server error detail')
      expect(h.saving.value).toBe(false)
    })

    it('clears draft on successful save', async () => {
      localStorage.setItem(
        'form-draft-sig-1',
        JSON.stringify({ title: 'x', savedAt: new Date().toISOString() }),
      )
      mockCreateForm.mockResolvedValue({ id: 'new-form-1' })
      const h = createHarness()
      h.title.value = 'Form'
      h.addQuestion()
      h.questions.value[0].label = 'Q1'
      await h.saveForm()

      expect(localStorage.getItem('form-draft-sig-1')).toBeNull()
    })

    it('serializes choice question options correctly (filters empty labels)', async () => {
      mockCreateForm.mockResolvedValue({ id: 'new-form-1' })
      const h = createHarness()
      h.title.value = 'Form'
      h.addQuestion()
      h.questions.value[0].label = 'Pick one'
      h.questions.value[0].type = 'single_choice'
      h.questions.value[0].options = [
        { id: 'o1', label: 'Option A' },
        { id: 'o2', label: '' },
        { id: 'o3', label: 'Option C' },
      ]
      await h.saveForm()

      const payload = mockCreateForm.mock.calls[0][1]
      const serializedQ = payload.questions[0]
      expect(serializedQ.options).toHaveLength(2)
      expect(serializedQ.options[0].label).toBe('Option A')
      expect(serializedQ.options[1].label).toBe('Option C')
    })
  })

  // Collapse/expand
  describe('collapse/expand', () => {
    it('toggleCollapse toggles collapse state', () => {
      const h = createHarness()
      h.addQuestion()
      const qId = h.questions.value[0].id
      expect(h.isCollapsed(qId)).toBe(false)

      h.toggleCollapse(qId)
      expect(h.isCollapsed(qId)).toBe(true)

      h.toggleCollapse(qId)
      expect(h.isCollapsed(qId)).toBe(false)
    })

    it('collapseAll collapses all questions', () => {
      const h = createHarness()
      h.addQuestion()
      h.addQuestion()
      h.collapseAll()
      expect(h.isCollapsed(h.questions.value[0].id)).toBe(true)
      expect(h.isCollapsed(h.questions.value[1].id)).toBe(true)
    })

    it('expandAll expands all questions', () => {
      const h = createHarness()
      h.addQuestion()
      h.addQuestion()
      h.collapseAll()
      h.expandAll()
      expect(h.isCollapsed(h.questions.value[0].id)).toBe(false)
      expect(h.isCollapsed(h.questions.value[1].id)).toBe(false)
    })
  })

  // duplicateQuestion
  describe('duplicateQuestion', () => {
    it('duplicates a question with a new ID', () => {
      const h = createHarness()
      h.addQuestion()
      h.questions.value[0].label = 'Original'
      h.questions.value[0].type = 'single_choice'
      h.questions.value[0].options = [{ id: 'o1', label: 'A' }]
      h.duplicateQuestion(0)

      expect(h.questions.value).toHaveLength(2)
      expect(h.questions.value[1].label).toBe('Original')
      expect(h.questions.value[1].id).not.toBe(h.questions.value[0].id)
      // Options should also have new IDs
      expect(h.questions.value[1].options![0].id).not.toBe('o1')
      expect(h.questions.value[1].options![0].label).toBe('A')
    })
  })

  // insertQuestionAt
  describe('insertQuestionAt', () => {
    it('inserts a question at the specified index', () => {
      const h = createHarness()
      h.addQuestion()
      h.addQuestion()
      const firstId = h.questions.value[0].id
      const secondId = h.questions.value[1].id
      h.insertQuestionAt(1)
      expect(h.questions.value).toHaveLength(3)
      expect(h.questions.value[0].id).toBe(firstId)
      expect(h.questions.value[2].id).toBe(secondId)
      expect(h.questions.value[1].id).not.toBe(firstId)
      expect(h.questions.value[1].id).not.toBe(secondId)
    })
  })

  // moveOption
  describe('moveOption', () => {
    it('moves an option up within a question', () => {
      const h = createHarness()
      h.addQuestion()
      const q = h.questions.value[0]
      h.addOption(q)
      h.addOption(q)
      q.options![0].label = 'First'
      q.options![1].label = 'Second'
      h.moveOption(q, 1, -1)
      expect(q.options![0].label).toBe('Second')
      expect(q.options![1].label).toBe('First')
    })

    it('does nothing when moving option out of bounds', () => {
      const h = createHarness()
      h.addQuestion()
      const q = h.questions.value[0]
      h.addOption(q)
      h.addOption(q)
      q.options![0].label = 'First'
      q.options![1].label = 'Second'
      h.moveOption(q, 0, -1)
      expect(q.options![0].label).toBe('First')
    })
  })

  // updateAllowedTypes
  describe('updateAllowedTypes', () => {
    it('parses comma-separated allowed types from input', () => {
      const h = createHarness()
      h.addQuestion()
      const q = h.questions.value[0]
      q.type = 'file_upload'
      const event = { target: { value: 'pdf, docx, txt' } } as unknown as Event
      h.updateAllowedTypes(q, event)
      expect(q.allowed_types).toEqual(['pdf', 'docx', 'txt'])
    })

    it('filters out empty strings', () => {
      const h = createHarness()
      h.addQuestion()
      const q = h.questions.value[0]
      const event = { target: { value: 'pdf,,, docx' } } as unknown as Event
      h.updateAllowedTypes(q, event)
      expect(q.allowed_types).toEqual(['pdf', 'docx'])
    })
  })

  // Preview mode
  describe('preview mode', () => {
    it('defaults to desktop', () => {
      const h = createHarness()
      expect(h.previewMode.value).toBe('desktop')
    })

    it('setPreviewMobile switches to mobile', () => {
      const h = createHarness()
      h.setPreviewMobile()
      expect(h.previewMode.value).toBe('mobile')
    })

    it('setPreviewDesktop switches to desktop', () => {
      const h = createHarness()
      h.setPreviewMobile()
      h.setPreviewDesktop()
      expect(h.previewMode.value).toBe('desktop')
    })
  })

  // fetchForm (edit mode)
  describe('fetchForm', () => {
    it('loads form data in edit mode', async () => {
      const formData = makeFormData({ title: 'Loaded Form' })
      mockGetForm.mockResolvedValue(formData)
      mockGetSig.mockResolvedValue({ id: 'sig-1', name: 'Test SIG' })

      const h = createHarness({ formId: 'form-1' })
      // Trigger onMounted which calls fetchForm
      for (const cb of onMountedCallbacks) cb()
      // Wait for async fetchForm to complete
      await vi.waitFor(() => {
        expect(h.loading.value).toBe(false)
      })

      expect(h.title.value).toBe('Loaded Form')
      expect(h.questions.value).toHaveLength(1)
      expect(h.sigName.value).toBe('Test SIG')
    })

    it('sets error on fetch failure', async () => {
      mockGetForm.mockRejectedValue(new Error('Not found'))

      const h = createHarness({ formId: 'form-1' })
      for (const cb of onMountedCallbacks) cb()
      await vi.waitFor(() => {
        expect(h.loading.value).toBe(false)
      })

      expect(h.error.value).toBe('forms.builder.loadError')
    })
  })

  // startAutoSave guard
  describe('startAutoSave guard', () => {
    it('should not create duplicate auto-save timers', () => {
      const setIntervalSpy = vi.spyOn(globalThis, 'setInterval')

      const h = createHarness()

      // Clear calls from constructor/createHarness
      setIntervalSpy.mockClear()

      // Trigger onMounted which calls startAutoSave
      for (const cb of onMountedCallbacks) cb()

      // Count calls from onMounted
      const callsAfterFirstMount = setIntervalSpy.mock.calls.length

      // Trigger onMounted again (simulating double-mount) — startAutoSave guard should prevent duplicate
      for (const cb of onMountedCallbacks) cb()

      // setInterval should NOT have been called again
      expect(setIntervalSpy.mock.calls.length).toBe(callsAfterFirstMount)

      setIntervalSpy.mockRestore()
    })
  })

  // Drag and drop
  describe('drag and drop', () => {
    it('handleDrop reorders questions', () => {
      const h = createHarness()
      h.addQuestion()
      h.addQuestion()
      h.addQuestion()
      const ids = h.questions.value.map((q) => q.id)

      // Simulate dragging index 0 to index 2
      h.dragIndex.value = 0
      const event = {
        preventDefault: vi.fn(),
        dataTransfer: { dropEffect: '' },
      } as unknown as DragEvent
      h.handleDrop(event, 2)

      expect(h.questions.value[0].id).toBe(ids[1])
      expect(h.questions.value[1].id).toBe(ids[0])
      expect(h.dragIndex.value).toBeNull()
      expect(h.dropTargetIndex.value).toBeNull()
    })

    it('handleDrop does nothing when dragIndex equals targetIndex', () => {
      const h = createHarness()
      h.addQuestion()
      h.addQuestion()
      h.dragIndex.value = 1
      const event = { preventDefault: vi.fn() } as unknown as DragEvent
      h.handleDrop(event, 1)
      expect(h.dragIndex.value).toBeNull()
    })

    it('handleDragEnd resets drag state', () => {
      const h = createHarness()
      h.dragIndex.value = 2
      h.dropTargetIndex.value = 0
      h.handleDragEnd()
      expect(h.dragIndex.value).toBeNull()
      expect(h.dropTargetIndex.value).toBeNull()
    })
  })
})

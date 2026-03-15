import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { ref } from 'vue'
import type { FormData, FormResponse, Question } from '@/types'

// Capture lifecycle callbacks
const onUnmountedCallbacks: (() => void)[] = []
vi.mock('vue', async () => {
  const actual = await vi.importActual<typeof import('vue')>('vue')
  return {
    ...actual,
    onUnmounted: vi.fn((cb: () => void) => {
      onUnmountedCallbacks.push(cb)
    }),
  }
})

// Mock API modules
vi.mock('@/api/forms', () => ({
  getForm: vi.fn(),
  submitForm: vi.fn(),
  getMyResponse: vi.fn(),
}))

vi.mock('@/api/sigs', () => ({
  getSig: vi.fn(),
}))

vi.mock('@/api/files', () => ({
  uploadEditorFile: vi.fn(),
}))

// Mock the response draft composable
vi.mock('@/composables/useFormResponseDraft', () => ({
  useFormResponseDraft: vi.fn(() => ({
    draftRestored: ref(false),
    loadDraft: vi.fn(() => false),
    clearDraft: vi.fn(),
    startAutoSave: vi.fn(),
    stopAutoSave: vi.fn(),
  })),
}))

// Mock auth store
vi.mock('@/stores/auth', () => ({
  useAuthStore: vi.fn(),
}))

import { useFormSubmit } from '../useFormSubmit'
import { getForm, submitForm as apiSubmitForm, getMyResponse } from '@/api/forms'
import { getSig } from '@/api/sigs'
import { uploadEditorFile } from '@/api/files'
import { useFormResponseDraft } from '@/composables/useFormResponseDraft'

const mockGetForm = getForm as ReturnType<typeof vi.fn>
const mockSubmitForm = apiSubmitForm as ReturnType<typeof vi.fn>
const mockGetMyResponse = getMyResponse as ReturnType<typeof vi.fn>
const mockGetSig = getSig as ReturnType<typeof vi.fn>
const mockUploadEditorFile = uploadEditorFile as ReturnType<typeof vi.fn>
const mockUseFormResponseDraft = useFormResponseDraft as ReturnType<typeof vi.fn>

const t = (key: string, _values?: Record<string, unknown>) => key

function makeQuestion(overrides: Partial<Question> = {}): Question {
  return {
    id: 'q1',
    type: 'text',
    label: 'Name',
    required: true,
    placeholder: '',
    options: [],
    min: 1,
    max: 5,
    ...overrides,
  }
}

function makeFormData(overrides: Partial<FormData> = {}): FormData {
  return {
    id: 'form-1',
    sig_id: 'sig-1',
    title: 'Test Form',
    description: 'Description',
    banner_url: null,
    deadline: null,
    max_respondents: null,
    questions: [makeQuestion()],
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

function createDefaultAuth() {
  return {
    user: { id: 'user1' } as { id: string },
    isAdmin: false,
    isAuthenticated: true,
    isGuest: false,
  }
}

function createHarness(authOverrides: Partial<ReturnType<typeof createDefaultAuth>> = {}) {
  const formId = ref('form-1')
  const mockRouter = { push: vi.fn() } as unknown as import('vue-router').Router
  const auth = { ...createDefaultAuth(), ...authOverrides } as ReturnType<
    typeof import('@/stores/auth').useAuthStore
  >

  onUnmountedCallbacks.length = 0

  const result = useFormSubmit({ formId, auth, router: mockRouter, t })
  return { ...result, formId, mockRouter, auth }
}

describe('useFormSubmit', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.useFakeTimers()
    localStorage.clear()
    onUnmountedCallbacks.length = 0
    mockGetSig.mockResolvedValue({ id: 'sig-1', name: 'Test SIG' })
    mockGetMyResponse.mockRejectedValue(new Error('No response'))

    // Reset the mock to default behavior
    mockUseFormResponseDraft.mockReturnValue({
      draftRestored: ref(false),
      loadDraft: vi.fn(() => false),
      clearDraft: vi.fn(),
      startAutoSave: vi.fn(),
      stopAutoSave: vi.fn(),
    })
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  // 1. Initial loading state
  describe('initial state', () => {
    it('has correct initial values', () => {
      const h = createHarness()
      expect(h.loading.value).toBe(true)
      expect(h.form.value).toBeNull()
      expect(h.submitting.value).toBe(false)
      expect(h.submitted.value).toBe(false)
      expect(h.error.value).toBe('')
      expect(h.message.value).toBe('')
      expect(h.sigName.value).toBe('')
      expect(h.previousResponse.value).toBeNull()
      expect(h.answers.value).toEqual({})
    })
  })

  // 2. Fetching form data successfully
  describe('loadForm', () => {
    it('loads form data and initializes answers', async () => {
      const formData = makeFormData({
        questions: [
          makeQuestion({ id: 'q1', type: 'text' }),
          makeQuestion({ id: 'q2', type: 'multiple_choice' }),
          makeQuestion({ id: 'q3', type: 'rating' }),
        ],
      })
      mockGetForm.mockResolvedValue(formData)

      const h = createHarness()
      await h.loadForm()

      expect(h.form.value).toEqual(formData)
      expect(h.loading.value).toBe(false)
      expect(h.answers.value.q1).toBe('')
      expect(h.answers.value.q2).toEqual([])
      expect(h.answers.value.q3).toBeNull()
      expect(h.sigName.value).toBe('Test SIG')
    })

    it('fetches SIG name for breadcrumbs', async () => {
      mockGetForm.mockResolvedValue(makeFormData())
      mockGetSig.mockResolvedValue({ id: 'sig-1', name: 'My SIG' })

      const h = createHarness()
      await h.loadForm()

      expect(h.sigName.value).toBe('My SIG')
    })

    // 3. Error handling (network error)
    it('sets error on form load failure', async () => {
      mockGetForm.mockRejectedValue(new Error('Network error'))

      const h = createHarness()
      await h.loadForm()

      expect(h.error.value).toBe('forms.view.loadError')
      expect(h.loading.value).toBe(false)
    })

    it('still loads form when SIG fetch fails (breadcrumb fallback)', async () => {
      mockGetForm.mockResolvedValue(makeFormData())
      mockGetSig.mockRejectedValue(new Error('SIG not found'))

      const h = createHarness()
      await h.loadForm()

      expect(h.form.value).not.toBeNull()
      expect(h.sigName.value).toBe('')
    })
  })

  // 4. Setting answer values for different question types
  describe('setting answers', () => {
    it('handles text answers', async () => {
      mockGetForm.mockResolvedValue(
        makeFormData({ questions: [makeQuestion({ id: 'q1', type: 'text' })] }),
      )
      const h = createHarness()
      await h.loadForm()

      h.answers.value.q1 = 'My text answer'
      expect(h.answers.value.q1).toBe('My text answer')
    })

    it('handles single choice answers', async () => {
      mockGetForm.mockResolvedValue(
        makeFormData({
          questions: [
            makeQuestion({
              id: 'q1',
              type: 'single_choice',
              options: [
                { id: 'o1', label: 'A' },
                { id: 'o2', label: 'B' },
              ],
            }),
          ],
        }),
      )
      const h = createHarness()
      await h.loadForm()

      h.answers.value.q1 = 'o1'
      expect(h.answers.value.q1).toBe('o1')
    })

    it('handles rating answers via selectRating', async () => {
      mockGetForm.mockResolvedValue(
        makeFormData({ questions: [makeQuestion({ id: 'q1', type: 'rating' })] }),
      )
      const h = createHarness()
      await h.loadForm()

      h.selectRating('q1', 4)
      expect(h.answers.value.q1).toBe(4)
    })

    it('handles multiple choice via toggleMultipleChoice', async () => {
      mockGetForm.mockResolvedValue(
        makeFormData({
          questions: [
            makeQuestion({
              id: 'q1',
              type: 'multiple_choice',
              options: [
                { id: 'o1', label: 'A' },
                { id: 'o2', label: 'B' },
              ],
            }),
          ],
        }),
      )
      const h = createHarness()
      await h.loadForm()

      h.toggleMultipleChoice('q1', 'o1')
      expect(h.answers.value.q1).toEqual(['o1'])

      h.toggleMultipleChoice('q1', 'o2')
      expect(h.answers.value.q1).toEqual(['o1', 'o2'])

      // Toggle off
      h.toggleMultipleChoice('q1', 'o1')
      expect(h.answers.value.q1).toEqual(['o2'])
    })
  })

  // 5. Required field validation
  describe('validation', () => {
    it('rejects missing required text field', async () => {
      mockGetForm.mockResolvedValue(
        makeFormData({
          questions: [makeQuestion({ id: 'q1', type: 'text', label: 'Name', required: true })],
        }),
      )
      const h = createHarness()
      await h.loadForm()

      // answers.q1 defaults to ''
      await h.submitForm()

      expect(h.error.value).toBeTruthy()
      expect(h.validationErrors.value.q1).toBeTruthy()
      expect(mockSubmitForm).not.toHaveBeenCalled()
    })

    it('rejects empty array for required multiple_choice', async () => {
      mockGetForm.mockResolvedValue(
        makeFormData({
          questions: [
            makeQuestion({ id: 'q1', type: 'multiple_choice', label: 'Choices', required: true }),
          ],
        }),
      )
      const h = createHarness()
      await h.loadForm()

      await h.submitForm()

      expect(h.validationErrors.value.q1).toBeTruthy()
      expect(mockSubmitForm).not.toHaveBeenCalled()
    })

    // 6. Optional field validation
    it('passes when optional field is empty', async () => {
      mockGetForm.mockResolvedValue(
        makeFormData({
          questions: [makeQuestion({ id: 'q1', type: 'text', label: 'Bio', required: false })],
        }),
      )
      mockSubmitForm.mockResolvedValue(undefined)
      const h = createHarness()
      await h.loadForm()

      await h.submitForm()

      expect(h.validationErrors.value.q1).toBeUndefined()
      expect(mockSubmitForm).toHaveBeenCalled()
    })

    it('rejects null for required rating field', async () => {
      mockGetForm.mockResolvedValue(
        makeFormData({
          questions: [makeQuestion({ id: 'q1', type: 'rating', label: 'Rate', required: true })],
        }),
      )
      const h = createHarness()
      await h.loadForm()

      // Rating defaults to null
      await h.submitForm()

      expect(h.validationErrors.value.q1).toBeTruthy()
    })

    // 7. Text max_length validation
    it('rejects text exceeding max_length', async () => {
      mockGetForm.mockResolvedValue(
        makeFormData({
          questions: [
            makeQuestion({ id: 'q1', type: 'text', label: 'Short', required: false, max_length: 5 }),
          ],
        }),
      )
      const h = createHarness()
      await h.loadForm()

      h.answers.value.q1 = 'This is way too long'
      await h.submitForm()

      expect(h.validationErrors.value.q1).toContain('exceeds maximum length')
      expect(mockSubmitForm).not.toHaveBeenCalled()
    })
  })

  // 8. File upload validation - allowed types
  describe('file upload', () => {
    it('rejects file with disallowed extension', async () => {
      mockGetForm.mockResolvedValue(
        makeFormData({
          questions: [
            makeQuestion({
              id: 'q1',
              type: 'file_upload',
              label: 'Upload',
              allowed_types: ['pdf', 'docx'],
            }),
          ],
        }),
      )
      const h = createHarness()
      await h.loadForm()

      const file = new File(['data'], 'image.png', { type: 'image/png' })
      const event = { target: { files: [file], value: '' } } as unknown as Event
      h.handleFileUpload('q1', event)

      expect(h.validationErrors.value.q1).toBe('forms.view.fileTypeError')
    })

    // 9. File upload - validates file size
    it('rejects file exceeding max size', async () => {
      mockGetForm.mockResolvedValue(
        makeFormData({
          questions: [
            makeQuestion({
              id: 'q1',
              type: 'file_upload',
              label: 'Upload',
              max_size_mb: 1,
            }),
          ],
        }),
      )
      const h = createHarness()
      await h.loadForm()

      // Create a file larger than 1MB
      const bigContent = new Uint8Array(2 * 1024 * 1024)
      const file = new File([bigContent], 'big.pdf', { type: 'application/pdf' })
      const event = { target: { files: [file], value: '' } } as unknown as Event
      h.handleFileUpload('q1', event)

      expect(h.validationErrors.value.q1).toBe('forms.view.fileSizeError')
    })

    it('accepts valid file upload', async () => {
      mockGetForm.mockResolvedValue(
        makeFormData({
          questions: [
            makeQuestion({
              id: 'q1',
              type: 'file_upload',
              label: 'Upload',
              allowed_types: ['pdf'],
              max_size_mb: 10,
            }),
          ],
        }),
      )
      const h = createHarness()
      await h.loadForm()

      const file = new File(['data'], 'doc.pdf', { type: 'application/pdf' })
      const event = { target: { files: [file], value: '' } } as unknown as Event
      h.handleFileUpload('q1', event)

      expect(h.validationErrors.value.q1).toBeUndefined()
      expect(h.answers.value.q1).toBe(file)
    })

    it('removeFile clears the answer and preview', async () => {
      mockGetForm.mockResolvedValue(
        makeFormData({
          questions: [makeQuestion({ id: 'q1', type: 'file_upload', label: 'Upload' })],
        }),
      )
      const h = createHarness()
      await h.loadForm()

      const file = new File(['data'], 'doc.pdf', { type: 'application/pdf' })
      h.answers.value.q1 = file
      h.removeFile('q1')

      expect(h.answers.value.q1).toBe('')
    })
  })

  // 10. Submitting form - success flow
  describe('submitForm', () => {
    it('submits form successfully', async () => {
      mockGetForm.mockResolvedValue(
        makeFormData({
          questions: [makeQuestion({ id: 'q1', type: 'text', label: 'Name', required: true })],
        }),
      )
      mockSubmitForm.mockResolvedValue(undefined)
      const h = createHarness()
      await h.loadForm()

      h.answers.value.q1 = 'John'
      await h.submitForm()

      expect(mockSubmitForm).toHaveBeenCalledWith('form-1', { q1: 'John' })
      expect(h.submitted.value).toBe(true)
      expect(h.message.value).toBe('forms.view.successMessage')
    })

    it('cleans empty answers before submit', async () => {
      mockGetForm.mockResolvedValue(
        makeFormData({
          questions: [
            makeQuestion({ id: 'q1', type: 'text', label: 'Name', required: true }),
            makeQuestion({ id: 'q2', type: 'text', label: 'Bio', required: false }),
          ],
        }),
      )
      mockSubmitForm.mockResolvedValue(undefined)
      const h = createHarness()
      await h.loadForm()

      h.answers.value.q1 = 'John'
      // q2 stays empty
      await h.submitForm()

      expect(mockSubmitForm).toHaveBeenCalledWith('form-1', { q1: 'John' })
    })

    it('uploads pending File objects before submit', async () => {
      mockGetForm.mockResolvedValue(
        makeFormData({
          questions: [
            makeQuestion({ id: 'q1', type: 'text', label: 'Name', required: true }),
            makeQuestion({ id: 'q2', type: 'file_upload', label: 'File', required: true }),
          ],
        }),
      )
      mockSubmitForm.mockResolvedValue(undefined)
      mockUploadEditorFile.mockResolvedValue({ url: 'http://s3/file.pdf', key: 'files/file.pdf' })

      const h = createHarness()
      await h.loadForm()

      h.answers.value.q1 = 'John'
      h.answers.value.q2 = new File(['data'], 'file.pdf', { type: 'application/pdf' })
      await h.submitForm()

      expect(mockUploadEditorFile).toHaveBeenCalled()
      expect(mockSubmitForm).toHaveBeenCalledWith('form-1', {
        q1: 'John',
        q2: { key: 'files/file.pdf', filename: 'file.pdf' },
      })
    })

    // 11. Duplicate submission prevented (409)
    it('handles 409 duplicate submission', async () => {
      mockGetForm.mockResolvedValue(
        makeFormData({
          questions: [makeQuestion({ id: 'q1', type: 'text', label: 'Name', required: true })],
        }),
      )
      const mockResponse: FormResponse = {
        id: 'resp-1',
        display_name: 'John',
        created_at: '2026-01-01T00:00:00Z',
        answers: { q1: 'John' },
      }
      mockSubmitForm.mockRejectedValue({ response: { status: 409 } })
      mockGetMyResponse.mockResolvedValue(mockResponse)

      const h = createHarness()
      await h.loadForm()
      h.answers.value.q1 = 'John'
      await h.submitForm()

      expect(h.submitted.value).toBe(true)
      expect(h.message.value).toBe('forms.view.alreadySubmitted')
      expect(h.previousResponse.value).toEqual(mockResponse)
    })

    // 12. Submit error handling
    it('handles generic submit error', async () => {
      mockGetForm.mockResolvedValue(
        makeFormData({
          questions: [makeQuestion({ id: 'q1', type: 'text', label: 'Name', required: true })],
        }),
      )
      mockSubmitForm.mockRejectedValue({
        response: { status: 500, data: { detail: 'Server error' } },
      })

      const h = createHarness()
      await h.loadForm()
      h.answers.value.q1 = 'John'
      await h.submitForm()

      expect(h.error.value).toBe('Server error')
      expect(h.submitted.value).toBe(false)
      expect(h.submitting.value).toBe(false)
    })
  })

  // 13. Scroll to first invalid question on validation failure
  describe('validation scroll behavior', () => {
    it('highlights invalid questions on validation failure', async () => {
      mockGetForm.mockResolvedValue(
        makeFormData({
          questions: [
            makeQuestion({ id: 'q1', type: 'text', label: 'Name', required: true }),
            makeQuestion({ id: 'q2', type: 'text', label: 'Email', required: true }),
          ],
        }),
      )
      const h = createHarness()
      await h.loadForm()

      await h.submitForm()

      expect(h.highlightedQuestions.value.has('q1')).toBe(true)
      expect(h.highlightedQuestions.value.has('q2')).toBe(true)
    })

    it('highlight clears after 3 seconds', async () => {
      mockGetForm.mockResolvedValue(
        makeFormData({
          questions: [makeQuestion({ id: 'q1', type: 'text', label: 'Name', required: true })],
        }),
      )
      const h = createHarness()
      await h.loadForm()

      await h.submitForm()
      expect(h.highlightedQuestions.value.has('q1')).toBe(true)

      vi.advanceTimersByTime(3000)
      expect(h.highlightedQuestions.value.has('q1')).toBe(false)
    })
  })

  // 14. Draft auto-save during form filling
  describe('draft behavior', () => {
    it('calls startAutoSave after loadForm when no previous response', async () => {
      const mockStartAutoSave = vi.fn()
      const mockLoadDraft = vi.fn(() => false)
      mockUseFormResponseDraft.mockReturnValue({
        draftRestored: ref(false),
        loadDraft: mockLoadDraft,
        clearDraft: vi.fn(),
        startAutoSave: mockStartAutoSave,
        stopAutoSave: vi.fn(),
      })
      mockGetForm.mockResolvedValue(makeFormData())

      const h = createHarness()
      await h.loadForm()

      expect(mockLoadDraft).toHaveBeenCalled()
      expect(mockStartAutoSave).toHaveBeenCalled()
    })

    it('does not start auto-save if previous response exists', async () => {
      const mockStartAutoSave = vi.fn()
      mockUseFormResponseDraft.mockReturnValue({
        draftRestored: ref(false),
        loadDraft: vi.fn(() => false),
        clearDraft: vi.fn(),
        startAutoSave: mockStartAutoSave,
        stopAutoSave: vi.fn(),
      })
      mockGetForm.mockResolvedValue(makeFormData())
      mockGetMyResponse.mockResolvedValue({
        id: 'resp-1',
        display_name: 'John',
        created_at: '2026-01-01T00:00:00Z',
        answers: { q1: 'John' },
      })

      const h = createHarness()
      await h.loadForm()

      expect(mockStartAutoSave).not.toHaveBeenCalled()
    })

    it('clearDraft is called on successful submit', async () => {
      const mockClearDraft = vi.fn()
      const mockStopAutoSave = vi.fn()
      mockUseFormResponseDraft.mockReturnValue({
        draftRestored: ref(false),
        loadDraft: vi.fn(() => false),
        clearDraft: mockClearDraft,
        startAutoSave: vi.fn(),
        stopAutoSave: mockStopAutoSave,
      })
      mockGetForm.mockResolvedValue(
        makeFormData({
          questions: [makeQuestion({ id: 'q1', type: 'text', label: 'Name', required: true })],
        }),
      )
      mockSubmitForm.mockResolvedValue(undefined)

      const h = createHarness()
      await h.loadForm()
      h.answers.value.q1 = 'John'
      await h.submitForm()

      expect(mockClearDraft).toHaveBeenCalled()
      expect(mockStopAutoSave).toHaveBeenCalled()
    })
  })

  // 15. Loading existing response (view mode)
  describe('previous response', () => {
    it('loads previous response if user has already submitted', async () => {
      const previousResp: FormResponse = {
        id: 'resp-1',
        display_name: 'John',
        created_at: '2026-01-01T00:00:00Z',
        answers: { q1: 'Previous answer' },
      }
      mockGetForm.mockResolvedValue(makeFormData())
      mockGetMyResponse.mockResolvedValue(previousResp)

      const h = createHarness()
      await h.loadForm()

      expect(h.previousResponse.value).toEqual(previousResp)
    })

    it('showForm is false when previous response exists', async () => {
      mockGetForm.mockResolvedValue(makeFormData())
      mockGetMyResponse.mockResolvedValue({
        id: 'resp-1',
        display_name: 'John',
        created_at: '2026-01-01T00:00:00Z',
        answers: { q1: 'answer' },
      })

      const h = createHarness()
      await h.loadForm()

      expect(h.showForm.value).toBe(false)
    })

    it('showForm is false for guest users', async () => {
      mockGetForm.mockResolvedValue(makeFormData())

      const h = createHarness({ isGuest: true })
      await h.loadForm()

      expect(h.showForm.value).toBe(false)
    })

    it('showForm is true for authenticated non-guest with active form and no previous response', async () => {
      mockGetForm.mockResolvedValue(makeFormData({ is_active: true }))
      mockGetMyResponse.mockRejectedValue(new Error('No response'))

      const h = createHarness()
      await h.loadForm()

      expect(h.showForm.value).toBe(true)
    })
  })

  // Computed properties
  describe('computed properties', () => {
    it('progressPercent calculates correctly', async () => {
      mockGetForm.mockResolvedValue(
        makeFormData({
          questions: [
            makeQuestion({ id: 'q1', type: 'text' }),
            makeQuestion({ id: 'q2', type: 'text' }),
            makeQuestion({ id: 'q3', type: 'text' }),
            makeQuestion({ id: 'q4', type: 'text' }),
          ],
        }),
      )
      const h = createHarness()
      await h.loadForm()

      expect(h.progressPercent.value).toBe(0)
      expect(h.totalQuestions.value).toBe(4)

      h.answers.value.q1 = 'answer'
      expect(h.answeredCount.value).toBe(1)
      expect(h.progressPercent.value).toBe(25)

      h.answers.value.q2 = 'answer'
      expect(h.progressPercent.value).toBe(50)
    })

    it('canEdit is true for form creator', async () => {
      mockGetForm.mockResolvedValue(makeFormData({ created_by: 'user1' }))
      mockGetMyResponse.mockRejectedValue(new Error('No response'))

      const h = createHarness({ user: { id: 'user1' } })
      await h.loadForm()

      expect(h.canEdit.value).toBe(true)
    })

    it('canEdit is true for admin', async () => {
      mockGetForm.mockResolvedValue(makeFormData({ created_by: 'other' }))
      mockGetMyResponse.mockRejectedValue(new Error('No response'))

      const h = createHarness({ isAdmin: true })
      await h.loadForm()

      expect(h.canEdit.value).toBe(true)
    })

    it('canExport is true for admin', async () => {
      mockGetForm.mockResolvedValue(makeFormData())
      mockGetMyResponse.mockRejectedValue(new Error('No response'))

      const h = createHarness({ isAdmin: true })
      await h.loadForm()

      expect(h.canExport.value).toBe(true)
    })

    it('canExport is true for SIG admin', async () => {
      mockGetForm.mockResolvedValue(makeFormData({ user_is_sig_admin: true }))
      mockGetMyResponse.mockRejectedValue(new Error('No response'))

      const h = createHarness()
      await h.loadForm()

      expect(h.canExport.value).toBe(true)
    })
  })

  // Rating helpers
  describe('rating helpers', () => {
    it('ratingRange returns correct range', () => {
      const h = createHarness()
      const q = makeQuestion({ type: 'rating', min: 1, max: 5 })
      expect(h.ratingRange(q)).toEqual([1, 2, 3, 4, 5])
    })

    it('ratingRange uses defaults', () => {
      const h = createHarness()
      const q = makeQuestion({ type: 'rating', min: undefined, max: undefined })
      expect(h.ratingRange(q)).toEqual([1, 2, 3, 4, 5])
    })

    it('ratingCount returns correct count', () => {
      const h = createHarness()
      const q = makeQuestion({ type: 'rating', min: 2, max: 8 })
      expect(h.ratingCount(q)).toBe(7)
    })
  })

  // Display answer helpers
  describe('getDisplayAnswer', () => {
    it('returns noAnswer for null/empty', () => {
      const h = createHarness()
      const q = makeQuestion()
      expect(h.getDisplayAnswer(q, null)).toBe('forms.view.noAnswer')
      expect(h.getDisplayAnswer(q, '')).toBe('forms.view.noAnswer')
    })

    it('resolves single_choice option label', () => {
      const h = createHarness()
      const q = makeQuestion({
        type: 'single_choice',
        options: [
          { id: 'o1', label: 'Option A' },
          { id: 'o2', label: 'Option B' },
        ],
      })
      expect(h.getDisplayAnswer(q, 'o1')).toBe('Option A')
    })

    it('resolves multiple_choice option labels', () => {
      const h = createHarness()
      const q = makeQuestion({
        type: 'multiple_choice',
        options: [
          { id: 'o1', label: 'A' },
          { id: 'o2', label: 'B' },
        ],
      })
      expect(h.getDisplayAnswer(q, ['o1', 'o2'])).toBe('A, B')
    })

    it('returns noAnswer for empty multiple_choice array', () => {
      const h = createHarness()
      const q = makeQuestion({ type: 'multiple_choice' })
      expect(h.getDisplayAnswer(q, [])).toBe('forms.view.noAnswer')
    })

    it('returns rating as string', () => {
      const h = createHarness()
      const q = makeQuestion({ type: 'rating' })
      expect(h.getDisplayAnswer(q, 4)).toBe('4')
    })

    it('returns filename for file_upload', () => {
      const h = createHarness()
      const q = makeQuestion({ type: 'file_upload' })
      expect(h.getDisplayAnswer(q, { filename: 'doc.pdf' })).toBe('doc.pdf')
    })

    it('returns fileUploaded for file_upload without filename', () => {
      const h = createHarness()
      const q = makeQuestion({ type: 'file_upload' })
      expect(h.getDisplayAnswer(q, { key: 'files/doc.pdf' })).toBe('forms.view.fileUploaded')
    })
  })

  // Utility functions
  describe('utility functions', () => {
    it('isFileObject returns true for File instances', () => {
      const h = createHarness()
      const file = new File(['data'], 'test.txt')
      expect(h.isFileObject(file)).toBe(true)
      expect(h.isFileObject('not a file')).toBe(false)
    })

    it('getFileName returns file name from File', () => {
      const h = createHarness()
      const file = new File(['data'], 'test.txt')
      expect(h.getFileName(file)).toBe('test.txt')
    })

    it('getFileName returns filename from object', () => {
      const h = createHarness()
      expect(h.getFileName({ filename: 'doc.pdf' })).toBe('doc.pdf')
    })

    it('getFileName returns empty for unknown', () => {
      const h = createHarness()
      expect(h.getFileName('something')).toBe('')
    })

    it('formatFileSize formats bytes correctly', () => {
      const h = createHarness()
      expect(h.formatFileSize(500)).toBe('500 B')
      expect(h.formatFileSize(2048)).toBe('2.0 KB')
      expect(h.formatFileSize(2 * 1024 * 1024)).toBe('2.0 MB')
    })
  })

  // getResponseAnswers
  describe('getResponseAnswers', () => {
    it('returns previousResponse answers when exists', async () => {
      mockGetForm.mockResolvedValue(makeFormData())
      mockGetMyResponse.mockResolvedValue({
        id: 'resp-1',
        display_name: 'John',
        created_at: '2026-01-01T00:00:00Z',
        answers: { q1: 'Previous' },
      })

      const h = createHarness()
      await h.loadForm()

      expect(h.getResponseAnswers()).toEqual({ q1: 'Previous' })
    })

    it('returns submittedAnswers when no previousResponse', async () => {
      mockGetForm.mockResolvedValue(
        makeFormData({
          questions: [makeQuestion({ id: 'q1', type: 'text', label: 'Name', required: true })],
        }),
      )
      mockSubmitForm.mockResolvedValue(undefined)

      const h = createHarness()
      await h.loadForm()
      h.answers.value.q1 = 'John'
      await h.submitForm()

      expect(h.getResponseAnswers()).toEqual({ q1: 'John' })
    })
  })

  // handleClearDraft
  describe('handleClearDraft', () => {
    it('resets answers to defaults when draft is cleared', async () => {
      const mockClearDraft = vi.fn()
      mockUseFormResponseDraft.mockReturnValue({
        draftRestored: ref(false),
        loadDraft: vi.fn(() => false),
        clearDraft: mockClearDraft,
        startAutoSave: vi.fn(),
        stopAutoSave: vi.fn(),
      })
      mockGetForm.mockResolvedValue(
        makeFormData({
          questions: [
            makeQuestion({ id: 'q1', type: 'text' }),
            makeQuestion({ id: 'q2', type: 'multiple_choice' }),
            makeQuestion({ id: 'q3', type: 'rating' }),
          ],
        }),
      )

      const h = createHarness()
      await h.loadForm()

      h.answers.value.q1 = 'filled'
      h.answers.value.q2 = ['o1']
      h.answers.value.q3 = 4

      h.handleClearDraft()

      expect(mockClearDraft).toHaveBeenCalled()
      expect(h.answers.value.q1).toBe('')
      expect(h.answers.value.q2).toEqual([])
      expect(h.answers.value.q3).toBeNull()
    })
  })

  // goBackToSig
  describe('goBackToSig', () => {
    it('navigates to SIG page', async () => {
      mockGetForm.mockResolvedValue(makeFormData({ sig_id: 'sig-42' }))
      mockGetMyResponse.mockRejectedValue(new Error('No response'))

      const h = createHarness()
      await h.loadForm()
      h.goBackToSig()

      expect(
        (h.mockRouter as unknown as { push: ReturnType<typeof vi.fn> }).push,
      ).toHaveBeenCalledWith('/sigs/sig-42')
    })
  })

  // Error clearing
  describe('error clearing on input', () => {
    it('onTextInput clears validation error for question', async () => {
      mockGetForm.mockResolvedValue(
        makeFormData({
          questions: [makeQuestion({ id: 'q1', type: 'text', label: 'Name', required: true })],
        }),
      )
      const h = createHarness()
      await h.loadForm()

      // Trigger validation error
      await h.submitForm()
      expect(h.validationErrors.value.q1).toBeTruthy()

      // Clear via text input handler
      h.onTextInput('q1')
      expect(h.validationErrors.value.q1).toBeUndefined()
    })

    it('onSelectChange clears validation error', async () => {
      mockGetForm.mockResolvedValue(
        makeFormData({
          questions: [
            makeQuestion({ id: 'q1', type: 'dropdown', label: 'Pick', required: true }),
          ],
        }),
      )
      const h = createHarness()
      await h.loadForm()

      await h.submitForm()
      expect(h.validationErrors.value.q1).toBeTruthy()

      h.onSelectChange('q1')
      expect(h.validationErrors.value.q1).toBeUndefined()
    })

    it('onRadioChange clears validation error', async () => {
      mockGetForm.mockResolvedValue(
        makeFormData({
          questions: [
            makeQuestion({ id: 'q1', type: 'single_choice', label: 'Pick', required: true }),
          ],
        }),
      )
      const h = createHarness()
      await h.loadForm()

      await h.submitForm()
      expect(h.validationErrors.value.q1).toBeTruthy()

      h.onRadioChange('q1')
      expect(h.validationErrors.value.q1).toBeUndefined()
    })
  })
})

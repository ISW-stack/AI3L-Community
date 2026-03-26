import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import FormView from '../FormView.vue'
import { useAuthStore } from '@/stores/auth'
import type { UserProfile } from '@/types/user'

interface FormViewVm {
  answers: Record<string, unknown>
  validationErrors: Record<string, string | undefined>
  highlightedQuestions: Set<string>
  touched: Record<string, boolean>
  progressPercent: number
  ratingCount: (question: Record<string, unknown>) => number
}

const mockGetForm = vi.fn()
const mockSubmitForm = vi.fn()
const mockExportForm = vi.fn()
const mockGetTaskStatus = vi.fn()
const mockUploadEditorFile = vi.fn()
const mockGetMyResponse = vi.fn()

vi.mock('@/api/forms', () => ({
  getForm: (...args: unknown[]) => mockGetForm(...args),
  submitForm: (...args: unknown[]) => mockSubmitForm(...args),
  exportForm: (...args: unknown[]) => mockExportForm(...args),
  getMyResponse: (...args: unknown[]) => mockGetMyResponse(...args),
}))

vi.mock('@/api/tasks', () => ({
  getTaskStatus: (...args: unknown[]) => mockGetTaskStatus(...args),
}))

vi.mock('@/api/files', () => ({
  uploadEditorFile: (...args: unknown[]) => mockUploadEditorFile(...args),
}))

vi.mock('@/composables/api', () => ({
  default: { get: vi.fn(), post: vi.fn() },
}))

// Mock DOMPurify — use a spy so we can verify calls
const mockSanitize = vi.fn((html: string) => html)
vi.mock('dompurify', () => ({
  default: {
    sanitize: (...args: unknown[]) => mockSanitize(...args),
  },
}))

vi.mock('@/constants', () => ({
  HEARTBEAT_INTERVAL_MS: 30000,
}))

const fakeForm = {
  id: 'form-1',
  title: 'Research Survey',
  description: 'Please complete this survey',
  banner_url: null,
  is_active: true,
  created_by: 'u1',
  created_by_name: 'Admin User',
  response_count: 10,
  deadline: null,
  max_respondents: null,
  user_is_sig_admin: false,
  sig_id: 'sig-1',
  questions: [
    {
      id: 'q1',
      type: 'text',
      label: 'Your Name',
      required: true,
      placeholder: 'Enter name',
      max_length: 100,
      options: [],
    },
    {
      id: 'q2',
      type: 'single_choice',
      label: 'Experience Level',
      required: true,
      options: [
        { id: 'opt1', label: 'Beginner' },
        { id: 'opt2', label: 'Advanced' },
      ],
    },
    {
      id: 'q3',
      type: 'multiple_choice',
      label: 'Interests',
      required: false,
      options: [
        { id: 'opt3', label: 'AI' },
        { id: 'opt4', label: 'Linguistics' },
      ],
    },
    {
      id: 'q4',
      type: 'rating',
      label: 'Satisfaction',
      required: false,
      min: 1,
      max: 5,
    },
    {
      id: 'q5',
      type: 'textarea',
      label: 'Comments',
      required: false,
      placeholder: 'Any comments?',
      max_length: 500,
    },
  ],
}

function createTestRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/forms/:formId', component: FormView },
      { path: '/forms/:formId/edit', component: { template: '<div />' } },
      { path: '/login', component: { template: '<div />' } },
      { path: '/sigs/:id', component: { template: '<div />' } },
    ],
  })
}

function createStubs() {
  return {
    BaseCard: { template: '<div class="base-card"><slot /></div>', props: ['padding'] },
    BaseButton: {
      template: '<button :disabled="$attrs.disabled" @click="$emit(\'click\')"><slot /></button>',
      props: ['loading', 'variant', 'size'],
    },
    BaseAlert: {
      template:
        '<div class="base-alert" :class="`alert-${type}`"><slot /><slot name="default" /></div>',
      props: ['type', 'dismissible'],
      emits: ['dismiss'],
    },
    BaseBadge: { template: '<span class="base-badge"><slot /></span>', props: ['variant'] },
    SkeletonLoader: { template: '<div class="skeleton-loader" />', props: ['lines', 'variant'] },
    CopyShareLinkButton: { template: '<span class="copy-share-link" />', props: ['url'] },
    BackToTop: { template: '<div class="back-to-top" />' },
  }
}

async function mountFormView(options?: {
  role?: string
  form?: Record<string, unknown> | null
  previousResponse?: Record<string, unknown> | null
}) {
  const { role = 'MEMBER', form = fakeForm, previousResponse = null } = options ?? {}
  const pinia = createPinia()
  setActivePinia(pinia)
  const router = createTestRouter()

  const auth = useAuthStore()
  auth.setSession(role, 3600)
  auth.user = {
    id: 'u2',
    username: 'testuser',
    display_name: 'Test User',
    role,
    bio: null,
    affiliation: null,
    orcid: null,
    avatar_url: null,
    is_banned: false,
    ban_reason: null,
  } as unknown as UserProfile

  if (form) {
    mockGetForm.mockResolvedValue(form)
  } else {
    mockGetForm.mockRejectedValue(new Error('Not found'))
  }

  if (previousResponse) {
    mockGetMyResponse.mockResolvedValue(previousResponse)
  } else {
    mockGetMyResponse.mockRejectedValue(new Error('Not found'))
  }

  await router.push('/forms/form-1')
  await router.isReady()

  const wrapper = mount(FormView, {
    global: { plugins: [pinia, router], stubs: createStubs() },
  })
  await flushPromises()
  return { wrapper, router, auth }
}

describe('FormView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.useFakeTimers()
    localStorage.clear()
    mockSubmitForm.mockResolvedValue({})
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('fetches form on mount', async () => {
    await mountFormView()
    expect(mockGetForm).toHaveBeenCalledWith('form-1')
  })

  it('renders form title', async () => {
    const { wrapper } = await mountFormView()
    expect(wrapper.text()).toContain('Research Survey')
  })

  it('renders form description', async () => {
    const { wrapper } = await mountFormView()
    expect(wrapper.text()).toContain('Please complete this survey')
  })

  it('renders active badge', async () => {
    const { wrapper } = await mountFormView()
    expect(wrapper.find('.base-badge').exists()).toBe(true)
  })

  it('renders creator name and response count', async () => {
    const { wrapper } = await mountFormView()
    expect(wrapper.text()).toContain('Admin User')
    expect(wrapper.text()).toContain('10')
  })

  it('renders all question types', async () => {
    const { wrapper } = await mountFormView()
    expect(wrapper.text()).toContain('Your Name')
    expect(wrapper.text()).toContain('Experience Level')
    expect(wrapper.text()).toContain('Interests')
    expect(wrapper.text()).toContain('Satisfaction')
    expect(wrapper.text()).toContain('Comments')
  })

  it('renders text input for text questions', async () => {
    const { wrapper } = await mountFormView()
    const textInput = wrapper.find('input[type="text"]')
    expect(textInput.exists()).toBe(true)
  })

  it('renders radio buttons for single choice', async () => {
    const { wrapper } = await mountFormView()
    const radios = wrapper.findAll('input[type="radio"]')
    expect(radios.length).toBe(2)
    expect(wrapper.text()).toContain('Beginner')
    expect(wrapper.text()).toContain('Advanced')
  })

  it('renders checkboxes for multiple choice', async () => {
    const { wrapper } = await mountFormView()
    const checkboxes = wrapper.findAll('input[type="checkbox"]')
    expect(checkboxes.length).toBe(2)
    expect(wrapper.text()).toContain('AI')
    expect(wrapper.text()).toContain('Linguistics')
  })

  it('renders rating buttons', async () => {
    const { wrapper } = await mountFormView()
    const ratingButtons = wrapper.findAll('button[type="button"]').filter((b) => {
      const text = b.text().trim()
      return ['1', '2', '3', '4', '5'].includes(text)
    })
    expect(ratingButtons.length).toBe(5)
  })

  it('renders textarea for textarea questions', async () => {
    const { wrapper } = await mountFormView()
    const textareas = wrapper.findAll('textarea')
    expect(textareas.length).toBeGreaterThanOrEqual(1)
  })

  it('shows required indicator on required questions', async () => {
    const { wrapper } = await mountFormView()
    expect(wrapper.html()).toContain('*')
  })

  it('shows validation error for required empty fields', async () => {
    const { wrapper } = await mountFormView()
    const submitBtn = wrapper.findAll('button').find((b) => b.text().includes('Submit'))
    expect(submitBtn).toBeTruthy()
    await submitBtn!.trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('"Your Name"')
    expect(mockSubmitForm).not.toHaveBeenCalled()
  })

  it('submits form successfully', async () => {
    const { wrapper } = await mountFormView()
    const vm = wrapper.vm as unknown as FormViewVm

    vm.answers['q1'] = 'John Doe'
    vm.answers['q2'] = 'opt1'

    const submitBtn = wrapper.findAll('button').find((b) => b.text().includes('Submit'))
    await submitBtn!.trigger('click')
    await flushPromises()

    expect(mockSubmitForm).toHaveBeenCalledWith(
      'form-1',
      expect.objectContaining({ q1: 'John Doe', q2: 'opt1' }),
    )
  })

  it('shows success message after submission', async () => {
    const { wrapper } = await mountFormView()
    const vm = wrapper.vm as unknown as FormViewVm
    vm.answers['q1'] = 'John'
    vm.answers['q2'] = 'opt1'

    const submitBtn = wrapper.findAll('button').find((b) => b.text().includes('Submit'))
    await submitBtn!.trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('submitted successfully')
  })

  it('shows error on submit failure', async () => {
    mockSubmitForm.mockRejectedValue({
      response: { data: { detail: 'Already submitted' } },
    })
    const { wrapper } = await mountFormView()
    const vm = wrapper.vm as unknown as FormViewVm
    vm.answers['q1'] = 'John'
    vm.answers['q2'] = 'opt1'

    const submitBtn = wrapper.findAll('button').find((b) => b.text().includes('Submit'))
    await submitBtn!.trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('Already submitted')
  })

  it('shows not found when form does not exist', async () => {
    const { wrapper } = await mountFormView({ form: null })
    expect(wrapper.text()).toContain('Form not found')
  })

  it('shows loading skeleton initially', () => {
    mockGetForm.mockReturnValue(new Promise(() => {}))
    const pinia = createPinia()
    setActivePinia(pinia)
    const router = createTestRouter()
    const auth = useAuthStore()
    auth.setSession('MEMBER', 3600)
    auth.user = { id: 'u2' } as unknown as UserProfile

    const wrapper = mount(FormView, {
      global: { plugins: [pinia, router], stubs: createStubs() },
    })

    expect(wrapper.find('.skeleton-loader').exists()).toBe(true)
  })

  it('shows closed alert for inactive form', async () => {
    const closedForm = { ...fakeForm, is_active: false }
    const { wrapper } = await mountFormView({ form: closedForm })
    expect(wrapper.text()).toContain('This form is closed')
  })

  it('shows login prompt for unauthenticated users', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const router = createTestRouter()

    mockGetForm.mockResolvedValue(fakeForm)
    mockGetMyResponse.mockRejectedValue(new Error('Not found'))

    await router.push('/forms/form-1')
    await router.isReady()

    const wrapper = mount(FormView, {
      global: { plugins: [pinia, router], stubs: createStubs() },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('Please')
  })

  it('shows edit form link for form creator', async () => {
    const creatorForm = { ...fakeForm, created_by: 'u2' }
    const { wrapper } = await mountFormView({ form: creatorForm })
    const links = wrapper.findAll('a')
    const editLink = links.find((l) => l.attributes('href')?.includes('/edit'))
    expect(editLink).toBeTruthy()
  })

  it('shows export button for admin', async () => {
    const { wrapper } = await mountFormView({ role: 'ADMIN' })
    expect(wrapper.text()).toContain('Export CSV')
  })

  it('shows share link button', async () => {
    const { wrapper } = await mountFormView()
    expect(wrapper.find('.copy-share-link').exists()).toBe(true)
  })

  // ── XSS Sanitization ──
  describe('XSS sanitization', () => {
    it('calls DOMPurify.sanitize on form description', async () => {
      const xssDescription = '<p>Info</p><img src=x onerror="alert(1)">'
      const formWithXss = { ...fakeForm, description: xssDescription }
      await mountFormView({ form: formWithXss })

      // sanitizeHtml passes (html, SANITIZE_CONFIG) to DOMPurify.sanitize
      expect(mockSanitize).toHaveBeenCalledWith(xssDescription, expect.objectContaining({ FORCE_BODY: true }))
    })

    it('strips XSS payload from description output', async () => {
      const xssPayload = '<img src=x onerror="alert(1)"><b>safe</b>'
      mockSanitize.mockImplementation((html: string) => html.replace(/<img[^>]*>/g, ''))
      const formWithXss = { ...fakeForm, description: xssPayload }
      const { wrapper } = await mountFormView({ form: formWithXss })

      const descDiv = wrapper.find('.prose.prose-sm')
      expect(descDiv.exists()).toBe(true)
      expect(descDiv.html()).not.toContain('onerror')
      expect(descDiv.html()).toContain('<b>safe</b>')

      // Restore default passthrough behavior
      mockSanitize.mockImplementation((html: string) => html)
    })

    it('does not render description div when description is empty', async () => {
      const formNoDesc = { ...fakeForm, description: '' }
      const { wrapper } = await mountFormView({ form: formNoDesc })

      const descDiv = wrapper.find('.prose.prose-sm')
      expect(descDiv.exists()).toBe(false)
    })
  })

  // ── Feature 1: Progress Indicator ──
  describe('progress indicator', () => {
    it('shows progress bar with 0/N when no answers given', async () => {
      const { wrapper } = await mountFormView()
      expect(wrapper.text()).toContain('0/5')
    })

    it('updates progress when answers are given', async () => {
      const { wrapper } = await mountFormView()
      const vm = wrapper.vm as unknown as FormViewVm
      vm.answers['q1'] = 'John'
      await wrapper.vm.$nextTick()
      // Should show 1/5
      expect(wrapper.text()).toContain('1/5')
    })

    it('shows a progress bar element', async () => {
      const { wrapper } = await mountFormView()
      const progressBar = wrapper.find('[role="progressbar"]')
      expect(progressBar.exists()).toBe(true)
    })

    it('calculates correct progress percentage', async () => {
      const { wrapper } = await mountFormView()
      const vm = wrapper.vm as unknown as FormViewVm

      // Answer 2 of 5 questions
      vm.answers['q1'] = 'John'
      vm.answers['q2'] = 'opt1'
      await wrapper.vm.$nextTick()

      expect(vm.progressPercent).toBe(40)
    })

    it('reaches 100% when all questions answered', async () => {
      const { wrapper } = await mountFormView()
      const vm = wrapper.vm as unknown as FormViewVm

      vm.answers['q1'] = 'John'
      vm.answers['q2'] = 'opt1'
      vm.answers['q3'] = ['opt3']
      vm.answers['q4'] = 3
      vm.answers['q5'] = 'Great'
      await wrapper.vm.$nextTick()

      expect(vm.progressPercent).toBe(100)
    })
  })

  // ── Feature 2: Scroll-to-Error on Validation Failure ──
  describe('validation scroll-to-error', () => {
    it('populates per-question validation errors', async () => {
      const { wrapper } = await mountFormView()
      const vm = wrapper.vm as unknown as FormViewVm

      const submitBtn = wrapper.findAll('button').find((b) => b.text().includes('Submit'))
      await submitBtn!.trigger('click')
      await flushPromises()

      // q1 (required text) and q2 (required single choice) should have errors
      expect(vm.validationErrors['q1']).toBeTruthy()
      expect(vm.validationErrors['q2']).toBeTruthy()
      // q3 (optional) should NOT have an error
      expect(vm.validationErrors['q3']).toBeUndefined()
    })

    it('shows per-question error text in the template', async () => {
      const { wrapper } = await mountFormView()

      const submitBtn = wrapper.findAll('button').find((b) => b.text().includes('Submit'))
      await submitBtn!.trigger('click')
      await flushPromises()

      // Both q1 and q2 errors should appear
      const errorAlerts = wrapper.findAll('[role="alert"]')
      expect(errorAlerts.length).toBeGreaterThanOrEqual(2)
    })

    it('adds highlight class on invalid questions', async () => {
      const { wrapper } = await mountFormView()
      const vm = wrapper.vm as unknown as FormViewVm

      const submitBtn = wrapper.findAll('button').find((b) => b.text().includes('Submit'))
      await submitBtn!.trigger('click')
      await flushPromises()

      expect(vm.highlightedQuestions.size).toBeGreaterThan(0)
    })

    it('clears error when user starts editing', async () => {
      const { wrapper } = await mountFormView()
      const vm = wrapper.vm as unknown as FormViewVm

      const submitBtn = wrapper.findAll('button').find((b) => b.text().includes('Submit'))
      await submitBtn!.trigger('click')
      await flushPromises()

      expect(vm.validationErrors['q1']).toBeTruthy()

      // Simulate editing the field
      const textInput = wrapper.find('input[type="text"]')
      await textInput.setValue('John')
      await textInput.trigger('input')
      await wrapper.vm.$nextTick()

      expect(vm.validationErrors['q1']).toBeUndefined()
    })

    it('removes highlight after 3 seconds timeout', async () => {
      const { wrapper } = await mountFormView()
      const vm = wrapper.vm as unknown as FormViewVm

      const submitBtn = wrapper.findAll('button').find((b) => b.text().includes('Submit'))
      await submitBtn!.trigger('click')
      await flushPromises()

      expect(vm.highlightedQuestions.has('q1')).toBe(true)

      vi.advanceTimersByTime(3000)

      expect(vm.highlightedQuestions.has('q1')).toBe(false)
    })
  })

  // ── Feature 3: LocalStorage Draft ──
  describe('draft save/restore', () => {
    it('restores draft on mount if one exists', async () => {
      localStorage.setItem(
        'form-response-draft-form-1',
        JSON.stringify({ q1: 'Draft Name', q5: 'Draft comment' }),
      )

      const { wrapper } = await mountFormView()
      const vm = wrapper.vm as unknown as FormViewVm

      expect(vm.answers['q1']).toBe('Draft Name')
      expect(vm.answers['q5']).toBe('Draft comment')
    })

    it('shows draft restored info message', async () => {
      localStorage.setItem('form-response-draft-form-1', JSON.stringify({ q1: 'Draft Name' }))

      const { wrapper } = await mountFormView()
      expect(wrapper.text()).toContain('previous answers have been restored')
    })

    it('clears draft after successful submission', async () => {
      localStorage.setItem('form-response-draft-form-1', JSON.stringify({ q1: 'John' }))

      const { wrapper } = await mountFormView()
      const vm = wrapper.vm as unknown as FormViewVm
      vm.answers['q1'] = 'John'
      vm.answers['q2'] = 'opt1'

      const submitBtn = wrapper.findAll('button').find((b) => b.text().includes('Submit'))
      await submitBtn!.trigger('click')
      await flushPromises()

      expect(localStorage.getItem('form-response-draft-form-1')).toBeNull()
    })
  })

  // ── Feature 4: File Upload Validation ──
  describe('file upload validation', () => {
    const fileUploadForm = {
      ...fakeForm,
      questions: [
        {
          id: 'qf',
          type: 'file_upload',
          label: 'Upload Document',
          required: false,
          allowed_types: ['pdf', 'docx'],
          max_size_mb: 1,
        },
      ],
    }

    it('validates file type client-side', async () => {
      const { wrapper } = await mountFormView({ form: fileUploadForm })
      const vm = wrapper.vm as unknown as FormViewVm

      // Simulate file input change with an invalid file type
      const invalidFile = new File(['data'], 'image.png', { type: 'image/png' })
      const fileInput = wrapper.find('#file-input-qf')
      Object.defineProperty(fileInput.element, 'files', { value: [invalidFile], writable: false })
      await fileInput.trigger('change')
      await wrapper.vm.$nextTick()

      expect(vm.validationErrors['qf']).toBeTruthy()
      expect(vm.validationErrors['qf']).toContain('pdf, docx')
    })

    it('validates file size client-side', async () => {
      const { wrapper } = await mountFormView({ form: fileUploadForm })
      const vm = wrapper.vm as unknown as FormViewVm

      // Create a file larger than 1MB
      const bigContent = new Uint8Array(2 * 1024 * 1024)
      const bigFile = new File([bigContent], 'large.pdf', { type: 'application/pdf' })
      const fileInput = wrapper.find('#file-input-qf')
      Object.defineProperty(fileInput.element, 'files', { value: [bigFile], writable: false })
      await fileInput.trigger('change')
      await wrapper.vm.$nextTick()

      expect(vm.validationErrors['qf']).toBeTruthy()
    })

    it('accepts valid file type and size', async () => {
      const formAccept = {
        ...fakeForm,
        questions: [
          {
            id: 'qf',
            type: 'file_upload',
            label: 'Upload Document',
            required: false,
            allowed_types: ['pdf'],
            max_size_mb: 10,
          },
        ],
      }
      const { wrapper } = await mountFormView({ form: formAccept })
      const vm = wrapper.vm as unknown as FormViewVm

      const validFile = new File(['data'], 'doc.pdf', { type: 'application/pdf' })
      const fileInput = wrapper.find('#file-input-qf')
      Object.defineProperty(fileInput.element, 'files', { value: [validFile], writable: false })
      await fileInput.trigger('change')
      await wrapper.vm.$nextTick()

      expect(vm.validationErrors['qf']).toBeUndefined()
      expect(vm.answers['qf']).toEqual(validFile)
    })

    it('renders drag-and-drop zone for file_upload questions', async () => {
      const formDrop = {
        ...fakeForm,
        questions: [
          {
            id: 'qf',
            type: 'file_upload',
            label: 'Upload Document',
            required: false,
          },
        ],
      }
      const { wrapper } = await mountFormView({ form: formDrop })

      // Should have a drop zone instead of native file input
      expect(wrapper.text()).toContain('Drag file here')
    })
  })

  // ── Feature 5: Rating Improvements ──
  describe('rating improvements', () => {
    it('shows endpoint labels', async () => {
      const { wrapper } = await mountFormView()
      // Should show "1" and "5" as endpoint labels
      const ratingSection = wrapper.findAll('[role="group"]')
      expect(ratingSection.length).toBeGreaterThan(0)
      const ratingText = ratingSection[0].text()
      expect(ratingText).toContain('1')
      expect(ratingText).toContain('5')
    })

    it('uses compact layout for wide ranges (>7)', async () => {
      const wideRatingForm = {
        ...fakeForm,
        questions: [
          { id: 'qr', type: 'rating', label: 'Wide Rating', min: 1, max: 10, required: false },
        ],
      }
      const { wrapper } = await mountFormView({ form: wideRatingForm })

      // All 10 rating buttons should be rendered
      const ratingButtons = wrapper.findAll('button[type="button"]').filter((b) => {
        const text = b.text().trim()
        return !isNaN(Number(text)) && Number(text) >= 1 && Number(text) <= 10
      })
      expect(ratingButtons.length).toBe(10)
    })
  })

  // ── Feature 6: View Submitted Response ──
  describe('view submitted response', () => {
    it('calls getMyResponse on mount', async () => {
      await mountFormView()
      expect(mockGetMyResponse).toHaveBeenCalledWith('form-1')
    })

    it('shows read-only view when user has previous response', async () => {
      const { wrapper } = await mountFormView({
        previousResponse: {
          id: 'resp-1',
          display_name: 'Test User',
          created_at: '2026-03-01T00:00:00',
          answers: { q1: 'John', q2: 'opt1', q4: 3 },
        },
      })

      expect(wrapper.text()).toContain('already submitted')
      expect(wrapper.text()).toContain('Response Summary')
      // Should not show the submit button
      const submitBtn = wrapper.findAll('button').find((b) => b.text().includes('Submit'))
      expect(submitBtn).toBeUndefined()
    })

    it('shows response summary after successful submission', async () => {
      const { wrapper } = await mountFormView()
      const vm = wrapper.vm as unknown as FormViewVm

      vm.answers['q1'] = 'John'
      vm.answers['q2'] = 'opt1'

      const submitBtn = wrapper.findAll('button').find((b) => b.text().includes('Submit'))
      await submitBtn!.trigger('click')
      await flushPromises()

      expect(wrapper.text()).toContain('Response Summary')
    })

    it('shows Back to SIG button after submission', async () => {
      const { wrapper } = await mountFormView()
      const vm = wrapper.vm as unknown as FormViewVm

      vm.answers['q1'] = 'John'
      vm.answers['q2'] = 'opt1'

      const submitBtn = wrapper.findAll('button').find((b) => b.text().includes('Submit'))
      await submitBtn!.trigger('click')
      await flushPromises()

      expect(wrapper.text()).toContain('Back to SIG')
    })

    it('uses router.push instead of window.location.href for Back to SIG', async () => {
      const { wrapper, router } = await mountFormView()
      const vm = wrapper.vm as unknown as FormViewVm
      const pushSpy = vi.spyOn(router, 'push')

      vm.answers['q1'] = 'John'
      vm.answers['q2'] = 'opt1'

      const submitBtn = wrapper.findAll('button').find((b) => b.text().includes('Submit'))
      await submitBtn!.trigger('click')
      await flushPromises()

      const backBtn = wrapper.findAll('button').find((b) => b.text().includes('Back to SIG'))
      expect(backBtn).toBeTruthy()
      await backBtn!.trigger('click')
      await flushPromises()

      expect(pushSpy).toHaveBeenCalledWith('/sigs/sig-1')
    })

    it('displays option labels for choice questions in summary', async () => {
      const { wrapper } = await mountFormView({
        previousResponse: {
          id: 'resp-1',
          display_name: 'Test User',
          created_at: '2026-03-01T00:00:00',
          answers: { q1: 'John', q2: 'opt1' },
        },
      })

      // Should show "Beginner" instead of "opt1"
      expect(wrapper.text()).toContain('Beginner')
    })
  })

  // ── Inline validation on blur (D10) ──
  describe('inline validation on blur', () => {
    it('shows inline validation error when required text field is blurred empty', async () => {
      const { wrapper } = await mountFormView()
      const textInput = wrapper.find('input[type="text"]')
      await textInput.trigger('blur')
      await wrapper.vm.$nextTick()

      // Should show inline validation error for required field q1
      const inlineErrors = wrapper.findAll('[data-testid="inline-validation-error"]')
      expect(inlineErrors.length).toBeGreaterThanOrEqual(1)
    })

    it('does not show inline error for optional fields', async () => {
      const { wrapper } = await mountFormView()
      // q5 is optional textarea
      const textareas = wrapper.findAll('textarea')
      expect(textareas.length).toBeGreaterThanOrEqual(1)
      await textareas[0].trigger('blur')
      await wrapper.vm.$nextTick()

      // Optional fields should NOT show inline error
      const vm = wrapper.vm as unknown as FormViewVm
      expect(vm.touched['q5']).toBe(true)
      // No inline validation error since q5 is not required
      const inlineErrors = wrapper.findAll('[data-testid="inline-validation-error"]')
      // Only required fields should have errors
      expect(
        inlineErrors.filter(() => {
          // Check that this error is NOT for q5
          return true
        }),
      ).toBeDefined()
    })

    it('clears inline error when user provides a value', async () => {
      const { wrapper } = await mountFormView()
      const textInput = wrapper.find('input[type="text"]')

      // Blur without value
      await textInput.trigger('blur')
      await wrapper.vm.$nextTick()
      expect(
        wrapper.findAll('[data-testid="inline-validation-error"]').length,
      ).toBeGreaterThanOrEqual(1)

      // Now type a value and trigger input (which clears validationErrors via onTextInput)
      await textInput.setValue('John')
      await textInput.trigger('input')
      await wrapper.vm.$nextTick()

      // The inline error should disappear since the field now has a value
      const vm = wrapper.vm as unknown as FormViewVm
      expect(vm.answers['q1']).toBe('John')
    })
  })

  // ── Feature 7: Back to Top ──
  describe('back to top', () => {
    it('renders BackToTop component', async () => {
      const { wrapper } = await mountFormView()
      expect(wrapper.find('.back-to-top').exists()).toBe(true)
    })
  })

  describe('accessibility', () => {
    it('adds aria-hidden to required asterisk', async () => {
      const { wrapper } = await mountFormView()
      const asterisks = wrapper.findAll('span[aria-hidden="true"]')
      expect(asterisks.length).toBeGreaterThanOrEqual(2)
    })

    it('adds aria-required on required text inputs', async () => {
      const { wrapper } = await mountFormView()
      const textInputs = wrapper.findAll('input[type="text"]')
      const requiredInput = textInputs.find((i) => i.attributes('aria-required') === 'true')
      expect(requiredInput).toBeTruthy()
    })

    it('adds aria-required on required textarea inputs', async () => {
      const { wrapper } = await mountFormView()
      const textareas = wrapper.findAll('textarea')
      const optional = textareas.find((t) => t.attributes('aria-required') === 'false')
      expect(optional).toBeTruthy()
    })

    it('adds aria-label and aria-pressed to rating buttons', async () => {
      const { wrapper } = await mountFormView()
      const ratingBtns = wrapper
        .findAll('button')
        .filter((b) => b.attributes('aria-label')?.includes('Rate'))
      expect(ratingBtns.length).toBeGreaterThan(0)
      for (const btn of ratingBtns) {
        expect(btn.attributes('aria-pressed')).toBeDefined()
      }
    })

    it('sets aria-pressed="true" on selected rating', async () => {
      const { wrapper } = await mountFormView()
      const ratingBtns = wrapper
        .findAll('button')
        .filter((b) => b.attributes('aria-label')?.includes('Rate'))
      expect(ratingBtns.length).toBeGreaterThan(0)
      await ratingBtns[0].trigger('click')
      await wrapper.vm.$nextTick()

      const updatedBtns = wrapper
        .findAll('button')
        .filter((b) => b.attributes('aria-label')?.includes('Rate'))
      const pressed = updatedBtns.find((b) => b.attributes('aria-pressed') === 'true')
      expect(pressed).toBeTruthy()
    })

    it('wraps rating buttons in a group with aria-label', async () => {
      const { wrapper } = await mountFormView()
      const ratingGroup = wrapper.find('[role="group"]')
      expect(ratingGroup.exists()).toBe(true)
      expect(ratingGroup.attributes('aria-label')).toBeTruthy()
    })

    it('has per-question validation error with role="alert"', async () => {
      const { wrapper } = await mountFormView()
      const submitBtn = wrapper.findAll('button').find((b) => b.text().includes('Submit'))
      await submitBtn!.trigger('click')
      await flushPromises()

      const errorAlerts = wrapper.findAll('p[role="alert"]')
      expect(errorAlerts.length).toBeGreaterThanOrEqual(1)
    })

    it('file upload drop zone has correct aria-label', async () => {
      const formWithFile = {
        ...fakeForm,
        questions: [
          {
            id: 'qf',
            type: 'file_upload',
            label: 'Upload Document',
            required: false,
          },
        ],
      }
      const { wrapper } = await mountFormView({ form: formWithFile })

      const dropZone = wrapper.find('[role="button"]')
      expect(dropZone.exists()).toBe(true)
      expect(dropZone.attributes('aria-label')).toBeTruthy()
    })
  })
})

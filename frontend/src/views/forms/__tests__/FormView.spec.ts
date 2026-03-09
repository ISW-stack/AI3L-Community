import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import FormView from '../FormView.vue'
import { useAuthStore } from '@/stores/auth'

const mockGetForm = vi.fn()
const mockSubmitForm = vi.fn()
const mockExportForm = vi.fn()
const mockGetTaskStatus = vi.fn()
const mockUploadEditorFile = vi.fn()

vi.mock('@/api/forms', () => ({
  getForm: (...args: unknown[]) => mockGetForm(...args),
  submitForm: (...args: unknown[]) => mockSubmitForm(...args),
  exportForm: (...args: unknown[]) => mockExportForm(...args),
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
    BaseAlert: { template: '<div class="base-alert"><slot /></div>', props: ['type'] },
    BaseBadge: { template: '<span class="base-badge"><slot /></span>', props: ['variant'] },
    SkeletonLoader: { template: '<div class="skeleton-loader" />', props: ['lines', 'variant'] },
    CopyShareLinkButton: { template: '<span class="copy-share-link" />', props: ['url'] },
  }
}

async function mountFormView(options?: { role?: string; form?: typeof fakeForm | null }) {
  const { role = 'MEMBER', form = fakeForm } = options ?? {}
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
  } as any

  if (form) {
    mockGetForm.mockResolvedValue(form)
  } else {
    mockGetForm.mockRejectedValue(new Error('Not found'))
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
    // Rating buttons 1-5
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
    // Submit without filling required fields
    const submitBtn = wrapper.findAll('button').find((b) => b.text().includes('Submit'))
    expect(submitBtn).toBeTruthy()
    await submitBtn!.trigger('click')
    await flushPromises()

    // Should show validation error
    expect(wrapper.text()).toContain('"Your Name"')
    expect(mockSubmitForm).not.toHaveBeenCalled()
  })

  it('submits form successfully', async () => {
    const { wrapper } = await mountFormView()
    const vm = wrapper.vm as any

    // Fill required fields
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
    const vm = wrapper.vm as any
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
    const vm = wrapper.vm as any
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
    auth.user = { id: 'u2' } as any

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
})

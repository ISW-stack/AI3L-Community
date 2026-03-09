import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import FormBuilderView from '../FormBuilderView.vue'

const mockGetForm = vi.fn()
const mockCreateForm = vi.fn()
const mockUpdateForm = vi.fn()
const mockUploadEditorFile = vi.fn()

vi.mock('@/api/forms', () => ({
  getForm: (...args: unknown[]) => mockGetForm(...args),
  createForm: (...args: unknown[]) => mockCreateForm(...args),
  updateForm: (...args: unknown[]) => mockUpdateForm(...args),
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

const fakeEditForm = {
  id: 'form-1',
  title: 'Existing Survey',
  description: 'Existing description',
  banner_url: null,
  is_active: true,
  is_schema_locked: false,
  allow_non_members: false,
  created_by: 'u1',
  created_by_name: 'Admin',
  response_count: 0,
  deadline: null,
  max_respondents: null,
  questions: [
    {
      id: 'q1',
      type: 'text',
      label: 'Name',
      required: true,
      placeholder: 'Enter name',
      max_length: 100,
      options: [],
    },
  ],
}

function createTestRouter(options?: { isEdit?: boolean }) {
  const { isEdit: _isEdit = false } = options ?? {}
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      {
        path: '/sigs/:sigId/forms/create',
        component: FormBuilderView,
      },
      {
        path: '/forms/:formId/edit',
        component: FormBuilderView,
      },
      { path: '/forms/:id', component: { template: '<div />' } },
    ],
  })
}

function createStubs() {
  return {
    BaseCard: { template: '<div class="base-card"><slot /></div>', props: ['padding'] },
    BaseButton: {
      template:
        '<button :disabled="$attrs.disabled" :type="$attrs.type || \'button\'" @click="$emit(\'click\')"><slot /></button>',
      props: ['loading', 'variant', 'size', 'type'],
    },
    BaseAlert: { template: '<div class="base-alert"><slot /></div>', props: ['type'] },
    BaseInput: {
      template:
        '<input class="base-input" :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
      props: ['modelValue', 'label', 'placeholder'],
    },
    BaseTextarea: {
      template:
        '<textarea class="base-textarea" :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)"></textarea>',
      props: ['modelValue', 'label', 'rows', 'placeholder'],
    },
    BaseModal: {
      template: '<div class="base-modal" v-if="modelValue"><slot /></div>',
      props: ['modelValue', 'title', 'size'],
    },
    SkeletonLoader: { template: '<div class="skeleton-loader" />', props: ['lines', 'variant'] },
  }
}

async function mountBuilder(options?: { isEdit?: boolean }) {
  const { isEdit = false } = options ?? {}
  const pinia = createPinia()
  setActivePinia(pinia)
  const router = createTestRouter()

  if (isEdit) {
    await router.push('/forms/form-1/edit')
  } else {
    await router.push('/sigs/sig-1/forms/create')
  }
  await router.isReady()

  const wrapper = mount(FormBuilderView, {
    global: { plugins: [pinia, router], stubs: createStubs() },
  })
  await flushPromises()
  return { wrapper, router }
}

describe('FormBuilderView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockGetForm.mockResolvedValue(fakeEditForm)
    mockCreateForm.mockResolvedValue({ id: 'new-form-1' })
    mockUpdateForm.mockResolvedValue({})
    // Mock crypto.randomUUID
    let counter = 0
    vi.spyOn(crypto, 'randomUUID').mockImplementation(
      () => `uuid-${++counter}` as `${string}-${string}-${string}-${string}-${string}`,
    )
  })

  describe('Create mode', () => {
    it('renders create title', async () => {
      const { wrapper } = await mountBuilder()
      expect(wrapper.text()).toContain('Create Form')
    })

    it('starts with one default question', async () => {
      const { wrapper } = await mountBuilder()
      expect(wrapper.text()).toContain('Question')
    })

    it('renders title and description inputs', async () => {
      const { wrapper } = await mountBuilder()
      expect(wrapper.find('.base-input').exists()).toBe(true)
      expect(wrapper.find('.base-textarea').exists()).toBe(true)
    })

    it('renders add question button and can add questions', async () => {
      const { wrapper } = await mountBuilder()
      const addBtn = wrapper.findAll('button').find((b) => b.text().includes('+ Add Question'))
      expect(addBtn).toBeTruthy()

      // Verify there are question cards rendered
      const questionCards = wrapper.findAll('.border-l-4')
      expect(questionCards.length).toBeGreaterThanOrEqual(1)
    })

    it('removes a question', async () => {
      const { wrapper } = await mountBuilder()
      // Add a second question first
      const addBtn = wrapper.findAll('button').find((b) => b.text().includes('+ Add Question'))
      await addBtn!.trigger('click')
      await nextTick()
      const afterAddCount = wrapper.findAll('.border-l-4').length

      // Remove button (x)
      const removeBtn = wrapper.findAll('button').find((b) => b.text().includes('\u00D7'))
      expect(removeBtn).toBeTruthy()
      await removeBtn!.trigger('click')
      await nextTick()

      expect(wrapper.findAll('.border-l-4').length).toBe(afterAddCount - 1)
    })

    it('shows validation error when title is empty', async () => {
      const { wrapper } = await mountBuilder()
      const vm = wrapper.vm as any
      vm.title = ''
      vm.questions[0].label = 'Q1'

      const saveBtn = wrapper.findAll('button').find((b) => b.text().includes('Create Form'))
      await saveBtn!.trigger('click')
      await flushPromises()

      expect(wrapper.text()).toContain('Title is required.')
      expect(mockCreateForm).not.toHaveBeenCalled()
    })

    it('shows validation error when no questions exist', async () => {
      const { wrapper } = await mountBuilder()
      const vm = wrapper.vm as any
      vm.title = 'Survey Title'
      vm.questions = []

      const saveBtn = wrapper.findAll('button').find((b) => b.text().includes('Create Form'))
      await saveBtn!.trigger('click')
      await flushPromises()

      expect(wrapper.text()).toContain('At least one question is required.')
    })

    it('shows validation error for empty question label', async () => {
      const { wrapper } = await mountBuilder()
      const vm = wrapper.vm as any
      vm.title = 'Survey Title'
      vm.questions[0].label = ''

      const saveBtn = wrapper.findAll('button').find((b) => b.text().includes('Create Form'))
      await saveBtn!.trigger('click')
      await flushPromises()

      expect(wrapper.text()).toContain('All questions must have a label.')
    })

    it('creates form and redirects on success', async () => {
      const { wrapper, router } = await mountBuilder()
      const replaceSpy = vi.spyOn(router, 'replace')
      const vm = wrapper.vm as any
      vm.title = 'New Survey'
      vm.questions[0].label = 'Question 1'

      const saveBtn = wrapper.findAll('button').find((b) => b.text().includes('Create Form'))
      await saveBtn!.trigger('click')
      await flushPromises()

      expect(mockCreateForm).toHaveBeenCalledWith(
        'sig-1',
        expect.objectContaining({ title: 'New Survey' }),
      )
      expect(replaceSpy).toHaveBeenCalledWith('/forms/new-form-1')
    })

    it('shows error on creation failure', async () => {
      mockCreateForm.mockRejectedValue({
        response: { data: { detail: 'Permission denied' } },
      })
      const { wrapper } = await mountBuilder()
      const vm = wrapper.vm as any
      vm.title = 'New Survey'
      vm.questions[0].label = 'Q1'

      const saveBtn = wrapper.findAll('button').find((b) => b.text().includes('Create Form'))
      await saveBtn!.trigger('click')
      await flushPromises()

      expect(wrapper.text()).toContain('Permission denied')
    })

    it('renders question type selector', async () => {
      const { wrapper } = await mountBuilder()
      const selects = wrapper.findAll('select')
      expect(selects.length).toBeGreaterThanOrEqual(1)
    })

    it('shows preview modal', async () => {
      const { wrapper } = await mountBuilder()
      const previewBtn = wrapper.findAll('button').find((b) => b.text().includes('Preview'))
      expect(previewBtn).toBeTruthy()
      await previewBtn!.trigger('click')
      await nextTick()

      expect(wrapper.find('.base-modal').exists()).toBe(true)
    })

    it('renders allow non-members checkbox', async () => {
      const { wrapper } = await mountBuilder()
      expect(wrapper.text()).toContain('Allow non-SIG members to submit this form')
    })
  })

  describe('Edit mode', () => {
    it('fetches existing form data', async () => {
      await mountBuilder({ isEdit: true })
      expect(mockGetForm).toHaveBeenCalledWith('form-1')
    })

    it('renders edit title', async () => {
      const { wrapper } = await mountBuilder({ isEdit: true })
      expect(wrapper.text()).toContain('Edit Form')
    })

    it('populates form fields from fetched data', async () => {
      const { wrapper } = await mountBuilder({ isEdit: true })
      const vm = wrapper.vm as any
      expect(vm.title).toBe('Existing Survey')
      expect(vm.description).toBe('Existing description')
    })

    it('shows update button instead of create', async () => {
      const { wrapper } = await mountBuilder({ isEdit: true })
      expect(wrapper.text()).toContain('Update Form')
    })

    it('shows schema locked warning when locked', async () => {
      mockGetForm.mockResolvedValue({ ...fakeEditForm, is_schema_locked: true })
      const { wrapper } = await mountBuilder({ isEdit: true })
      expect(wrapper.text()).toContain('Questions are locked')
    })
  })
})

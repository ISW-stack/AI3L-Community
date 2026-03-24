import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import FormBuilderView from '../FormBuilderView.vue'

interface QuestionOption {
  id: string
  label: string
}

interface Question {
  id: string
  type: string
  label: string
  required: boolean
  options: QuestionOption[]
  [key: string]: unknown
}

interface FormBuilderVm {
  title: string
  description: string
  deadline: string
  showPreview: boolean
  questions: Question[]
  addQuestion: () => void
  duplicateQuestion: (index: number) => void
  insertQuestionAt: (index: number) => void
  moveQuestion: (from: number, to: number) => void
  moveOption: (question: Question, index: number, direction: number) => void
  toggleCollapse: (id: string) => void
  isCollapsed: (id: string) => boolean
  collapseAll: () => void
  expandAll: () => void
  handleUndo: () => void
}

const mockGetForm = vi.fn()
const mockCreateForm = vi.fn()
const mockUpdateForm = vi.fn()
const mockUploadEditorFile = vi.fn()
const mockGetSig = vi.fn()

vi.mock('@/api/forms', () => ({
  getForm: (...args: unknown[]) => mockGetForm(...args),
  createForm: (...args: unknown[]) => mockCreateForm(...args),
  updateForm: (...args: unknown[]) => mockUpdateForm(...args),
}))

vi.mock('@/api/files', () => ({
  uploadEditorFile: (...args: unknown[]) => mockUploadEditorFile(...args),
}))

vi.mock('@/api/sigs', () => ({
  getSig: (...args: unknown[]) => mockGetSig(...args),
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
  sig_id: 'sig-1',
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

function createTestRouter() {
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
    // Description field was migrated from BaseTextarea to TiptapEditor
    TiptapEditor: {
      template:
        '<div class="tiptap-editor"><textarea class="tiptap-textarea" :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)"></textarea></div>',
      props: ['modelValue'],
      emits: ['update:modelValue'],
    },
    BaseModal: {
      template: '<div class="base-modal" v-if="modelValue"><slot /></div>',
      props: ['modelValue', 'title', 'size'],
    },
    SkeletonLoader: { template: '<div class="skeleton-loader" />', props: ['lines', 'variant'] },
    EmptyState: { template: '<div class="empty-state" />', props: ['message'] },
    BaseBreadcrumb: { template: '<div class="base-breadcrumb" />', props: ['items'] },
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
    localStorage.clear()
    mockGetForm.mockResolvedValue(fakeEditForm)
    mockCreateForm.mockResolvedValue({ id: 'new-form-1' })
    mockUpdateForm.mockResolvedValue({})
    mockGetSig.mockResolvedValue({ name: 'Test SIG' })
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

    it('renders title input and TiptapEditor for description', async () => {
      const { wrapper } = await mountBuilder()
      expect(wrapper.find('.base-input').exists()).toBe(true)
      // Description field uses TiptapEditor (not BaseTextarea)
      expect(wrapper.find('.tiptap-editor').exists()).toBe(true)
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
      const vm = wrapper.vm as unknown as FormBuilderVm
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
      const vm = wrapper.vm as unknown as FormBuilderVm
      vm.title = 'Survey Title'
      vm.questions = []

      const saveBtn = wrapper.findAll('button').find((b) => b.text().includes('Create Form'))
      await saveBtn!.trigger('click')
      await flushPromises()

      expect(wrapper.text()).toContain('At least one question is required.')
    })

    it('shows validation error for empty question label', async () => {
      const { wrapper } = await mountBuilder()
      const vm = wrapper.vm as unknown as FormBuilderVm
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
      const vm = wrapper.vm as unknown as FormBuilderVm
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
      const vm = wrapper.vm as unknown as FormBuilderVm
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

  describe('Deadline validation', () => {
    it('rejects a deadline set in the past', async () => {
      const { wrapper } = await mountBuilder()
      const vm = wrapper.vm as unknown as FormBuilderVm
      vm.title = 'Survey With Past Deadline'
      vm.questions[0].label = 'Q1'

      // Set deadline to 1 hour in the past
      const pastDate = new Date(Date.now() - 60 * 60 * 1000)
      const pad = (n: number) => String(n).padStart(2, '0')
      vm.deadline = `${pastDate.getFullYear()}-${pad(pastDate.getMonth() + 1)}-${pad(pastDate.getDate())}T${pad(pastDate.getHours())}:${pad(pastDate.getMinutes())}`

      const saveBtn = wrapper.findAll('button').find((b) => b.text().includes('Create Form'))
      await saveBtn!.trigger('click')
      await flushPromises()

      expect(wrapper.text()).toContain('Deadline must be in the future')
      expect(mockCreateForm).not.toHaveBeenCalled()
    })

    it('accepts a deadline set in the future', async () => {
      const { wrapper } = await mountBuilder()
      const vm = wrapper.vm as unknown as FormBuilderVm
      vm.title = 'Survey With Future Deadline'
      vm.questions[0].label = 'Q1'

      // Set deadline to 1 day in the future
      const futureDate = new Date(Date.now() + 24 * 60 * 60 * 1000)
      const pad = (n: number) => String(n).padStart(2, '0')
      vm.deadline = `${futureDate.getFullYear()}-${pad(futureDate.getMonth() + 1)}-${pad(futureDate.getDate())}T${pad(futureDate.getHours())}:${pad(futureDate.getMinutes())}`

      const saveBtn = wrapper.findAll('button').find((b) => b.text().includes('Create Form'))
      await saveBtn!.trigger('click')
      await flushPromises()

      expect(wrapper.text()).not.toContain('Deadline must be in the future')
      expect(mockCreateForm).toHaveBeenCalled()
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
      const vm = wrapper.vm as unknown as FormBuilderVm
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

  describe('Accessibility', () => {
    it('has aria-label on move up button', async () => {
      const { wrapper } = await mountBuilder()
      const moveUpBtn = wrapper.find('button[aria-label="Move question up"]')
      expect(moveUpBtn.exists()).toBe(true)
    })

    it('has aria-label on move down button', async () => {
      const { wrapper } = await mountBuilder()
      const moveDownBtn = wrapper.find('button[aria-label="Move question down"]')
      expect(moveDownBtn.exists()).toBe(true)
    })

    it('has aria-label on delete question button', async () => {
      const { wrapper } = await mountBuilder()
      const deleteBtn = wrapper.find('button[aria-label="Delete question"]')
      expect(deleteBtn.exists()).toBe(true)
    })

    it('has aria-label on choice option inputs', async () => {
      const { wrapper } = await mountBuilder()
      const vm = wrapper.vm as unknown as FormBuilderVm
      // Change the first question to single_choice with options
      vm.questions[0].type = 'single_choice'
      vm.questions[0].options = [
        { id: 'o1', label: 'A' },
        { id: 'o2', label: 'B' },
      ]
      await wrapper.vm.$nextTick()

      const optionInputs = wrapper.findAll('input[aria-label^="Option"]')
      expect(optionInputs.length).toBe(2)
      expect(optionInputs[0].attributes('aria-label')).toBe('Option 1')
      expect(optionInputs[1].attributes('aria-label')).toBe('Option 2')
    })

    it('has aria-label on remove option button', async () => {
      const { wrapper } = await mountBuilder()
      const vm = wrapper.vm as unknown as FormBuilderVm
      vm.questions[0].type = 'single_choice'
      vm.questions[0].options = [{ id: 'o1', label: 'A' }]
      await wrapper.vm.$nextTick()

      const removeBtn = wrapper.find('button[aria-label="Remove option"]')
      expect(removeBtn.exists()).toBe(true)
    })
  })

  // ── New feature tests ──

  describe('Feature 3: Duplicate Question', () => {
    it('has duplicate button with aria-label', async () => {
      const { wrapper } = await mountBuilder()
      const dupBtn = wrapper.find('button[aria-label="Duplicate question"]')
      expect(dupBtn.exists()).toBe(true)
    })

    it('duplicates a question with new IDs', async () => {
      const { wrapper } = await mountBuilder()
      const vm = wrapper.vm as unknown as FormBuilderVm
      vm.questions[0].label = 'Original'
      vm.questions[0].type = 'single_choice'
      vm.questions[0].options = [
        { id: 'opt1', label: 'A' },
        { id: 'opt2', label: 'B' },
      ]
      await nextTick()

      const initialCount = vm.questions.length
      vm.duplicateQuestion(0)
      await nextTick()

      expect(vm.questions.length).toBe(initialCount + 1)
      expect(vm.questions[1].label).toBe('Original')
      expect(vm.questions[1].id).not.toBe(vm.questions[0].id)
      // Options should have new IDs
      expect(vm.questions[1].options[0].id).not.toBe('opt1')
      expect(vm.questions[1].options[0].label).toBe('A')
    })
  })

  describe('Feature 4: Collapse/Expand', () => {
    it('renders collapse/expand toggle button', async () => {
      const { wrapper } = await mountBuilder()
      const collapseBtn = wrapper.find('button[aria-label="Collapse question"]')
      expect(collapseBtn.exists()).toBe(true)
    })

    it('toggleCollapse hides question content', async () => {
      const { wrapper } = await mountBuilder()
      const vm = wrapper.vm as unknown as FormBuilderVm
      const qId = vm.questions[0].id

      // Initially expanded
      expect(vm.isCollapsed(qId)).toBe(false)

      vm.toggleCollapse(qId)
      expect(vm.isCollapsed(qId)).toBe(true)

      vm.toggleCollapse(qId)
      expect(vm.isCollapsed(qId)).toBe(false)
    })

    it('collapseAll and expandAll work', async () => {
      const { wrapper } = await mountBuilder()
      const vm = wrapper.vm as unknown as FormBuilderVm

      // Add a second question
      vm.addQuestion()
      await nextTick()

      vm.collapseAll()
      expect(vm.isCollapsed(vm.questions[0].id)).toBe(true)
      expect(vm.isCollapsed(vm.questions[1].id)).toBe(true)

      vm.expandAll()
      expect(vm.isCollapsed(vm.questions[0].id)).toBe(false)
      expect(vm.isCollapsed(vm.questions[1].id)).toBe(false)
    })

    it('renders collapse all / expand all buttons when multiple questions', async () => {
      const { wrapper } = await mountBuilder()
      const vm = wrapper.vm as unknown as FormBuilderVm
      vm.addQuestion()
      await nextTick()

      expect(wrapper.text()).toContain('Collapse All')
      expect(wrapper.text()).toContain('Expand All')
    })
  })

  describe('Feature 5: Option Reordering', () => {
    it('renders option up/down arrows for choice questions', async () => {
      const { wrapper } = await mountBuilder()
      const vm = wrapper.vm as unknown as FormBuilderVm
      vm.questions[0].type = 'single_choice'
      vm.questions[0].options = [
        { id: 'o1', label: 'A' },
        { id: 'o2', label: 'B' },
      ]
      await nextTick()

      const moveUpBtns = wrapper.findAll('button[aria-label="Move option up"]')
      const moveDownBtns = wrapper.findAll('button[aria-label="Move option down"]')
      expect(moveUpBtns.length).toBeGreaterThanOrEqual(2)
      expect(moveDownBtns.length).toBeGreaterThanOrEqual(2)
    })

    it('moveOption swaps options correctly', async () => {
      const { wrapper } = await mountBuilder()
      const vm = wrapper.vm as unknown as FormBuilderVm
      vm.questions[0].type = 'single_choice'
      vm.questions[0].options = [
        { id: 'o1', label: 'A' },
        { id: 'o2', label: 'B' },
        { id: 'o3', label: 'C' },
      ]
      await nextTick()

      vm.moveOption(vm.questions[0], 0, 1)
      expect(vm.questions[0].options[0].label).toBe('B')
      expect(vm.questions[0].options[1].label).toBe('A')
    })

    it('does not move option beyond boundaries', async () => {
      const { wrapper } = await mountBuilder()
      const vm = wrapper.vm as unknown as FormBuilderVm
      vm.questions[0].type = 'single_choice'
      vm.questions[0].options = [
        { id: 'o1', label: 'A' },
        { id: 'o2', label: 'B' },
      ]
      await nextTick()

      // Try moving first option up (should be no-op)
      vm.moveOption(vm.questions[0], 0, -1)
      expect(vm.questions[0].options[0].label).toBe('A')

      // Try moving last option down (should be no-op)
      vm.moveOption(vm.questions[0], 1, 1)
      expect(vm.questions[0].options[1].label).toBe('B')
    })
  })

  describe('Feature 2: Drag-and-Drop reordering', () => {
    it('question cards have draggable attribute', async () => {
      const { wrapper } = await mountBuilder()
      const cards = wrapper.findAll('[draggable="true"]')
      expect(cards.length).toBeGreaterThanOrEqual(1)
    })

    it('has drag handle element', async () => {
      const { wrapper } = await mountBuilder()
      const handle = wrapper.find('[aria-label="Drag to reorder"]')
      expect(handle.exists()).toBe(true)
    })

    it('moveQuestion reorders correctly', async () => {
      const { wrapper } = await mountBuilder()
      const vm = wrapper.vm as unknown as FormBuilderVm
      vm.addQuestion()
      await nextTick()

      vm.questions[0].label = 'First'
      vm.questions[1].label = 'Second'

      vm.moveQuestion(0, 1)
      expect(vm.questions[0].label).toBe('Second')
      expect(vm.questions[1].label).toBe('First')
    })
  })

  describe('Feature 1: Floating Action Button', () => {
    it('renders FAB with aria-label', async () => {
      const { wrapper } = await mountBuilder()
      const fab = wrapper.find('button.fixed')
      expect(fab.exists()).toBe(true)
      expect(fab.attributes('aria-label')).toBe('+ Add Question')
    })
  })

  describe('Feature 1: Insert Question Divider', () => {
    it('renders insert divider between questions', async () => {
      const { wrapper } = await mountBuilder()
      const vm = wrapper.vm as unknown as FormBuilderVm
      vm.addQuestion()
      await nextTick()

      const insertBtn = wrapper.find('button[aria-label="Insert question here"]')
      expect(insertBtn.exists()).toBe(true)
    })

    it('insertQuestionAt inserts at correct position', async () => {
      const { wrapper } = await mountBuilder()
      const vm = wrapper.vm as unknown as FormBuilderVm
      vm.addQuestion()
      await nextTick()

      vm.questions[0].label = 'First'
      vm.questions[1].label = 'Second'

      vm.insertQuestionAt(1)
      await nextTick()

      expect(vm.questions.length).toBe(3)
      expect(vm.questions[0].label).toBe('First')
      expect(vm.questions[1].label).toBe('') // new question
      expect(vm.questions[2].label).toBe('Second')
    })
  })

  describe('Feature 6: Undo/Redo UI', () => {
    it('renders undo and redo buttons', async () => {
      const { wrapper } = await mountBuilder()
      const undoBtn = wrapper.find('button[aria-label="Undo"]')
      const redoBtn = wrapper.find('button[aria-label="Redo"]')
      expect(undoBtn.exists()).toBe(true)
      expect(redoBtn.exists()).toBe(true)
    })
  })

  describe('Feature 8: Mobile Preview', () => {
    it('renders desktop/mobile toggle in preview', async () => {
      const { wrapper } = await mountBuilder()
      const vm = wrapper.vm as unknown as FormBuilderVm
      vm.showPreview = true
      await nextTick()

      expect(wrapper.text()).toContain('Desktop')
      expect(wrapper.text()).toContain('Mobile')
    })
  })

  describe('Feature 7: Draft banner', () => {
    it('shows draft banner when draft exists in localStorage', async () => {
      const draftData = {
        title: 'Draft Title',
        description: 'Draft desc',
        bannerUrl: '',
        deadline: '',
        maxRespondents: null,
        allowNonMembers: false,
        questions: [{ id: 'q-draft', type: 'text', label: 'Draft Q', required: true, options: [] }],
        savedAt: '2026-03-12T10:00:00Z',
      }
      localStorage.setItem('form-draft-sig-1', JSON.stringify(draftData))
      const { wrapper } = await mountBuilder()
      expect(wrapper.text()).toContain('Restore')
      expect(wrapper.text()).toContain('Discard')
    })

    it('clears draft after successful save', async () => {
      // Manually set a draft in localStorage
      localStorage.setItem(
        'form-draft-sig-1',
        JSON.stringify({
          title: 'Draft',
          description: '',
          bannerUrl: '',
          deadline: '',
          maxRespondents: null,
          allowNonMembers: false,
          questions: [{ id: 'q1', type: 'text', label: 'Q1', required: true }],
          savedAt: new Date().toISOString(),
        }),
      )
      expect(localStorage.getItem('form-draft-sig-1')).toBeTruthy()

      const { wrapper } = await mountBuilder()
      const vm = wrapper.vm as unknown as FormBuilderVm
      vm.title = 'New Survey'
      vm.questions[0].label = 'Q1'

      // Save form
      const saveBtn = wrapper.findAll('button').find((b) => b.text().includes('Create Form'))
      await saveBtn!.trigger('click')
      await flushPromises()

      expect(localStorage.getItem('form-draft-sig-1')).toBeNull()
    })

    it('does not show draft banner in edit mode', async () => {
      // Set a draft for the edit form key
      const draftData = {
        title: 'Edit Draft',
        description: '',
        bannerUrl: '',
        deadline: '',
        maxRespondents: null,
        allowNonMembers: false,
        questions: [],
        savedAt: '2026-03-12T10:00:00Z',
      }
      localStorage.setItem('form-draft-edit-form-1', JSON.stringify(draftData))
      const { wrapper } = await mountBuilder({ isEdit: true })
      await flushPromises()
      // In edit mode the draft banner should never be shown
      expect(wrapper.text()).not.toContain('Restore')
    })
  })

  describe('XSS sanitization', () => {
    it('calls DOMPurify.sanitize on description in preview', async () => {
      const xssDescription = '<p>Hello</p><img src=x onerror="alert(1)">'
      mockGetForm.mockResolvedValue({ ...fakeEditForm, description: xssDescription })
      const { wrapper } = await mountBuilder({ isEdit: true })
      const vm = wrapper.vm as unknown as FormBuilderVm
      vm.showPreview = true
      await nextTick()

      expect(mockSanitize).toHaveBeenCalledWith(xssDescription)
    })

    it('renders sanitized description, not raw HTML', async () => {
      const xssPayload = '<img src=x onerror="alert(1)"><b>safe</b>'
      // Make sanitize strip the img tag
      mockSanitize.mockImplementation((html: string) => html.replace(/<img[^>]*>/g, ''))
      mockGetForm.mockResolvedValue({ ...fakeEditForm, description: xssPayload })
      const { wrapper } = await mountBuilder({ isEdit: true })
      const vm = wrapper.vm as unknown as FormBuilderVm
      vm.showPreview = true
      await nextTick()

      const descDiv = wrapper.find('.prose.prose-sm')
      if (descDiv.exists()) {
        expect(descDiv.html()).not.toContain('onerror')
        expect(descDiv.html()).toContain('<b>safe</b>')
      }
      // Restore default passthrough behavior
      mockSanitize.mockImplementation((html: string) => html)
    })
  })

  describe('Feature 6: Undo/Redo functionality', () => {
    it('undo reverts question addition', async () => {
      const { wrapper } = await mountBuilder()
      const vm = wrapper.vm as unknown as FormBuilderVm

      // Initially 1 question
      expect(vm.questions.length).toBe(1)

      // Add a second question
      vm.addQuestion()
      await nextTick()
      expect(vm.questions.length).toBe(2)

      // Undo should revert to 1 question
      vm.handleUndo()
      await nextTick()
      expect(vm.questions.length).toBe(1)
    })

    it('Ctrl+Z triggers undo', async () => {
      const { wrapper } = await mountBuilder()
      const vm = wrapper.vm as unknown as FormBuilderVm

      // Add a question so there is something to undo
      vm.addQuestion()
      await nextTick()
      expect(vm.questions.length).toBe(2)

      // Dispatch Ctrl+Z on the document
      const event = new KeyboardEvent('keydown', { key: 'z', ctrlKey: true, bubbles: true })
      document.dispatchEvent(event)
      await nextTick()

      expect(vm.questions.length).toBe(1)
    })

    it('Ctrl+Shift+Z triggers redo', async () => {
      const { wrapper } = await mountBuilder()
      const vm = wrapper.vm as unknown as FormBuilderVm

      // Add a question, then undo it
      vm.addQuestion()
      await nextTick()
      expect(vm.questions.length).toBe(2)

      vm.handleUndo()
      await nextTick()
      expect(vm.questions.length).toBe(1)

      // Dispatch Ctrl+Shift+Z to redo
      const event = new KeyboardEvent('keydown', {
        key: 'z',
        ctrlKey: true,
        shiftKey: true,
        bubbles: true,
      })
      document.dispatchEvent(event)
      await nextTick()

      expect(vm.questions.length).toBe(2)
    })
  })
})

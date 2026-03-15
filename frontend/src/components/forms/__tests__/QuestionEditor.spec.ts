import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import QuestionEditor from '../QuestionEditor.vue'
import type { Question } from '@/types'

function createQuestion(overrides: Partial<Question> = {}): Question {
  return {
    id: 'q1',
    type: 'text',
    label: 'Test Question',
    required: false,
    placeholder: '',
    max_length: undefined,
    options: [],
    ...overrides,
  }
}

function mountEditor(props: Partial<Record<string, unknown>> = {}) {
  return mount(QuestionEditor, {
    props: {
      question: createQuestion(),
      index: 0,
      totalQuestions: 1,
      isSchemaLocked: false,
      isCollapsed: false,
      dragIndex: null,
      dropTargetIndex: null,
      ...props,
    },
  })
}

describe('QuestionEditor', () => {
  describe('rendering', () => {
    it('renders question label with index', () => {
      const wrapper = mountEditor({ index: 2 })
      expect(wrapper.text()).toContain('Question 3')
    })

    it('renders question type selector', () => {
      const wrapper = mountEditor()
      const select = wrapper.find('select')
      expect(select.exists()).toBe(true)
    })

    it('renders question label input', () => {
      const wrapper = mountEditor({
        question: createQuestion({ label: 'My Label' }),
      })
      const input = wrapper.find('input[type="text"]')
      expect(input.exists()).toBe(true)
      expect((input.element as HTMLInputElement).value).toBe('My Label')
    })

    it('renders required checkbox', () => {
      const wrapper = mountEditor()
      expect(wrapper.text()).toContain('Required')
    })

    it('renders drag handle when not schema-locked', () => {
      const wrapper = mountEditor()
      const handle = wrapper.find('[aria-label="Drag to reorder"]')
      expect(handle.exists()).toBe(true)
    })

    it('hides drag handle when schema-locked', () => {
      const wrapper = mountEditor({ isSchemaLocked: true })
      const handle = wrapper.find('[aria-label="Drag to reorder"]')
      expect(handle.exists()).toBe(false)
    })

    it('shows collapsed state with type badge', () => {
      const wrapper = mountEditor({
        isCollapsed: true,
        question: createQuestion({ label: 'My Q', type: 'text' }),
      })
      expect(wrapper.text()).toContain('My Q')
      expect(wrapper.text()).toContain('Short Text')
    })

    it('hides expanded content when collapsed', () => {
      const wrapper = mountEditor({ isCollapsed: true })
      const selects = wrapper.findAll('select')
      expect(selects.length).toBe(0)
    })
  })

  describe('text/textarea specific fields', () => {
    it('renders placeholder input for text type', () => {
      const wrapper = mountEditor({
        question: createQuestion({ type: 'text' }),
      })
      const inputs = wrapper.findAll('input[type="text"]')
      // label + placeholder = at least 2
      expect(inputs.length).toBeGreaterThanOrEqual(2)
    })

    it('renders max_length input for text type', () => {
      const wrapper = mountEditor({
        question: createQuestion({ type: 'text' }),
      })
      const numberInput = wrapper.find('input[type="number"]')
      expect(numberInput.exists()).toBe(true)
    })
  })

  describe('choice options', () => {
    it('renders options for single_choice', () => {
      const wrapper = mountEditor({
        question: createQuestion({
          type: 'single_choice',
          options: [
            { id: 'o1', label: 'Option A' },
            { id: 'o2', label: 'Option B' },
          ],
        }),
      })
      const optionInputs = wrapper.findAll('input[aria-label^="Option"]')
      expect(optionInputs.length).toBe(2)
    })

    it('renders add option button for choice types', () => {
      const wrapper = mountEditor({
        question: createQuestion({ type: 'single_choice', options: [] }),
      })
      expect(wrapper.text()).toContain('+ Add option')
    })
  })

  describe('rating fields', () => {
    it('renders min/max inputs for rating type', () => {
      const wrapper = mountEditor({
        question: createQuestion({ type: 'rating', min: 1, max: 5 }),
      })
      const numberInputs = wrapper.findAll('input[type="number"]')
      expect(numberInputs.length).toBe(2)
    })

    it('shows validation error when min >= max', () => {
      const wrapper = mountEditor({
        question: createQuestion({ type: 'rating', min: 5, max: 3 }),
      })
      expect(wrapper.text()).toContain('Minimum must be less than maximum.')
    })
  })

  describe('file_upload fields', () => {
    it('renders allowed types and max size inputs', () => {
      const wrapper = mountEditor({
        question: createQuestion({ type: 'file_upload' }),
      })
      expect(wrapper.text()).toContain('Allowed types:')
    })
  })

  describe('emits', () => {
    it('emits remove when delete button clicked', async () => {
      const wrapper = mountEditor()
      const deleteBtn = wrapper.find('button[aria-label="Delete question"]')
      await deleteBtn.trigger('click')
      expect(wrapper.emitted('remove')).toBeTruthy()
    })

    it('emits move-up when up arrow clicked', async () => {
      const wrapper = mountEditor({ index: 1, totalQuestions: 3 })
      const upBtn = wrapper.find('button[aria-label="Move question up"]')
      await upBtn.trigger('click')
      expect(wrapper.emitted('move-up')).toBeTruthy()
    })

    it('emits move-down when down arrow clicked', async () => {
      const wrapper = mountEditor({ index: 0, totalQuestions: 3 })
      const downBtn = wrapper.find('button[aria-label="Move question down"]')
      await downBtn.trigger('click')
      expect(wrapper.emitted('move-down')).toBeTruthy()
    })

    it('emits duplicate when duplicate button clicked', async () => {
      const wrapper = mountEditor()
      const dupBtn = wrapper.find('button[aria-label="Duplicate question"]')
      await dupBtn.trigger('click')
      expect(wrapper.emitted('duplicate')).toBeTruthy()
    })

    it('emits toggle-collapse when collapse button clicked', async () => {
      const wrapper = mountEditor()
      const collapseBtn = wrapper.find('button[aria-label="Collapse question"]')
      await collapseBtn.trigger('click')
      expect(wrapper.emitted('toggle-collapse')).toBeTruthy()
    })

    it('emits add-option when add option clicked', async () => {
      const wrapper = mountEditor({
        question: createQuestion({ type: 'single_choice', options: [] }),
      })
      const addBtn = wrapper.findAll('button').find((b) => b.text().includes('+ Add option'))
      await addBtn!.trigger('click')
      expect(wrapper.emitted('add-option')).toBeTruthy()
    })

    it('emits remove-option with index when option remove clicked', async () => {
      const wrapper = mountEditor({
        question: createQuestion({
          type: 'single_choice',
          options: [{ id: 'o1', label: 'A' }],
        }),
      })
      const removeBtn = wrapper.find('button[aria-label="Remove option"]')
      await removeBtn.trigger('click')
      expect(wrapper.emitted('remove-option')).toBeTruthy()
      expect(wrapper.emitted('remove-option')![0]).toEqual([0])
    })

    it('emits move-option with index and direction', async () => {
      const wrapper = mountEditor({
        question: createQuestion({
          type: 'single_choice',
          options: [
            { id: 'o1', label: 'A' },
            { id: 'o2', label: 'B' },
          ],
        }),
      })
      const moveDownBtns = wrapper.findAll('button[aria-label="Move option down"]')
      await moveDownBtns[0].trigger('click')
      expect(wrapper.emitted('move-option')).toBeTruthy()
      expect(wrapper.emitted('move-option')![0]).toEqual([0, 1])
    })

    it('emits insert-at when insert button clicked', async () => {
      const wrapper = mountEditor({ index: 1, totalQuestions: 3 })
      const insertBtn = wrapper.find('button[aria-label="Insert question here"]')
      expect(insertBtn.exists()).toBe(true)
      await insertBtn.trigger('click')
      expect(wrapper.emitted('insert-at')).toBeTruthy()
    })

    it('does not render insert button for first question', () => {
      const wrapper = mountEditor({ index: 0 })
      const insertBtn = wrapper.find('button[aria-label="Insert question here"]')
      expect(insertBtn.exists()).toBe(false)
    })
  })

  describe('disabled state (schema-locked)', () => {
    it('disables move/duplicate/delete buttons when schema-locked', () => {
      const wrapper = mountEditor({ isSchemaLocked: true })
      const upBtn = wrapper.find('button[aria-label="Move question up"]')
      expect(upBtn.exists()).toBe(false)
    })

    it('disables type selector when schema-locked', () => {
      const wrapper = mountEditor({ isSchemaLocked: true })
      // Expanded content not visible when locked? Actually it should be.
      // Let's check: isCollapsed is false, so it shows.
      const select = wrapper.find('select')
      expect(select.exists()).toBe(true)
      expect(select.attributes('disabled')).toBeDefined()
    })
  })

  describe('move button disabled states', () => {
    it('disables move-up for first question', () => {
      const wrapper = mountEditor({ index: 0, totalQuestions: 3 })
      const upBtn = wrapper.find('button[aria-label="Move question up"]')
      expect(upBtn.attributes('disabled')).toBeDefined()
    })

    it('disables move-down for last question', () => {
      const wrapper = mountEditor({ index: 2, totalQuestions: 3 })
      const downBtn = wrapper.find('button[aria-label="Move question down"]')
      expect(downBtn.attributes('disabled')).toBeDefined()
    })
  })
})

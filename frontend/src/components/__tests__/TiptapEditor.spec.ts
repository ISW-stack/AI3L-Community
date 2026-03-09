import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { ref } from 'vue'
import TiptapEditor from '../TiptapEditor.vue'

// Mock all TipTap dependencies
const mockChain = {
  focus: vi.fn().mockReturnThis(),
  toggleBold: vi.fn().mockReturnThis(),
  toggleItalic: vi.fn().mockReturnThis(),
  toggleHeading: vi.fn().mockReturnThis(),
  toggleBulletList: vi.fn().mockReturnThis(),
  toggleOrderedList: vi.fn().mockReturnThis(),
  toggleBlockquote: vi.fn().mockReturnThis(),
  toggleCodeBlock: vi.fn().mockReturnThis(),
  setLink: vi.fn().mockReturnThis(),
  setImage: vi.fn().mockReturnThis(),
  insertTable: vi.fn().mockReturnThis(),
  undo: vi.fn().mockReturnThis(),
  redo: vi.fn().mockReturnThis(),
  setContent: vi.fn().mockReturnThis(),
  run: vi.fn(),
}

const mockEditor = {
  chain: vi.fn(() => mockChain),
  isActive: vi.fn(() => false),
  can: vi.fn(() => ({ undo: vi.fn(() => true), redo: vi.fn(() => true) })),
  getHTML: vi.fn(() => '<p>test</p>'),
  commands: { setContent: vi.fn() },
}

vi.mock('@tiptap/vue-3', () => ({
  useEditor: vi.fn(() => ref(mockEditor)),
  EditorContent: {
    name: 'EditorContent',
    props: ['editor'],
    template: '<div class="editor-content" />',
  },
}))

vi.mock('@tiptap/starter-kit', () => ({
  default: { configure: vi.fn().mockReturnThis() },
}))

vi.mock('@tiptap/extension-image', () => ({ default: {} }))

vi.mock('@tiptap/extension-link', () => ({
  default: { configure: vi.fn().mockReturnThis() },
}))

vi.mock('@tiptap/extension-table', () => ({
  Table: { configure: vi.fn().mockReturnThis() },
}))

vi.mock('@tiptap/extension-table-row', () => ({
  TableRow: {},
}))

vi.mock('@tiptap/extension-table-cell', () => ({
  TableCell: {},
}))

vi.mock('@tiptap/extension-table-header', () => ({
  TableHeader: {},
}))

vi.mock('@/api/files', () => ({
  uploadEditorFile: vi.fn(),
  getFileScanStatus: vi.fn(),
}))

vi.mock('lucide-vue-next', () => ({
  Bold: { name: 'Bold', template: '<svg data-testid="bold-icon" />' },
  Italic: { name: 'Italic', template: '<svg data-testid="italic-icon" />' },
  Heading1: { name: 'Heading1', template: '<svg />' },
  Heading2: { name: 'Heading2', template: '<svg />' },
  Heading3: { name: 'Heading3', template: '<svg />' },
  List: { name: 'List', template: '<svg />' },
  ListOrdered: { name: 'ListOrdered', template: '<svg />' },
  Quote: { name: 'Quote', template: '<svg />' },
  Code: { name: 'Code', template: '<svg />' },
  Link: { name: 'Link', template: '<svg />' },
  ImagePlus: { name: 'ImagePlus', template: '<svg data-testid="image-btn" />' },
  Undo2: { name: 'Undo2', template: '<svg />' },
  Redo2: { name: 'Redo2', template: '<svg />' },
  Table: { name: 'Table', template: '<svg />' },
  ShieldCheck: { name: 'ShieldCheck', template: '<svg data-testid="shield-check" />' },
  ShieldAlert: { name: 'ShieldAlert', template: '<svg data-testid="shield-alert" />' },
  Loader2: { name: 'Loader2', template: '<svg data-testid="loader" />' },
}))

describe('TiptapEditor', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.restoreAllMocks()
    // Re-setup chain mocks after restoreAllMocks
    mockChain.focus.mockReturnThis()
    mockChain.toggleBold.mockReturnThis()
    mockChain.toggleItalic.mockReturnThis()
    mockChain.run.mockReturnValue(undefined)
    mockEditor.chain.mockReturnValue(mockChain)
    mockEditor.isActive.mockReturnValue(false)
    mockEditor.can.mockReturnValue({ undo: vi.fn(() => true), redo: vi.fn(() => true) })
    mockEditor.getHTML.mockReturnValue('<p>test</p>')
  })

  describe('rendering', () => {
    it('should render the editor container', () => {
      const wrapper = mount(TiptapEditor, {
        props: { modelValue: '<p>Hello</p>' },
      })
      expect(wrapper.find('.border').exists()).toBe(true)
    })

    it('should render the toolbar with buttons', () => {
      const wrapper = mount(TiptapEditor, {
        props: { modelValue: '<p>Hello</p>' },
      })
      const buttons = wrapper.findAll('button[type="button"]')
      expect(buttons.length).toBeGreaterThan(0)
    })

    it('should render EditorContent', () => {
      const wrapper = mount(TiptapEditor, {
        props: { modelValue: '<p>Hello</p>' },
      })
      expect(wrapper.find('.editor-content').exists()).toBe(true)
    })

    it('should render hidden file input for image upload', () => {
      const wrapper = mount(TiptapEditor, {
        props: { modelValue: '' },
      })
      const fileInput = wrapper.find('input[type="file"]')
      expect(fileInput.exists()).toBe(true)
      expect(fileInput.attributes('accept')).toContain('image/png')
    })
  })

  describe('toolbar interactions', () => {
    it('should call toggleBold on bold button click', async () => {
      const wrapper = mount(TiptapEditor, {
        props: { modelValue: '' },
      })
      const boldBtn = wrapper.findAll('button[type="button"]')[0]
      await boldBtn.trigger('click')
      expect(mockEditor.chain).toHaveBeenCalled()
    })

    it('should call toggleItalic on italic button click', async () => {
      const wrapper = mount(TiptapEditor, {
        props: { modelValue: '' },
      })
      const italicBtn = wrapper.findAll('button[type="button"]')[1]
      await italicBtn.trigger('click')
      expect(mockEditor.chain).toHaveBeenCalled()
    })
  })

  describe('scan status indicator', () => {
    it('should not show scan status by default', () => {
      const wrapper = mount(TiptapEditor, {
        props: { modelValue: '' },
      })
      expect(wrapper.find('[data-testid="loader"]').exists()).toBe(false)
      expect(wrapper.find('[data-testid="shield-check"]').exists()).toBe(false)
      expect(wrapper.find('[data-testid="shield-alert"]').exists()).toBe(false)
    })
  })
})

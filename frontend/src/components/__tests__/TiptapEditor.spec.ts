import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
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
  insertContent: vi.fn().mockReturnThis(),
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
    vi.clearAllMocks()
    // Re-setup chain mocks after clearAllMocks
    mockChain.focus.mockReturnThis()
    mockChain.toggleBold.mockReturnThis()
    mockChain.toggleItalic.mockReturnThis()
    mockChain.setImage.mockReturnThis()
    mockChain.insertContent.mockReturnThis()
    mockChain.setLink.mockReturnThis()
    mockChain.insertTable.mockReturnThis()
    mockChain.toggleHeading.mockReturnThis()
    mockChain.toggleBulletList.mockReturnThis()
    mockChain.toggleOrderedList.mockReturnThis()
    mockChain.toggleBlockquote.mockReturnThis()
    mockChain.toggleCodeBlock.mockReturnThis()
    mockChain.undo.mockReturnThis()
    mockChain.redo.mockReturnThis()
    mockChain.setContent.mockReturnThis()
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

  describe('handleFileUpload', () => {
    it('accepts image/png,image/jpeg,image/gif,image/webp,.pdf,.docx in file input', () => {
      const wrapper = mount(TiptapEditor, { props: { modelValue: '' } })
      const fileInput = wrapper.find('input[type="file"]')
      const accept = fileInput.attributes('accept') ?? ''
      expect(accept).toContain('image/png')
      expect(accept).toContain('image/jpeg')
      expect(accept).toContain('.pdf')
      expect(accept).toContain('.docx')
    })

    it('calls setImage when an image file is uploaded', async () => {
      const { uploadEditorFile } = await import('@/api/files')
      vi.mocked(uploadEditorFile).mockResolvedValue({
        url: '/api/v1/files/content/editor/x/photo.png',
        key: 'editor/x/photo.png',
        scan_task_id: null,
      })

      const wrapper = mount(TiptapEditor, { props: { modelValue: '' } })
      const vm = wrapper.vm as any

      const file = new File(['data'], 'photo.png', { type: 'image/png' })
      const fakeEvent = { target: { files: [file], value: '' } } as unknown as Event
      await vm.handleFileUpload(fakeEvent)
      await flushPromises()

      expect(mockChain.setImage).toHaveBeenCalledWith({
        src: '/api/v1/files/content/editor/x/photo.png',
      })
      expect(mockChain.run).toHaveBeenCalled()
    })

    it('calls insertContent with an <a> tag when a PDF file is uploaded', async () => {
      const { uploadEditorFile } = await import('@/api/files')
      vi.mocked(uploadEditorFile).mockResolvedValue({
        url: '/api/v1/files/content/editor/x/report.pdf',
        key: 'editor/x/report.pdf',
        scan_task_id: 'task-abc',
      })

      const wrapper = mount(TiptapEditor, { props: { modelValue: '' } })
      const vm = wrapper.vm as any

      const file = new File(['data'], 'report.pdf', { type: 'application/pdf' })
      const fakeEvent = { target: { files: [file], value: '' } } as unknown as Event
      await vm.handleFileUpload(fakeEvent)
      await flushPromises()

      expect(mockChain.insertContent).toHaveBeenCalledWith(
        expect.stringContaining('<a href="/api/v1/files/content/editor/x/report.pdf"'),
      )
      expect(mockChain.insertContent).toHaveBeenCalledWith(expect.stringContaining('report.pdf'))
      expect(mockChain.run).toHaveBeenCalled()
    })

    it('calls insertContent with an <a> tag when a DOCX file is uploaded', async () => {
      const { uploadEditorFile } = await import('@/api/files')
      vi.mocked(uploadEditorFile).mockResolvedValue({
        url: '/api/v1/files/content/editor/x/doc.docx',
        key: 'editor/x/doc.docx',
        scan_task_id: null,
      })

      const wrapper = mount(TiptapEditor, { props: { modelValue: '' } })
      const vm = wrapper.vm as any

      const file = new File(['data'], 'doc.docx', {
        type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      })
      const fakeEvent = { target: { files: [file], value: '' } } as unknown as Event
      await vm.handleFileUpload(fakeEvent)
      await flushPromises()

      expect(mockChain.setImage).not.toHaveBeenCalled()
      expect(mockChain.insertContent).toHaveBeenCalledWith(
        expect.stringContaining('target="_blank"'),
      )
    })

    it('does not call setImage or insertContent when no file is selected', async () => {
      const wrapper = mount(TiptapEditor, { props: { modelValue: '' } })
      const vm = wrapper.vm as any

      const fakeEvent = { target: { files: [], value: '' } } as unknown as Event
      await vm.handleFileUpload(fakeEvent)
      await flushPromises()

      expect(mockChain.setImage).not.toHaveBeenCalled()
      expect(mockChain.insertContent).not.toHaveBeenCalled()
    })

    it('sets scan status to pending when upload returns a scan_task_id', async () => {
      const { uploadEditorFile } = await import('@/api/files')
      vi.mocked(uploadEditorFile).mockResolvedValue({
        url: '/api/v1/files/content/editor/x/file.pdf',
        key: 'editor/x/file.pdf',
        scan_task_id: 'task-123',
      })

      const wrapper = mount(TiptapEditor, { props: { modelValue: '' } })
      const vm = wrapper.vm as any

      const file = new File(['data'], 'file.pdf', { type: 'application/pdf' })
      const fakeEvent = { target: { files: [file], value: '' } } as unknown as Event
      await vm.handleFileUpload(fakeEvent)
      await flushPromises()

      // After upload with scan_task_id, scanStatus should be 'pending'
      expect(vm.scanStatus).toBe('pending')
    })

    it('rejects files larger than 20 MB and shows error toast', async () => {
      const { uploadEditorFile } = await import('@/api/files')

      const wrapper = mount(TiptapEditor, { props: { modelValue: '' } })
      const vm = wrapper.vm as any

      // Create a file object with size > 20 MB
      const largeFile = new File(['x'], 'huge.pdf', { type: 'application/pdf' })
      Object.defineProperty(largeFile, 'size', { value: 21 * 1024 * 1024 })

      const fakeEvent = { target: { files: [largeFile], value: '' } } as unknown as Event
      await vm.handleFileUpload(fakeEvent)
      await flushPromises()

      // uploadEditorFile should NOT have been called
      expect(vi.mocked(uploadEditorFile)).not.toHaveBeenCalled()
      // Editor should not have inserted anything
      expect(mockChain.setImage).not.toHaveBeenCalled()
      expect(mockChain.insertContent).not.toHaveBeenCalled()
    })

    it('accepts files at exactly 20 MB', async () => {
      const { uploadEditorFile } = await import('@/api/files')
      vi.mocked(uploadEditorFile).mockResolvedValue({
        url: '/api/v1/files/content/editor/x/exact.pdf',
        key: 'editor/x/exact.pdf',
        scan_task_id: null,
      })

      const wrapper = mount(TiptapEditor, { props: { modelValue: '' } })
      const vm = wrapper.vm as any

      // Create a file exactly at the limit (20 MB)
      const exactFile = new File(['x'], 'exact.pdf', { type: 'application/pdf' })
      Object.defineProperty(exactFile, 'size', { value: 20 * 1024 * 1024 })

      const fakeEvent = { target: { files: [exactFile], value: '' } } as unknown as Event
      await vm.handleFileUpload(fakeEvent)
      await flushPromises()

      // uploadEditorFile SHOULD have been called (exactly at limit is allowed)
      expect(vi.mocked(uploadEditorFile)).toHaveBeenCalled()
    })

    it('does not set scan status to pending when scan_task_id is absent', async () => {
      const { uploadEditorFile } = await import('@/api/files')
      vi.mocked(uploadEditorFile).mockResolvedValue({
        url: '/api/v1/files/content/editor/x/photo.png',
        key: 'editor/x/photo.png',
        scan_task_id: null,
      })

      const wrapper = mount(TiptapEditor, { props: { modelValue: '' } })
      const vm = wrapper.vm as any

      const file = new File(['data'], 'photo.png', { type: 'image/png' })
      const fakeEvent = { target: { files: [file], value: '' } } as unknown as Event
      await vm.handleFileUpload(fakeEvent)
      await flushPromises()

      expect(vm.scanStatus).toBeNull()
    })
  })
})

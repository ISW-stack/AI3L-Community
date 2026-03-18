import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { nextTick } from 'vue'
import type { DMMessage, Conversation } from '@/types/dm'

// --------------- Global mocks ---------------

vi.mock('@/composables/api', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
}))

vi.mock('@/constants', () => ({
  HEARTBEAT_INTERVAL_MS: 30000,
  WS_INITIAL_BACKOFF_MS: 1000,
  WS_MAX_BACKOFF_MS: 30000,
}))

vi.mock('lucide-vue-next', () => ({
  Paperclip: { name: 'Paperclip', template: '<span class="icon-paperclip" />' },
  Send: { name: 'Send', template: '<span class="icon-send" />' },
  Check: { name: 'Check', template: '<span class="icon-check" />' },
  CheckCheck: { name: 'CheckCheck', template: '<span class="icon-check-check" />' },
  MoreHorizontal: { name: 'MoreHorizontal', template: '<span class="icon-more" />' },
  X: { name: 'X', template: '<span class="icon-x" />' },
  File: { name: 'File', template: '<span class="icon-file" />' },
  FileText: { name: 'FileText', template: '<span class="icon-file-text" />' },
  Film: { name: 'Film', template: '<span class="icon-film" />' },
  Music: { name: 'Music', template: '<span class="icon-music" />' },
  Download: { name: 'Download', template: '<span class="icon-download" />' },
  AlertTriangle: { name: 'AlertTriangle', template: '<span class="icon-alert" />' },
  MessageSquare: { name: 'MessageSquare', template: '<span class="icon-message-square" />' },
  ArrowLeft: { name: 'ArrowLeft', template: '<span class="icon-arrow-left" />' },
  ArrowDown: { name: 'ArrowDown', template: '<span class="icon-arrow-down" />' },
  Pencil: { name: 'Pencil', template: '<span class="icon-pencil" />' },
  Trash2: { name: 'Trash2', template: '<span class="icon-trash" />' },
}))

vi.mock('@/utils/datetime', () => ({
  relativeTime: (_date: string) => '2 min ago',
  formatDateTime: (date: string) => date,
}))

vi.mock('vue-router', () => ({
  useRoute: () => ({ params: {} }),
  useRouter: () => ({ push: vi.fn() }),
}))

const mockDMStoreState = {
  conversations: [] as Conversation[],
  conversationsTotal: 0,
  messages: [] as DMMessage[],
  messagesTotal: 0,
  unreadCount: 0,
  activeConversationId: null as string | null,
  loading: false,
  error: null as string | null,
}

vi.mock('@/stores/dm', () => ({
  useDMStore: () => ({
    get conversations() { return mockDMStoreState.conversations },
    set conversations(v) { mockDMStoreState.conversations = v },
    get conversationsTotal() { return mockDMStoreState.conversationsTotal },
    get messages() { return mockDMStoreState.messages },
    set messages(v) { mockDMStoreState.messages = v },
    get messagesTotal() { return mockDMStoreState.messagesTotal },
    set messagesTotal(v) { mockDMStoreState.messagesTotal = v },
    get unreadCount() { return mockDMStoreState.unreadCount },
    set unreadCount(v) { mockDMStoreState.unreadCount = v },
    get activeConversationId() { return mockDMStoreState.activeConversationId },
    get loading() { return mockDMStoreState.loading },
    get error() { return mockDMStoreState.error },
    fetchConversations: vi.fn(),
    fetchMessages: vi.fn(),
    setActiveConversation: vi.fn(),
    setCurrentUserId: vi.fn(),
  }),
}))

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({
    role: 'MEMBER',
    isAuthenticated: true,
    isAdmin: false,
    isSuperAdmin: false,
    isGuest: false,
    user: { id: 'user-1', display_name: 'Bob' },
    clearSession: vi.fn(),
  }),
}))

vi.mock('@/stores/toast', () => ({
  useToastStore: () => ({
    toasts: [],
    show: vi.fn(),
    dismiss: vi.fn(),
    clearAll: vi.fn(),
    showKey: vi.fn(),
  }),
}))

vi.mock('@/api/dm', () => ({
  listConversations: vi.fn(),
  listMessages: vi.fn(),
  sendMessage: vi.fn(),
  editMessage: vi.fn(),
  recallMessage: vi.fn(),
  markConversationRead: vi.fn(),
  getUnreadCount: vi.fn(),
}))

vi.mock('@/composables/usePagination', () => ({
  usePagination: () => ({
    page: { value: 1 },
    total: { value: 0 },
    totalPages: { value: 1 },
    pageSize: 30,
    setPage: vi.fn(),
    resetPage: vi.fn(),
    updateFromResponse: vi.fn(),
  }),
}))

// --------------- Import components ---------------

import ConversationList from '@/components/dm/ConversationList.vue'
import MessageThread from '@/components/dm/MessageThread.vue'
import MessageInput from '@/components/dm/MessageInput.vue'

// --------------- Test data factories ---------------

function makeSender(overrides: Record<string, unknown> = {}) {
  return {
    id: 'user-2',
    display_name: 'Alice',
    avatar_url: null as string | null,
    ...overrides,
  }
}

function makeMessage(overrides: Partial<DMMessage> = {}): DMMessage {
  return {
    id: 'msg-1',
    conversation_id: 'conv-1',
    sender: makeSender({ id: 'user-1', display_name: 'Bob' }),
    content: 'Hello!',
    attachment_url: null,
    attachment_name: null,
    attachment_size: null,
    attachment_expires_at: null,
    is_recalled: false,
    is_edited: false,
    read_at: null,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    ...overrides,
  }
}

function makeConversation(overrides: Partial<Conversation> = {}): Conversation {
  return {
    id: 'conv-1',
    other_user: makeSender(),
    last_message: null,
    unread_count: 0,
    updated_at: '2026-03-17T00:00:00Z',
    ...overrides,
  }
}

// --------------- UX-6: Image preview + file type icons ---------------

describe('UX-6: Image preview and file type icons', () => {
  function mountThread(props: Record<string, unknown> = {}) {
    const pinia = createPinia()
    setActivePinia(pinia)
    return mount(MessageThread, {
      props: {
        messages: [],
        currentUserId: 'user-1',
        loading: false,
        hasMore: false,
        ...props,
      },
      global: {
        plugins: [pinia],
      },
    })
  }

  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders <img> thumbnail for .jpg attachment', () => {
    const wrapper = mountThread({
      messages: [
        makeMessage({
          content: null,
          attachment_url: 'https://cdn.example.com/photo.jpg',
          attachment_name: 'photo.jpg',
          attachment_size: 2048,
        }),
      ],
    })
    const img = wrapper.find('img[alt="photo.jpg"]')
    expect(img.exists()).toBe(true)
    expect(img.attributes('src')).toBe('https://cdn.example.com/photo.jpg')
    expect(img.classes()).toContain('max-h-48')
    expect(img.classes()).toContain('rounded-lg')
  })

  it('renders <img> thumbnail for .png attachment', () => {
    const wrapper = mountThread({
      messages: [
        makeMessage({
          content: null,
          attachment_url: 'https://cdn.example.com/image.png',
          attachment_name: 'image.png',
          attachment_size: 4096,
        }),
      ],
    })
    const img = wrapper.find('img[alt="image.png"]')
    expect(img.exists()).toBe(true)
    expect(img.attributes('src')).toBe('https://cdn.example.com/image.png')
  })

  it('wraps image in a link to the full file', () => {
    const wrapper = mountThread({
      messages: [
        makeMessage({
          content: null,
          attachment_url: 'https://cdn.example.com/photo.webp',
          attachment_name: 'photo.webp',
        }),
      ],
    })
    const link = wrapper.find('a[href="https://cdn.example.com/photo.webp"]')
    expect(link.exists()).toBe(true)
    expect(link.attributes('target')).toBe('_blank')
    expect(link.find('img').exists()).toBe(true)
  })

  it('renders Film icon for .mp4 attachment', () => {
    const wrapper = mountThread({
      messages: [
        makeMessage({
          content: null,
          attachment_url: 'https://cdn.example.com/video.mp4',
          attachment_name: 'video.mp4',
          attachment_size: 1024 * 1024,
        }),
      ],
    })
    expect(wrapper.find('.icon-film').exists()).toBe(true)
    // Should not render image
    expect(wrapper.find('img[alt="video.mp4"]').exists()).toBe(false)
  })

  it('renders Music icon for .mp3 attachment', () => {
    const wrapper = mountThread({
      messages: [
        makeMessage({
          content: null,
          attachment_url: 'https://cdn.example.com/song.mp3',
          attachment_name: 'song.mp3',
          attachment_size: 5000,
        }),
      ],
    })
    expect(wrapper.find('.icon-music').exists()).toBe(true)
    expect(wrapper.find('img[alt="song.mp3"]').exists()).toBe(false)
  })

  it('renders FileText icon for .pdf attachment', () => {
    const wrapper = mountThread({
      messages: [
        makeMessage({
          content: null,
          attachment_url: 'https://cdn.example.com/report.pdf',
          attachment_name: 'report.pdf',
          attachment_size: 10000,
        }),
      ],
    })
    expect(wrapper.find('.icon-file-text').exists()).toBe(true)
    expect(wrapper.find('img[alt="report.pdf"]').exists()).toBe(false)
  })

  it('renders generic File icon for .txt attachment', () => {
    const wrapper = mountThread({
      messages: [
        makeMessage({
          content: null,
          attachment_url: 'https://cdn.example.com/notes.txt',
          attachment_name: 'notes.txt',
          attachment_size: 500,
        }),
      ],
    })
    expect(wrapper.find('.icon-file').exists()).toBe(true)
    expect(wrapper.find('img[alt="notes.txt"]').exists()).toBe(false)
  })

  it('still shows file name and size for non-image files', () => {
    const wrapper = mountThread({
      messages: [
        makeMessage({
          content: null,
          attachment_url: 'https://cdn.example.com/doc.pdf',
          attachment_name: 'doc.pdf',
          attachment_size: 2 * 1024 * 1024,
        }),
      ],
    })
    expect(wrapper.text()).toContain('doc.pdf')
    expect(wrapper.text()).toContain('2.0 MB')
  })

  it('still shows "File expired" for expired image attachments', () => {
    const expired = new Date(Date.now() - 1000).toISOString()
    const wrapper = mountThread({
      messages: [
        makeMessage({
          attachment_url: 'https://cdn.example.com/photo.jpg',
          attachment_name: 'photo.jpg',
          attachment_expires_at: expired,
        }),
      ],
    })
    expect(wrapper.text()).toContain('File expired')
    expect(wrapper.find('img[alt="photo.jpg"]').exists()).toBe(false)
  })

  it('shows expiry warning for non-image files expiring soon', () => {
    const soon = new Date(Date.now() + 12 * 60 * 60 * 1000).toISOString()
    const wrapper = mountThread({
      messages: [
        makeMessage({
          attachment_url: 'https://cdn.example.com/doc.pdf',
          attachment_name: 'doc.pdf',
          attachment_expires_at: soon,
        }),
      ],
    })
    expect(wrapper.text()).toContain('Expires soon')
  })
})

// --------------- UX-8: Textarea overflow indicator ---------------

describe('UX-8: Textarea overflow indicator', () => {
  function mountInput(props: Record<string, unknown> = {}) {
    const pinia = createPinia()
    setActivePinia(pinia)
    return mount(MessageInput, {
      props: {
        disabled: false,
        ...props,
      },
      global: {
        plugins: [pinia],
      },
    })
  }

  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('has overflow-y-auto class on textarea', () => {
    const wrapper = mountInput()
    const textarea = wrapper.find('textarea')
    expect(textarea.classes()).toContain('overflow-y-auto')
  })

  it('shows gradient overlay when textarea is overflowing', async () => {
    const wrapper = mountInput()
    const textarea = wrapper.find('textarea')

    // Simulate overflow: scrollHeight > clientHeight
    Object.defineProperty(textarea.element, 'scrollHeight', { value: 200, configurable: true })
    Object.defineProperty(textarea.element, 'clientHeight', { value: 120, configurable: true })

    // Trigger the input event to call checkOverflow
    await textarea.trigger('input')
    await nextTick()

    const gradient = wrapper.find('.bg-gradient-to-t')
    expect(gradient.exists()).toBe(true)
    expect(gradient.classes()).toContain('pointer-events-none')
  })

  it('hides gradient overlay when textarea is not overflowing', async () => {
    const wrapper = mountInput()
    const textarea = wrapper.find('textarea')

    // Simulate no overflow: scrollHeight === clientHeight
    Object.defineProperty(textarea.element, 'scrollHeight', { value: 38, configurable: true })
    Object.defineProperty(textarea.element, 'clientHeight', { value: 38, configurable: true })

    await textarea.trigger('input')
    await nextTick()

    expect(wrapper.find('.bg-gradient-to-t').exists()).toBe(false)
  })
})

// --------------- Accessibility: ConversationList ---------------

describe('Accessibility: ConversationList', () => {
  function mountConvList(props: Record<string, unknown> = {}) {
    const pinia = createPinia()
    setActivePinia(pinia)
    return mount(ConversationList, {
      props: {
        conversations: [],
        activeId: null,
        loading: false,
        ...props,
      },
      global: {
        plugins: [pinia],
      },
    })
  }

  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('unread badge has role="status" and aria-label with count', () => {
    const wrapper = mountConvList({
      conversations: [makeConversation({ unread_count: 5 })],
    })
    const badge = wrapper.find('[role="status"]')
    expect(badge.exists()).toBe(true)
    expect(badge.attributes('aria-label')).toBe('5 unread messages')
  })

  it('unread badge uses singular "message" for count of 1', () => {
    const wrapper = mountConvList({
      conversations: [makeConversation({ unread_count: 1 })],
    })
    const badge = wrapper.find('[role="status"]')
    expect(badge.exists()).toBe(true)
    expect(badge.attributes('aria-label')).toBe('1 unread message')
  })

  it('active conversation button has aria-current="true"', () => {
    const wrapper = mountConvList({
      conversations: [makeConversation({ id: 'conv-1' })],
      activeId: 'conv-1',
    })
    const button = wrapper.find('button')
    expect(button.attributes('aria-current')).toBe('true')
  })

  it('inactive conversation button does not have aria-current', () => {
    const wrapper = mountConvList({
      conversations: [makeConversation({ id: 'conv-1' })],
      activeId: 'conv-2',
    })
    const button = wrapper.find('button')
    expect(button.attributes('aria-current')).toBeUndefined()
  })
})

// --------------- Accessibility: MessageThread date separator ---------------

describe('Accessibility: MessageThread date separator', () => {
  function mountThread(props: Record<string, unknown> = {}) {
    const pinia = createPinia()
    setActivePinia(pinia)
    return mount(MessageThread, {
      props: {
        messages: [],
        currentUserId: 'user-1',
        loading: false,
        hasMore: false,
        ...props,
      },
      global: {
        plugins: [pinia],
      },
    })
  }

  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('date separator has role="separator" and aria-label', () => {
    const wrapper = mountThread({
      messages: [makeMessage({ created_at: new Date().toISOString() })],
    })
    const separator = wrapper.find('[role="separator"]')
    expect(separator.exists()).toBe(true)
    expect(separator.attributes('aria-label')).toBeTruthy()
    // The label should be "Today" since the message was created now
    expect(separator.attributes('aria-label')).toBe('Today')
  })
})

// --------------- Accessibility: MessageInput char counter ---------------

describe('Accessibility: MessageInput char counter', () => {
  function mountInput(props: Record<string, unknown> = {}) {
    const pinia = createPinia()
    setActivePinia(pinia)
    return mount(MessageInput, {
      props: {
        disabled: false,
        ...props,
      },
      global: {
        plugins: [pinia],
      },
    })
  }

  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('char counter has aria-live="polite" when visible', async () => {
    const wrapper = mountInput()
    const longText = 'a'.repeat(4600)
    await wrapper.find('textarea').setValue(longText)
    await nextTick()

    const counter = wrapper.find('[aria-live="polite"]')
    expect(counter.exists()).toBe(true)
    expect(counter.attributes('aria-label')).toBe('400 characters remaining')
  })

  it('char counter aria-label updates with remaining count', async () => {
    const wrapper = mountInput()
    const longText = 'a'.repeat(4900)
    await wrapper.find('textarea').setValue(longText)
    await nextTick()

    const counter = wrapper.find('[aria-live="polite"]')
    expect(counter.exists()).toBe(true)
    expect(counter.attributes('aria-label')).toBe('100 characters remaining')
  })
})

// --------------- B-06: MessageInput reacts to editContent prop changes ---------------

describe('B-06: MessageInput editContent reactivity', () => {
  function mountInput(props: Record<string, unknown> = {}) {
    const pinia = createPinia()
    setActivePinia(pinia)
    return mount(MessageInput, {
      props: {
        disabled: false,
        ...props,
      },
      global: {
        plugins: [pinia],
      },
    })
  }

  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('updates textarea content when editContent prop changes', async () => {
    const wrapper = mountInput({ editMode: true, editContent: 'First message' })
    const textarea = wrapper.find('textarea')
    expect((textarea.element as HTMLTextAreaElement).value).toBe('First message')

    await wrapper.setProps({ editContent: 'Second message' })
    await nextTick()

    expect((textarea.element as HTMLTextAreaElement).value).toBe('Second message')
  })

  it('does not clear content when editContent becomes undefined', async () => {
    const wrapper = mountInput({ editMode: true, editContent: 'Hello' })
    const textarea = wrapper.find('textarea')
    expect((textarea.element as HTMLTextAreaElement).value).toBe('Hello')

    await wrapper.setProps({ editContent: undefined })
    await nextTick()

    // Content should remain 'Hello' since undefined is ignored
    expect((textarea.element as HTMLTextAreaElement).value).toBe('Hello')
  })

  it('sets content to empty string when editContent changes to empty string', async () => {
    const wrapper = mountInput({ editMode: true, editContent: 'Hello' })

    await wrapper.setProps({ editContent: '' })
    await nextTick()

    const textarea = wrapper.find('textarea')
    expect((textarea.element as HTMLTextAreaElement).value).toBe('')
  })
})

// --------------- S-11: MessageInput file input accept attribute ---------------

describe('S-11: MessageInput file input accept attribute', () => {
  function mountInput(props: Record<string, unknown> = {}) {
    const pinia = createPinia()
    setActivePinia(pinia)
    return mount(MessageInput, {
      props: {
        disabled: false,
        ...props,
      },
      global: {
        plugins: [pinia],
      },
    })
  }

  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('file input has accept attribute restricting file types', () => {
    const wrapper = mountInput()
    const fileInput = wrapper.find('input[type="file"]')
    expect(fileInput.exists()).toBe(true)
    expect(fileInput.attributes('accept')).toBe(
      'image/*,.pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.txt,.csv,.zip',
    )
  })
})

// --------------- UX-9: Mobile back button ---------------

describe('UX-9: Mobile back button', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockDMStoreState.activeConversationId = 'conv-1'
    mockDMStoreState.conversations = [makeConversation({ id: 'conv-1' })]
    mockDMStoreState.messages = []
    mockDMStoreState.messagesTotal = 0
    mockDMStoreState.loading = false
  })

  it('back button has p-2 class for larger tap target', async () => {
    // We need to import DMView dynamically to avoid issues with onMounted calling fetchConversations
    const DMView = (await import('@/views/DMView.vue')).default
    const pinia = createPinia()
    setActivePinia(pinia)
    const wrapper = mount(DMView, {
      global: {
        plugins: [pinia],
        stubs: {
          BaseBreadcrumb: { template: '<div />' },
          BaseModal: { template: '<div />' },
          EmptyState: { template: '<div />' },
        },
      },
    })
    await nextTick()

    const backBtn = wrapper.find('[aria-label="Back to conversations"]')
    expect(backBtn.exists()).toBe(true)
    expect(backBtn.classes()).toContain('p-2')
    expect(backBtn.classes()).toContain('-ml-2')
    expect(backBtn.classes()).toContain('rounded-lg')
  })
})

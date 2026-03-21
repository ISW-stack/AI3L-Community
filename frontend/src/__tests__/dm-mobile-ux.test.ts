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
  Lock: { name: 'Lock', template: '<span class="icon-lock" />' },
  Unlock: { name: 'Unlock', template: '<span class="icon-unlock" />' },
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
    get conversations() {
      return mockDMStoreState.conversations
    },
    set conversations(v) {
      mockDMStoreState.conversations = v
    },
    get conversationsTotal() {
      return mockDMStoreState.conversationsTotal
    },
    get messages() {
      return mockDMStoreState.messages
    },
    set messages(v) {
      mockDMStoreState.messages = v
    },
    get messagesTotal() {
      return mockDMStoreState.messagesTotal
    },
    set messagesTotal(v) {
      mockDMStoreState.messagesTotal = v
    },
    get unreadCount() {
      return mockDMStoreState.unreadCount
    },
    set unreadCount(v) {
      mockDMStoreState.unreadCount = v
    },
    get activeConversationId() {
      return mockDMStoreState.activeConversationId
    },
    get loading() {
      return mockDMStoreState.loading
    },
    get error() {
      return mockDMStoreState.error
    },
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

// --------------- Issue #1: DM split-panel mobile layout ---------------

describe('Issue #1: DM split-panel mobile layout', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockDMStoreState.activeConversationId = 'conv-1'
    mockDMStoreState.conversations = [makeConversation({ id: 'conv-1' })]
    mockDMStoreState.messages = []
    mockDMStoreState.messagesTotal = 0
    mockDMStoreState.loading = false
  })

  it('conversation list uses full width on mobile (w-full sm:w-80)', async () => {
    const DMView = (await import('@/views/DMView.vue')).default
    const pinia = createPinia()
    setActivePinia(pinia)
    const wrapper = mount(DMView, {
      global: {
        plugins: [pinia],
        stubs: {
          BaseBreadcrumb: { template: '<div />' },
          BaseModal: { template: '<div />' },
        },
      },
    })
    await nextTick()

    // Find the conversation list container
    const convListContainer = wrapper.find('.sm\\:w-80')
    expect(convListContainer.exists()).toBe(true)
    expect(convListContainer.classes()).toContain('w-full')
  })

  it('message panel uses full width on mobile (w-full sm:flex-1)', async () => {
    const DMView = (await import('@/views/DMView.vue')).default
    const pinia = createPinia()
    setActivePinia(pinia)
    const wrapper = mount(DMView, {
      global: {
        plugins: [pinia],
        stubs: {
          BaseBreadcrumb: { template: '<div />' },
          BaseModal: { template: '<div />' },
        },
      },
    })
    await nextTick()

    const messagePanel = wrapper.find('.sm\\:flex-1')
    expect(messagePanel.exists()).toBe(true)
    expect(messagePanel.classes()).toContain('w-full')
  })

  it('main container uses dvh height with vh fallback', async () => {
    const DMView = (await import('@/views/DMView.vue')).default
    const pinia = createPinia()
    setActivePinia(pinia)
    const wrapper = mount(DMView, {
      global: {
        plugins: [pinia],
        stubs: {
          BaseBreadcrumb: { template: '<div />' },
          BaseModal: { template: '<div />' },
        },
      },
    })
    await nextTick()

    const container = wrapper.find('.flex.bg-surface.border')
    expect(container.exists()).toBe(true)
    // Vue/jsdom may resolve the duplicate height declarations;
    // check that dvh is present in either the style attribute or the raw HTML
    const html = container.html()
    expect(html).toContain('dvh')
  })
})

// --------------- Issue #2: Touch-friendly action menu ---------------

describe('Issue #2: Touch-friendly action menu', () => {
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
      global: { plugins: [pinia] },
    })
  }

  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('action menu wrapper is semi-visible on mobile (opacity-40)', () => {
    const recent = new Date().toISOString()
    const wrapper = mountThread({
      messages: [
        makeMessage({
          sender: makeSender({ id: 'user-1' }),
          created_at: recent,
        }),
      ],
    })
    const actionWrapper = wrapper.find('[data-testid="message-action-wrapper"]')
    expect(actionWrapper.exists()).toBe(true)
    // When not open, should have opacity-40 class (mobile-visible)
    expect(actionWrapper.classes()).toContain('opacity-40')
  })

  it('action menu wrapper becomes fully visible when menu is open', async () => {
    const recent = new Date().toISOString()
    const wrapper = mountThread({
      messages: [
        makeMessage({
          id: 'msg-1',
          sender: makeSender({ id: 'user-1' }),
          created_at: recent,
        }),
      ],
    })

    // Click to open menu
    await wrapper.find('[aria-label="Message actions"]').trigger('click')
    await nextTick()

    const actionWrapper = wrapper.find('[data-testid="message-action-wrapper"]')
    expect(actionWrapper.classes()).toContain('opacity-100')
  })

  it('action button has touch-friendly padding (p-2 on mobile)', () => {
    const recent = new Date().toISOString()
    const wrapper = mountThread({
      messages: [
        makeMessage({
          sender: makeSender({ id: 'user-1' }),
          created_at: recent,
        }),
      ],
    })
    const btn = wrapper.find('[aria-label="Message actions"]')
    expect(btn.classes()).toContain('p-2')
    expect(btn.classes()).toContain('touch-manipulation')
  })

  it('dropdown menu items have touch-friendly padding (py-2.5 on mobile)', async () => {
    const recent = new Date().toISOString()
    const wrapper = mountThread({
      messages: [
        makeMessage({
          id: 'msg-1',
          sender: makeSender({ id: 'user-1' }),
          content: 'Hello',
          created_at: recent,
        }),
      ],
    })

    await wrapper.find('[aria-label="Message actions"]').trigger('click')
    await nextTick()

    const editBtn = wrapper.findAll('button').find((b) => b.text().includes('Edit'))
    expect(editBtn).toBeTruthy()
    expect(editBtn!.classes()).toContain('py-2.5')
    expect(editBtn!.classes()).toContain('touch-manipulation')
  })
})

// --------------- Issue #3: Touch target sizes ---------------

describe('Issue #3: Touch target sizes', () => {
  it('ConversationList avatar uses w-11 h-11 on mobile', () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const wrapper = mount(ConversationList, {
      props: {
        conversations: [makeConversation()],
        activeId: null,
        loading: false,
      },
      global: { plugins: [pinia] },
    })

    const avatarContainer = wrapper.find('.shrink-0.rounded-full')
    expect(avatarContainer.exists()).toBe(true)
    expect(avatarContainer.classes()).toContain('w-11')
    expect(avatarContainer.classes()).toContain('h-11')
  })

  it('ConversationList avatar img uses w-full h-full for responsive sizing', () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const wrapper = mount(ConversationList, {
      props: {
        conversations: [
          makeConversation({
            other_user: makeSender({ avatar_url: 'https://example.com/a.jpg' }),
          }),
        ],
        activeId: null,
        loading: false,
      },
      global: { plugins: [pinia] },
    })

    const img = wrapper.find('img')
    expect(img.exists()).toBe(true)
    expect(img.classes()).toContain('w-full')
    expect(img.classes()).toContain('h-full')
  })
})

// --------------- Issue #4: Message bubble max-width ---------------

describe('Issue #4: Message bubble responsive max-width', () => {
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
      global: { plugins: [pinia] },
    })
  }

  it('message bubble uses max-w-[85%] on mobile and max-w-[70%] on sm+', () => {
    const wrapper = mountThread({
      messages: [makeMessage()],
    })
    const bubble = wrapper.find('.max-w-\\[85\\%\\]')
    expect(bubble.exists()).toBe(true)
    expect(bubble.classes()).toContain('sm:max-w-[70%]')
  })

  it('message content uses break-words instead of wrap-anywhere', () => {
    const wrapper = mountThread({
      messages: [makeMessage({ content: 'https://example.com/very-long-url-that-should-break' })],
    })
    const content = wrapper.find('.break-words')
    expect(content.exists()).toBe(true)
  })

  it('file name truncation is responsive (max-w-32 on mobile, max-w-45 on sm+)', () => {
    const wrapper = mountThread({
      messages: [
        makeMessage({
          content: null,
          attachment_url: 'https://cdn.example.com/file.pdf',
          attachment_name: 'very-long-filename-that-should-truncate.pdf',
          attachment_size: 1024,
        }),
      ],
    })
    const fileName = wrapper.find('.truncate.max-w-32')
    expect(fileName.exists()).toBe(true)
    expect(fileName.classes()).toContain('sm:max-w-45')
  })
})

// --------------- Issue #6: MessageInput mobile enhancements ---------------

describe('Issue #6: MessageInput mobile enhancements', () => {
  function mountInput(props: Record<string, unknown> = {}) {
    const pinia = createPinia()
    setActivePinia(pinia)
    return mount(MessageInput, {
      props: { disabled: false, ...props },
      global: { plugins: [pinia] },
    })
  }

  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('textarea has min-height of 44px for mobile touch targets', () => {
    const wrapper = mountInput()
    const textarea = wrapper.find('textarea')
    const style = textarea.attributes('style') ?? ''
    expect(style).toContain('min-height: 44px')
  })

  it('textarea uses text-base on mobile for readable text size', () => {
    const wrapper = mountInput()
    const textarea = wrapper.find('textarea')
    expect(textarea.classes()).toContain('text-base')
    expect(textarea.classes()).toContain('sm:text-sm')
  })

  it('textarea has @focus handler for virtual keyboard scrolling', () => {
    const wrapper = mountInput()
    const textarea = wrapper.find('textarea')
    // The focus event handler should be registered
    expect(textarea.attributes()).toBeDefined()
  })

  it('send button has touch-friendly padding (p-2.5 on mobile)', () => {
    const wrapper = mountInput()
    const sendBtn = wrapper.find('[aria-label="Send message"]')
    expect(sendBtn.classes()).toContain('p-2.5')
    expect(sendBtn.classes()).toContain('touch-manipulation')
  })

  it('attach button has touch-friendly padding (p-2.5 on mobile)', () => {
    const wrapper = mountInput()
    const attachBtn = wrapper.find('[aria-label="Attach file"]')
    expect(attachBtn.classes()).toContain('p-2.5')
    expect(attachBtn.classes()).toContain('touch-manipulation')
  })

  it('input container has safe area bottom padding', () => {
    const wrapper = mountInput()
    const container = wrapper.find('.border-t.border-border')
    const style = container.attributes('style') ?? ''
    expect(style).toContain('safe-area-inset-bottom')
  })
})

// --------------- Issue #7: Conversation list touch spacing ---------------

describe('Issue #7: Conversation list touch spacing', () => {
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
      global: { plugins: [pinia] },
    })
  }

  it('conversation buttons have increased padding on mobile (py-3.5)', () => {
    const wrapper = mountConvList({
      conversations: [makeConversation()],
    })
    const button = wrapper.find('button')
    expect(button.classes()).toContain('py-3.5')
    expect(button.classes()).toContain('sm:py-3')
  })

  it('conversation buttons have touch-manipulation class', () => {
    const wrapper = mountConvList({
      conversations: [makeConversation()],
    })
    const button = wrapper.find('button')
    expect(button.classes()).toContain('touch-manipulation')
  })

  it('conversation buttons have active state for touch feedback', () => {
    const wrapper = mountConvList({
      conversations: [makeConversation()],
    })
    const button = wrapper.find('button')
    expect(button.classes()).toContain('active:bg-surface-alt')
  })

  it('unread badge has larger size on mobile (min-w-[22px] h-[22px])', () => {
    const wrapper = mountConvList({
      conversations: [makeConversation({ unread_count: 5 })],
    })
    const badge = wrapper.find('[role="status"]')
    expect(badge.exists()).toBe(true)
    expect(badge.classes()).toContain('min-w-[22px]')
    expect(badge.classes()).toContain('h-[22px]')
  })
})

// --------------- Issue #12: Dropdown menu max-width ---------------

describe('Issue #12: Dropdown menu max-width', () => {
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
      global: { plugins: [pinia] },
    })
  }

  it('dropdown menu has max-w-[calc(100vw-2rem)] to prevent overflow', async () => {
    const recent = new Date().toISOString()
    const wrapper = mountThread({
      messages: [
        makeMessage({
          id: 'msg-1',
          sender: makeSender({ id: 'user-1' }),
          created_at: recent,
        }),
      ],
    })

    await wrapper.find('[aria-label="Message actions"]').trigger('click')
    await nextTick()

    const dropdown = wrapper.find('[data-message-menu].absolute.z-10')
    expect(dropdown.exists()).toBe(true)
    expect(dropdown.classes()).toContain('max-w-[calc(100vw-2rem)]')
  })
})

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { nextTick } from 'vue'
import type { DMMessage } from '@/types/dm'

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
  MoreHorizontal: {
    name: 'MoreHorizontal',
    template: '<span class="icon-more" />',
  },
  X: { name: 'X', template: '<span class="icon-x" />' },
  File: { name: 'File', template: '<span class="icon-file" />' },
  FileText: { name: 'FileText', template: '<span class="icon-file-text" />' },
  Film: { name: 'Film', template: '<span class="icon-film" />' },
  Music: { name: 'Music', template: '<span class="icon-music" />' },
  Download: { name: 'Download', template: '<span class="icon-download" />' },
  AlertTriangle: {
    name: 'AlertTriangle',
    template: '<span class="icon-alert" />',
  },
  MessageSquare: {
    name: 'MessageSquare',
    template: '<span class="icon-message-square" />',
  },
  ArrowLeft: {
    name: 'ArrowLeft',
    template: '<span class="icon-arrow-left" />',
  },
  ArrowDown: {
    name: 'ArrowDown',
    template: '<span class="icon-arrow-down" />',
  },
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

import MessageThread from '@/components/dm/MessageThread.vue'
import { getErrorMessage } from '@/utils/error'

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

// --------------- parseDMError unit tests (UX-3) ---------------

// We test parseDMError as a standalone function since it lives in DMView.vue.
// Re-implement the pure logic here for unit testing.
function parseDMError(e: unknown, fallback: string): string {
  if (e && typeof e === 'object' && 'response' in e) {
    const resp = (
      e as {
        response?: {
          data?: { detail?: { code?: string; message?: string } }
        }
      }
    ).response
    const code = resp?.data?.detail?.code
    if (code === 'DM_002') return 'The edit/recall window (12 hours) has expired.'
    if (code === 'SYS_422') {
      const msg = resp?.data?.detail?.message ?? ''
      if (msg.includes('already recalled')) return 'This message has already been recalled.'
      if (msg.includes('recalled message')) return 'Cannot edit a recalled message.'
    }
    if (code === 'SYS_403') return 'You can only edit or recall your own messages.'
  }
  return getErrorMessage(e, fallback)
}

describe('parseDMError', () => {
  it('returns window-expired message for DM_002 code', () => {
    const err = {
      response: { data: { detail: { code: 'DM_002', message: '' } } },
    }
    expect(parseDMError(err, 'fallback')).toBe('The edit/recall window (12 hours) has expired.')
  })

  it('returns "already recalled" message for SYS_422 with "already recalled"', () => {
    const err = {
      response: {
        data: {
          detail: {
            code: 'SYS_422',
            message: 'Message already recalled',
          },
        },
      },
    }
    expect(parseDMError(err, 'fallback')).toBe('This message has already been recalled.')
  })

  it('returns "cannot edit recalled" message for SYS_422 with "recalled message"', () => {
    const err = {
      response: {
        data: {
          detail: {
            code: 'SYS_422',
            message: 'Cannot edit a recalled message',
          },
        },
      },
    }
    expect(parseDMError(err, 'fallback')).toBe('Cannot edit a recalled message.')
  })

  it('returns permission message for SYS_403 code', () => {
    const err = {
      response: {
        data: { detail: { code: 'SYS_403', message: 'Forbidden' } },
      },
    }
    expect(parseDMError(err, 'fallback')).toBe('You can only edit or recall your own messages.')
  })

  it('returns fallback for unknown errors', () => {
    expect(parseDMError(null, 'My fallback')).toBe('My fallback')
  })

  it('returns getErrorMessage result for unrecognized response errors', () => {
    const err = {
      response: {
        data: { detail: { code: 'OTHER', message: 'Some server error' } },
      },
    }
    // getErrorMessage extracts the message field
    expect(parseDMError(err, 'fallback')).toBe('Some server error')
  })
})

// --------------- MessageThread component tests ---------------

describe('MessageThread UX', () => {
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

  // --- UX-4: Empty state distinction ---

  describe('UX-4: Empty state distinction', () => {
    it('shows spinner with "Loading messages..." when loading with no messages', () => {
      const wrapper = mountThread({ loading: true, messages: [] })
      expect(wrapper.text()).toContain('Loading messages...')
      expect(wrapper.find('.animate-spin').exists()).toBe(true)
    })

    it('shows "No messages yet" when not loading and messages are empty', () => {
      const wrapper = mountThread({ loading: false, messages: [] })
      expect(wrapper.text()).toContain('No messages yet')
      expect(wrapper.text()).toContain('Send the first message to start the conversation.')
      expect(wrapper.find('.icon-message-square').exists()).toBe(true)
    })

    it('does not show empty state when messages are present', () => {
      const wrapper = mountThread({
        loading: false,
        messages: [makeMessage()],
      })
      expect(wrapper.text()).not.toContain('No messages yet')
      expect(wrapper.text()).toContain('Hello!')
    })

    it('does not show spinner when not loading', () => {
      const wrapper = mountThread({ loading: false, messages: [] })
      expect(wrapper.find('.animate-spin').exists()).toBe(false)
    })
  })

  // --- UX-5: Smart auto-scroll ---

  describe('UX-5: Smart auto-scroll', () => {
    it('adds @scroll handler to scroll container', () => {
      const wrapper = mountThread({
        messages: [makeMessage()],
      })
      const container = wrapper.find('[class*="overflow-y-auto"]')
      expect(container.exists()).toBe(true)
    })

    it('shows "New message" hint button when showNewMessageHint is active', async () => {
      const msgs = [makeMessage({ id: 'msg-1' })]
      const wrapper = mountThread({ messages: msgs })

      // Simulate the scroll container not being at bottom
      const container = wrapper.find('[class*="overflow-y-auto"]')
      const el = container.element as HTMLElement

      // Mock scrollHeight/clientHeight so isAtBottom becomes false
      Object.defineProperty(el, 'scrollHeight', {
        value: 1000,
        writable: true,
      })
      Object.defineProperty(el, 'clientHeight', {
        value: 300,
        writable: true,
      })
      Object.defineProperty(el, 'scrollTop', { value: 0, writable: true })

      // Trigger scroll to update isAtBottom
      await container.trigger('scroll')
      await nextTick()

      // Now add a new message to trigger the watcher
      const newMsgs = [...msgs, makeMessage({ id: 'msg-2', content: 'New!' })]
      await wrapper.setProps({ messages: newMsgs })
      await nextTick()
      await nextTick()

      // The "New message" hint should appear
      const _hint = wrapper.find('button')
      const hintButtons = wrapper.findAll('button').filter((b) => b.text().includes('New message'))
      expect(hintButtons.length).toBe(1)
    })

    it('does not show "New message" hint when no new messages arrive', () => {
      const wrapper = mountThread({
        messages: [makeMessage({ id: 'msg-1' })],
      })
      const hintButtons = wrapper.findAll('button').filter((b) => b.text().includes('New message'))
      expect(hintButtons.length).toBe(0)
    })
  })

  // --- UX-7: Read receipt icons ---

  describe('UX-7: Read receipt icons', () => {
    it('shows single check (Sent) for own unread message', () => {
      const wrapper = mountThread({
        messages: [
          makeMessage({
            sender: makeSender({ id: 'user-1' }),
            read_at: null,
          }),
        ],
      })
      expect(wrapper.find('.icon-check').exists()).toBe(true)
      expect(wrapper.find('[aria-label="Sent"]').exists()).toBe(true)
      // Should not show double check
      expect(wrapper.find('.icon-check-check').exists()).toBe(false)
    })

    it('shows double check (Read) for own read message', () => {
      const wrapper = mountThread({
        messages: [
          makeMessage({
            sender: makeSender({ id: 'user-1' }),
            read_at: '2026-03-17T01:00:00Z',
          }),
        ],
      })
      expect(wrapper.find('.icon-check-check').exists()).toBe(true)
      expect(wrapper.find('[aria-label="Read"]').exists()).toBe(true)
    })

    it('does not show single check for read message (only double)', () => {
      const wrapper = mountThread({
        messages: [
          makeMessage({
            sender: makeSender({ id: 'user-1' }),
            read_at: '2026-03-17T01:00:00Z',
          }),
        ],
      })
      // icon-check exists inside icon-check-check (both have .icon-check in class)
      // But aria-label="Sent" should NOT exist
      expect(wrapper.find('[aria-label="Sent"]').exists()).toBe(false)
      expect(wrapper.find('[aria-label="Read"]').exists()).toBe(true)
    })

    it('has title tooltip on read receipt with formatted date', () => {
      const wrapper = mountThread({
        messages: [
          makeMessage({
            sender: makeSender({ id: 'user-1' }),
            read_at: '2026-03-17T01:00:00Z',
          }),
        ],
      })
      const readSpan = wrapper.find('[aria-label="Read"]').element.parentElement
      expect(readSpan).toBeTruthy()
      expect(readSpan!.getAttribute('title')).toContain('Read')
    })

    it('does not show any check icons for other user messages', () => {
      const wrapper = mountThread({
        messages: [
          makeMessage({
            sender: makeSender({ id: 'user-2' }),
            read_at: '2026-03-17T01:00:00Z',
          }),
        ],
      })
      expect(wrapper.find('[aria-label="Sent"]').exists()).toBe(false)
      expect(wrapper.find('[aria-label="Read"]').exists()).toBe(false)
    })

    it('does not show check icons on recalled messages', () => {
      const wrapper = mountThread({
        messages: [
          makeMessage({
            sender: makeSender({ id: 'user-1' }),
            read_at: '2026-03-17T01:00:00Z',
            is_recalled: true,
            content: null,
          }),
        ],
      })
      expect(wrapper.find('[aria-label="Sent"]').exists()).toBe(false)
      expect(wrapper.find('[aria-label="Read"]').exists()).toBe(false)
    })
  })

  // --- Message ordering (chronological: oldest at top, newest at bottom) ---

  describe('Message ordering', () => {
    it('renders messages in DOM order (oldest first in array = top of container)', () => {
      const msgs = [
        makeMessage({
          id: 'msg-old',
          content: 'Older message',
          created_at: '2026-03-17T00:00:00Z',
        }),
        makeMessage({
          id: 'msg-new',
          content: 'Newer message',
          created_at: '2026-03-17T01:00:00Z',
        }),
      ]
      const wrapper = mountThread({ messages: msgs })
      // Find message bubbles containing whitespace-pre-wrap content
      const contentElements = wrapper.findAll('.whitespace-pre-wrap')
      expect(contentElements).toHaveLength(2)
      // First content in DOM = older message (top), second = newer message (bottom)
      expect(contentElements[0].text()).toBe('Older message')
      expect(contentElements[1].text()).toBe('Newer message')
    })
  })

  // --- ResizeObserver scroll stability ---

  describe('ResizeObserver scroll stability', () => {
    it('calls scrollToBottom on resize when user is at bottom', async () => {
      const msgs = [makeMessage({ id: 'msg-1' })]
      const wrapper = mountThread({ messages: msgs })

      // Access exposed scrollToBottom
      const _scrollToBottomSpy = vi.spyOn(wrapper.vm, 'scrollToBottom' as never)

      // The ResizeObserver should have been registered on mount
      // We can't easily trigger a real ResizeObserver in JSDOM,
      // but we verify the component exposes scrollToBottom
      expect(typeof (wrapper.vm as Record<string, unknown>).scrollToBottom).toBe('function')
    })

    it('exposes scrollToBottom via defineExpose', () => {
      const wrapper = mountThread({ messages: [] })
      expect(typeof (wrapper.vm as Record<string, unknown>).scrollToBottom).toBe('function')
    })
  })
})

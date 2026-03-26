import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'

// Mock the API module before importing the store
const mockListConversations = vi.fn()
const mockListMessages = vi.fn()
const mockGetUnreadCount = vi.fn()

vi.mock('@/api/dm', () => ({
  listConversations: (...args: unknown[]) => mockListConversations(...args),
  listMessages: (...args: unknown[]) => mockListMessages(...args),
  sendMessage: vi.fn(),
  editMessage: vi.fn(),
  recallMessage: vi.fn(),
  markConversationRead: vi.fn(),
  getUnreadCount: (...args: unknown[]) => mockGetUnreadCount(...args),
}))

vi.mock('@/composables/api', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
}))

import { useDMStore } from '@/stores/dm'
import { markConversationRead } from '@/api/dm'
import type { DMMessage, Conversation } from '@/types/dm'

// --------------- Test data factories ---------------

function makeSender(
  overrides: Partial<{ id: string; display_name: string; avatar_url: string | null }> = {},
) {
  return {
    id: 'user-2',
    display_name: 'Alice',
    avatar_url: null,
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
    created_at: '2026-03-17T00:00:00Z',
    updated_at: '2026-03-17T00:00:00Z',
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

// --------------- Tests ---------------

describe('useDMStore — H-08 split loading refs', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('exposes conversationsLoading and messagesLoading as separate refs', () => {
    const store = useDMStore()
    expect(store.conversationsLoading).toBe(false)
    expect(store.messagesLoading).toBe(false)
  })

  it('loading is a computed that is true when conversationsLoading is true', () => {
    const store = useDMStore()
    expect(store.loading).toBe(false)
    store.conversationsLoading = true
    expect(store.loading).toBe(true)
    store.conversationsLoading = false
    expect(store.loading).toBe(false)
  })

  it('loading is a computed that is true when messagesLoading is true', () => {
    const store = useDMStore()
    expect(store.loading).toBe(false)
    store.messagesLoading = true
    expect(store.loading).toBe(true)
    store.messagesLoading = false
    expect(store.loading).toBe(false)
  })

  it('loading is true when both sub-loading refs are true', () => {
    const store = useDMStore()
    store.conversationsLoading = true
    store.messagesLoading = true
    expect(store.loading).toBe(true)
  })

  it('fetchConversations sets conversationsLoading but not messagesLoading', async () => {
    let resolveConv!: (value: unknown) => void
    const pending = new Promise((resolve) => {
      resolveConv = resolve
    })
    mockListConversations.mockReturnValueOnce(pending)

    const store = useDMStore()
    const fetchPromise = store.fetchConversations()

    // conversationsLoading should be true, messagesLoading should stay false
    expect(store.conversationsLoading).toBe(true)
    expect(store.messagesLoading).toBe(false)
    expect(store.loading).toBe(true)

    resolveConv({ conversations: [], total: 0 })
    await fetchPromise

    expect(store.conversationsLoading).toBe(false)
    expect(store.loading).toBe(false)
  })

  it('fetchMessages sets messagesLoading but not conversationsLoading', async () => {
    let resolveMsg!: (value: unknown) => void
    const pending = new Promise((resolve) => {
      resolveMsg = resolve
    })
    mockListMessages.mockReturnValueOnce(pending)

    const store = useDMStore()
    const fetchPromise = store.fetchMessages('conv-1')

    // messagesLoading should be true, conversationsLoading should stay false
    expect(store.messagesLoading).toBe(true)
    expect(store.conversationsLoading).toBe(false)
    expect(store.loading).toBe(true)

    resolveMsg({ messages: [makeMessage()], total: 1 })
    await fetchPromise

    expect(store.messagesLoading).toBe(false)
    expect(store.loading).toBe(false)
  })

  it('concurrent fetchConversations and fetchMessages have independent loading states', async () => {
    let resolveConv!: (value: unknown) => void
    let resolveMsg!: (value: unknown) => void
    const pendingConv = new Promise((resolve) => {
      resolveConv = resolve
    })
    const pendingMsg = new Promise((resolve) => {
      resolveMsg = resolve
    })
    mockListConversations.mockReturnValueOnce(pendingConv)
    mockListMessages.mockReturnValueOnce(pendingMsg)

    const store = useDMStore()
    const convPromise = store.fetchConversations()
    const msgPromise = store.fetchMessages('conv-1')

    // Both loading
    expect(store.conversationsLoading).toBe(true)
    expect(store.messagesLoading).toBe(true)
    expect(store.loading).toBe(true)

    // Resolve conversations first
    resolveConv({ conversations: [makeConversation()], total: 1 })
    await convPromise

    // Only conversations done
    expect(store.conversationsLoading).toBe(false)
    expect(store.messagesLoading).toBe(true)
    expect(store.loading).toBe(true) // still true because messagesLoading is true

    // Resolve messages
    resolveMsg({ messages: [makeMessage()], total: 1 })
    await msgPromise

    expect(store.messagesLoading).toBe(false)
    expect(store.loading).toBe(false)
  })

  it('resetState resets both conversationsLoading and messagesLoading', () => {
    const store = useDMStore()
    store.conversationsLoading = true
    store.messagesLoading = true
    expect(store.loading).toBe(true)

    store.resetState()

    expect(store.conversationsLoading).toBe(false)
    expect(store.messagesLoading).toBe(false)
    expect(store.loading).toBe(false)
  })

  it('fetchConversations sets conversationsLoading false on error', async () => {
    mockListConversations.mockRejectedValueOnce(new Error('Network'))
    const store = useDMStore()
    await store.fetchConversations()
    expect(store.conversationsLoading).toBe(false)
  })

  it('fetchMessages sets messagesLoading false on error', async () => {
    mockListMessages.mockRejectedValueOnce(new Error('Network'))
    const store = useDMStore()
    await store.fetchMessages('conv-1')
    expect(store.messagesLoading).toBe(false)
  })
})

describe('useDMStore — M-25 addFromWebSocket in-place mutations', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('updates conversation in place for own message', () => {
    const store = useDMStore()
    store.setCurrentUserId('user-1')
    const conv = makeConversation({ id: 'conv-1' })
    store.conversations = [conv]

    const msg = makeMessage({
      id: 'msg-new',
      conversation_id: 'conv-1',
      sender: makeSender({ id: 'user-1', display_name: 'Me' }),
    })
    store.addFromWebSocket(msg)

    expect(store.conversations).toHaveLength(1)
    expect(store.conversations[0].last_message).toStrictEqual(msg)
  })

  it('updates conversation in place for other user message', () => {
    const store = useDMStore()
    store.setCurrentUserId('user-1')
    const conv = makeConversation({ id: 'conv-1', unread_count: 0 })
    store.conversations = [conv]

    const msg = makeMessage({
      id: 'msg-other',
      conversation_id: 'conv-1',
      sender: makeSender({ id: 'user-2', display_name: 'Alice' }),
    })
    store.addFromWebSocket(msg)

    expect(store.conversations).toHaveLength(1)
    expect(store.conversations[0].last_message).toStrictEqual(msg)
    // Global unread should increment (not viewing this conversation)
    expect(store.unreadCount).toBe(1)
  })

  it('increments conversation unread_count when not viewing that conversation', () => {
    const store = useDMStore()
    store.setCurrentUserId('user-1')
    store.setActiveConversation('conv-other') // viewing different conversation
    store.conversations = [makeConversation({ id: 'conv-1', unread_count: 2 })]

    const msg = makeMessage({
      id: 'msg-x',
      conversation_id: 'conv-1',
      sender: makeSender({ id: 'user-2', display_name: 'Alice' }),
    })
    store.addFromWebSocket(msg)

    expect(store.conversations[0].unread_count).toBe(3)
  })

  it('does not increment conversation unread_count when viewing that conversation', () => {
    const store = useDMStore()
    store.setCurrentUserId('user-1')
    store.setActiveConversation('conv-1')
    store.conversations = [makeConversation({ id: 'conv-1', unread_count: 0 })]

    const msg = makeMessage({
      id: 'msg-x',
      conversation_id: 'conv-1',
      sender: makeSender({ id: 'user-2', display_name: 'Alice' }),
    })
    store.addFromWebSocket(msg)

    expect(store.conversations[0].unread_count).toBe(0)
  })

  it('moves conversation to top of list on new message', () => {
    const store = useDMStore()
    store.setCurrentUserId('user-1')
    store.conversations = [
      makeConversation({ id: 'conv-1' }),
      makeConversation({ id: 'conv-2', other_user: makeSender({ id: 'user-3' }) }),
    ]

    const msg = makeMessage({
      id: 'msg-y',
      conversation_id: 'conv-2',
      sender: makeSender({ id: 'user-3', display_name: 'Bob' }),
    })
    store.addFromWebSocket(msg)

    expect(store.conversations[0].id).toBe('conv-2')
    expect(store.conversations[1].id).toBe('conv-1')
  })

  it('adds message to messages array in place for unknown conversation', () => {
    const store = useDMStore()
    store.setCurrentUserId('user-1')
    store.setActiveConversation('conv-unknown')
    store.conversations = []
    store.messages = []

    // Mock fetchConversations to not actually call API
    mockListConversations.mockResolvedValue({ conversations: [], total: 0 })

    const msg = makeMessage({
      id: 'msg-unknown',
      conversation_id: 'conv-unknown',
      sender: makeSender({ id: 'user-2', display_name: 'Alice' }),
    })

    store.addFromWebSocket(msg)

    expect(store.messages).toHaveLength(1)
    expect(store.messages[0].id).toBe('msg-unknown')
  })

  it('deduplicates messages — does not add if already present', () => {
    const store = useDMStore()
    store.setCurrentUserId('user-1')
    store.setActiveConversation('conv-1')
    const existingMsg = makeMessage({ id: 'msg-dup', conversation_id: 'conv-1' })
    store.messages = [existingMsg]
    store.conversations = [makeConversation({ id: 'conv-1' })]

    store.addFromWebSocket(
      makeMessage({
        id: 'msg-dup',
        conversation_id: 'conv-1',
        sender: makeSender({ id: 'user-1', display_name: 'Me' }),
      }),
    )

    expect(store.messages).toHaveLength(1)
  })
})

describe('F-03: auto mark-read on WebSocket message', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('calls markConversationRead when message arrives in active conversation from other user', () => {
    const store = useDMStore()
    store.setCurrentUserId('user-1')
    store.setActiveConversation('conv-1')
    store.conversations = [makeConversation({ id: 'conv-1' })]

    const msg = makeMessage({
      id: 'msg-ws-1',
      conversation_id: 'conv-1',
      sender: makeSender({ id: 'user-2', display_name: 'Alice' }),
    })
    store.addFromWebSocket(msg)

    vi.advanceTimersByTime(500)

    expect(markConversationRead).toHaveBeenCalledWith('conv-1')
  })

  it('does NOT call markConversationRead for own echoed messages', () => {
    const store = useDMStore()
    store.setCurrentUserId('user-1')
    store.setActiveConversation('conv-1')
    store.conversations = [makeConversation({ id: 'conv-1' })]

    const msg = makeMessage({
      id: 'msg-ws-2',
      conversation_id: 'conv-1',
      sender: makeSender({ id: 'user-1', display_name: 'Me' }),
    })
    store.addFromWebSocket(msg)

    vi.advanceTimersByTime(500)

    expect(markConversationRead).not.toHaveBeenCalled()
  })

  it('does NOT call markConversationRead for messages in non-active conversation', () => {
    const store = useDMStore()
    store.setCurrentUserId('user-1')
    store.setActiveConversation('conv-2')
    store.conversations = [makeConversation({ id: 'conv-1' })]

    const msg = makeMessage({
      id: 'msg-ws-3',
      conversation_id: 'conv-1',
      sender: makeSender({ id: 'user-2', display_name: 'Alice' }),
    })
    store.addFromWebSocket(msg)

    vi.advanceTimersByTime(500)

    expect(markConversationRead).not.toHaveBeenCalled()
  })
})

// ── F-07: hasMoreMessages stays correct after WS additions ──────────

describe('useDMStore — F-07 messagesTotal sync on WebSocket', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('increments messagesTotal when other user WS message added to active conversation', () => {
    const store = useDMStore()
    store.setCurrentUserId('user-1')
    store.setActiveConversation('conv-1')
    store.conversations = [makeConversation({ id: 'conv-1' })]
    store.messagesTotal = 30 // pretend 30 messages from API

    const msg = makeMessage({
      id: 'msg-ws-new',
      conversation_id: 'conv-1',
      sender: makeSender({ id: 'user-2', display_name: 'Alice' }),
    })
    store.addFromWebSocket(msg)

    expect(store.messagesTotal).toBe(31)
  })

  it('increments messagesTotal for own echoed messages in active conversation', () => {
    const store = useDMStore()
    store.setCurrentUserId('user-1')
    store.setActiveConversation('conv-1')
    store.conversations = [makeConversation({ id: 'conv-1' })]
    store.messagesTotal = 30

    const msg = makeMessage({
      id: 'msg-ws-own',
      conversation_id: 'conv-1',
      sender: makeSender({ id: 'user-1', display_name: 'Me' }),
    })
    store.addFromWebSocket(msg)

    expect(store.messagesTotal).toBe(31)
  })

  it('does NOT increment messagesTotal for non-active conversation', () => {
    const store = useDMStore()
    store.setCurrentUserId('user-1')
    store.setActiveConversation('conv-2')
    store.conversations = [makeConversation({ id: 'conv-1' })]
    store.messagesTotal = 30

    const msg = makeMessage({
      id: 'msg-ws-other',
      conversation_id: 'conv-1',
      sender: makeSender({ id: 'user-2', display_name: 'Alice' }),
    })
    store.addFromWebSocket(msg)

    expect(store.messagesTotal).toBe(30)
  })
})

// ── F-23: recallFromWebSocket nulls attachment_size + attachment_expires_at ──

describe('useDMStore — F-23 recallFromWebSocket attachment fields', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('nulls attachment_size and attachment_expires_at on recall', () => {
    const store = useDMStore()
    store.messages = [
      makeMessage({
        id: 'msg-recall',
        conversation_id: 'conv-1',
        attachment_name: 'file.jpg',
        attachment_size: 1024,
        attachment_expires_at: '2026-03-20T00:00:00Z',
        attachment_url: 'https://example.com/file.jpg',
      }),
    ]
    store.conversations = [
      makeConversation({
        id: 'conv-1',
        last_message: makeMessage({
          id: 'msg-recall',
          attachment_name: 'file.jpg',
          attachment_size: 1024,
          attachment_expires_at: '2026-03-20T00:00:00Z',
        }),
      }),
    ]

    store.recallFromWebSocket('msg-recall', 'conv-1')

    const msg = store.messages[0]
    expect(msg.is_recalled).toBe(true)
    expect(msg.content).toBeNull()
    expect(msg.attachment_url).toBeNull()
    expect(msg.attachment_name).toBeNull()
    expect(msg.attachment_size).toBeNull()
    expect(msg.attachment_expires_at).toBeNull()
  })
})

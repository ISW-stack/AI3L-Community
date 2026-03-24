import { describe, it, expect, vi, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'

// Mock the API module before importing the store
const mockListConversations = vi.fn()
const mockListMessages = vi.fn()
const mockSendMessage = vi.fn()
const mockEditMessage = vi.fn()
const mockRecallMessage = vi.fn()
const mockMarkConversationRead = vi.fn()
const mockGetUnreadCount = vi.fn()

vi.mock('@/api/dm', () => ({
  listConversations: (...args: unknown[]) => mockListConversations(...args),
  listMessages: (...args: unknown[]) => mockListMessages(...args),
  sendMessage: (...args: unknown[]) => mockSendMessage(...args),
  editMessage: (...args: unknown[]) => mockEditMessage(...args),
  recallMessage: (...args: unknown[]) => mockRecallMessage(...args),
  markConversationRead: (...args: unknown[]) => mockMarkConversationRead(...args),
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

describe('useDMStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  // ============ fetchUnreadCount ============

  describe('fetchUnreadCount', () => {
    it('sets unread count from API response', async () => {
      mockGetUnreadCount.mockResolvedValueOnce({ unread_count: 3 })
      const store = useDMStore()
      await store.fetchUnreadCount()
      expect(store.unreadCount).toBe(3)
    })

    it('sets unread count to zero when API returns 0', async () => {
      mockGetUnreadCount.mockResolvedValueOnce({ unread_count: 0 })
      const store = useDMStore()
      store.unreadCount = 5
      await store.fetchUnreadCount()
      expect(store.unreadCount).toBe(0)
    })

    it('handles API error gracefully without throwing', async () => {
      mockGetUnreadCount.mockRejectedValueOnce(new Error('Network error'))
      const store = useDMStore()
      await expect(store.fetchUnreadCount()).resolves.toBeUndefined()
      expect(store.unreadCount).toBe(0)
    })

    it('preserves existing unread count on error', async () => {
      const store = useDMStore()
      store.unreadCount = 7
      mockGetUnreadCount.mockRejectedValueOnce(new Error('500'))
      await store.fetchUnreadCount()
      expect(store.unreadCount).toBe(7)
    })

    it('logs error to console on failure', async () => {
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
      mockGetUnreadCount.mockRejectedValueOnce(new Error('Boom'))
      const store = useDMStore()
      await store.fetchUnreadCount()
      expect(consoleSpy).toHaveBeenCalled()
      consoleSpy.mockRestore()
    })
  })

  // ============ fetchConversations ============

  describe('fetchConversations', () => {
    it('populates conversations array from API', async () => {
      const convos = [makeConversation({ id: 'conv-1' }), makeConversation({ id: 'conv-2' })]
      mockListConversations.mockResolvedValueOnce({ conversations: convos, total: 2 })
      const store = useDMStore()
      await store.fetchConversations()
      expect(store.conversations).toHaveLength(2)
      expect(store.conversations[0].id).toBe('conv-1')
    })

    it('sets conversationsTotal from API', async () => {
      mockListConversations.mockResolvedValueOnce({ conversations: [], total: 42 })
      const store = useDMStore()
      await store.fetchConversations()
      expect(store.conversationsTotal).toBe(42)
    })

    it('sets loading state to true while fetching', async () => {
      let resolvePromise: (value: unknown) => void
      const pending = new Promise((resolve) => {
        resolvePromise = resolve
      })
      mockListConversations.mockReturnValueOnce(pending)

      const store = useDMStore()
      const fetchPromise = store.fetchConversations()
      expect(store.loading).toBe(true)

      resolvePromise!({ conversations: [], total: 0 })
      await fetchPromise
      expect(store.loading).toBe(false)
    })

    it('sets loading to false after successful fetch', async () => {
      mockListConversations.mockResolvedValueOnce({ conversations: [], total: 0 })
      const store = useDMStore()
      await store.fetchConversations()
      expect(store.loading).toBe(false)
    })

    it('sets loading to false even on error', async () => {
      mockListConversations.mockRejectedValueOnce(new Error('Fail'))
      const store = useDMStore()
      await store.fetchConversations()
      expect(store.loading).toBe(false)
    })

    it('sets error string on failure', async () => {
      mockListConversations.mockRejectedValueOnce(new Error('Server error'))
      const store = useDMStore()
      await store.fetchConversations()
      expect(store.error).toBeTruthy()
    })

    it('clears error on new fetch attempt', async () => {
      const store = useDMStore()
      store.error = 'Previous error'
      mockListConversations.mockResolvedValueOnce({ conversations: [], total: 0 })
      await store.fetchConversations()
      expect(store.error).toBeNull()
    })

    it('replaces existing conversations on re-fetch', async () => {
      const store = useDMStore()
      mockListConversations.mockResolvedValueOnce({
        conversations: [makeConversation({ id: 'old-1' })],
        total: 1,
      })
      await store.fetchConversations()
      expect(store.conversations).toHaveLength(1)

      mockListConversations.mockResolvedValueOnce({
        conversations: [makeConversation({ id: 'new-1' }), makeConversation({ id: 'new-2' })],
        total: 2,
      })
      await store.fetchConversations()
      expect(store.conversations).toHaveLength(2)
      expect(store.conversations[0].id).toBe('new-1')
    })

    it('passes page and pageSize to the API', async () => {
      mockListConversations.mockResolvedValueOnce({ conversations: [], total: 0 })
      const store = useDMStore()
      await store.fetchConversations(3, 15)
      expect(mockListConversations).toHaveBeenCalledWith({ page: 3, page_size: 15 })
    })
  })

  // ============ fetchMessages ============

  describe('fetchMessages', () => {
    it('populates messages array from API on page 1 in chronological order', async () => {
      // Backend returns newest-first (DESC); store should reverse to chronological (ASC)
      const msgs = [makeMessage({ id: 'msg-2' }), makeMessage({ id: 'msg-1' })]
      mockListMessages.mockResolvedValueOnce({ messages: msgs, total: 2 })
      const store = useDMStore()
      await store.fetchMessages('conv-1')
      expect(store.messages).toHaveLength(2)
      // After reverse: msg-1 (older) first, msg-2 (newer) last
      expect(store.messages[0].id).toBe('msg-1')
      expect(store.messages[1].id).toBe('msg-2')
    })

    it('sets messagesTotal from API', async () => {
      mockListMessages.mockResolvedValueOnce({ messages: [], total: 50 })
      const store = useDMStore()
      await store.fetchMessages('conv-1')
      expect(store.messagesTotal).toBe(50)
    })

    it('prepends older messages on page > 1 in chronological order', async () => {
      // Current messages already in chronological order
      const store = useDMStore()
      store.messages = [makeMessage({ id: 'msg-3' }), makeMessage({ id: 'msg-4' })]

      // Backend returns DESC for page 2: msg-2 (newer), msg-1 (older)
      mockListMessages.mockResolvedValueOnce({
        messages: [makeMessage({ id: 'msg-2' }), makeMessage({ id: 'msg-1' })],
        total: 4,
      })
      await store.fetchMessages('conv-1', 2)

      expect(store.messages).toHaveLength(4)
      // After reverse + prepend: msg-1, msg-2, msg-3, msg-4
      expect(store.messages[0].id).toBe('msg-1')
      expect(store.messages[1].id).toBe('msg-2')
      expect(store.messages[2].id).toBe('msg-3')
      expect(store.messages[3].id).toBe('msg-4')
    })

    it('does not add duplicates on page > 1', async () => {
      const store = useDMStore()
      store.messages = [makeMessage({ id: 'msg-2' }), makeMessage({ id: 'msg-3' })]

      // Backend returns DESC: msg-2 (newer), msg-1 (older) → reversed to msg-1, msg-2
      mockListMessages.mockResolvedValueOnce({
        messages: [makeMessage({ id: 'msg-2' }), makeMessage({ id: 'msg-1' })],
        total: 3,
      })
      await store.fetchMessages('conv-1', 2)

      // msg-2 should not be duplicated
      const ids = store.messages.map((m) => m.id)
      expect(ids.filter((id) => id === 'msg-2')).toHaveLength(1)
    })

    it('sets loading state correctly during fetch', async () => {
      let resolvePromise: (value: unknown) => void
      const pending = new Promise((resolve) => {
        resolvePromise = resolve
      })
      mockListMessages.mockReturnValueOnce(pending)

      const store = useDMStore()
      const fetchPromise = store.fetchMessages('conv-1')
      expect(store.loading).toBe(true)

      resolvePromise!({ messages: [], total: 0 })
      await fetchPromise
      expect(store.loading).toBe(false)
    })

    it('sets error on failure', async () => {
      mockListMessages.mockRejectedValueOnce(new Error('Network'))
      const store = useDMStore()
      await store.fetchMessages('conv-1')
      expect(store.error).toBeTruthy()
      expect(store.loading).toBe(false)
    })

    it('passes conversation ID and params to the API', async () => {
      mockListMessages.mockResolvedValueOnce({ messages: [], total: 0 })
      const store = useDMStore()
      await store.fetchMessages('conv-abc', 2, 10)
      expect(mockListMessages).toHaveBeenCalledWith('conv-abc', { page: 2, page_size: 10 })
    })
  })

  // ============ fetchMessages chronological ordering ============

  describe('fetchMessages chronological ordering', () => {
    it('reverses DESC backend response to chronological ASC on page 1', async () => {
      // Backend: [newest, ..., oldest] → Store: [oldest, ..., newest]
      const msgs = [
        makeMessage({ id: 'msg-3', created_at: '2026-03-17T03:00:00Z' }),
        makeMessage({ id: 'msg-2', created_at: '2026-03-17T02:00:00Z' }),
        makeMessage({ id: 'msg-1', created_at: '2026-03-17T01:00:00Z' }),
      ]
      mockListMessages.mockResolvedValueOnce({ messages: msgs, total: 3 })
      const store = useDMStore()
      await store.fetchMessages('conv-1')

      expect(store.messages.map((m) => m.id)).toEqual(['msg-1', 'msg-2', 'msg-3'])
    })

    it('reverses and prepends older page in chronological order', async () => {
      const store = useDMStore()
      // Current page 1 already chronological
      store.messages = [
        makeMessage({ id: 'msg-4', created_at: '2026-03-17T04:00:00Z' }),
        makeMessage({ id: 'msg-5', created_at: '2026-03-17T05:00:00Z' }),
      ]

      // Page 2 from backend (DESC): msg-3, msg-2
      mockListMessages.mockResolvedValueOnce({
        messages: [
          makeMessage({ id: 'msg-3', created_at: '2026-03-17T03:00:00Z' }),
          makeMessage({ id: 'msg-2', created_at: '2026-03-17T02:00:00Z' }),
        ],
        total: 5,
      })
      await store.fetchMessages('conv-1', 2)

      // Result: msg-2, msg-3, msg-4, msg-5 (chronological)
      expect(store.messages.map((m) => m.id)).toEqual(['msg-2', 'msg-3', 'msg-4', 'msg-5'])
    })

    it('does not mutate the original API response array', async () => {
      const original = [makeMessage({ id: 'msg-2' }), makeMessage({ id: 'msg-1' })]
      const apiResponse = { messages: [...original], total: 2 }
      mockListMessages.mockResolvedValueOnce(apiResponse)
      const store = useDMStore()
      await store.fetchMessages('conv-1')

      // Original array order preserved (not reversed in-place)
      expect(apiResponse.messages[0].id).toBe('msg-2')
      expect(apiResponse.messages[1].id).toBe('msg-1')
    })
  })

  // ============ addFromWebSocket (NEW_DM) ============

  describe('addFromWebSocket', () => {
    it('adds message to messages array when viewing that conversation', () => {
      const store = useDMStore()
      store.activeConversationId = 'conv-1'
      store.conversations = [makeConversation({ id: 'conv-1' })]
      store.messages = [makeMessage({ id: 'existing' })]

      const newMsg = makeMessage({ id: 'new-msg', conversation_id: 'conv-1' })
      store.addFromWebSocket(newMsg)

      expect(store.messages).toHaveLength(2)
      expect(store.messages.some((m) => m.id === 'new-msg')).toBe(true)
    })

    it('does NOT add duplicate message with same id', () => {
      const store = useDMStore()
      store.activeConversationId = 'conv-1'
      store.conversations = [makeConversation({ id: 'conv-1' })]
      const msg = makeMessage({ id: 'dup-1', conversation_id: 'conv-1' })
      store.messages = [msg]

      store.addFromWebSocket(msg)
      expect(store.messages).toHaveLength(1)
    })

    it('increments unreadCount when NOT viewing that conversation', () => {
      const store = useDMStore()
      store.activeConversationId = 'conv-other'
      store.conversations = [makeConversation({ id: 'conv-1' })]
      store.unreadCount = 0

      const msg = makeMessage({ id: 'msg-x', conversation_id: 'conv-1' })
      store.addFromWebSocket(msg)
      expect(store.unreadCount).toBe(1)
    })

    it('does NOT increment unreadCount when viewing that conversation', () => {
      const store = useDMStore()
      store.activeConversationId = 'conv-1'
      store.conversations = [makeConversation({ id: 'conv-1' })]
      store.unreadCount = 0

      const msg = makeMessage({ id: 'msg-x', conversation_id: 'conv-1' })
      store.addFromWebSocket(msg)
      expect(store.unreadCount).toBe(0)
    })

    it('moves conversation to top of list', () => {
      const store = useDMStore()
      store.conversations = [
        makeConversation({ id: 'conv-1' }),
        makeConversation({ id: 'conv-2' }),
        makeConversation({ id: 'conv-3' }),
      ]

      const msg = makeMessage({ id: 'msg-new', conversation_id: 'conv-3' })
      store.addFromWebSocket(msg)

      expect(store.conversations[0].id).toBe('conv-3')
    })

    it('updates conversation last_message', () => {
      const store = useDMStore()
      store.conversations = [makeConversation({ id: 'conv-1', last_message: null })]

      const msg = makeMessage({ id: 'msg-new', conversation_id: 'conv-1', content: 'New!' })
      store.addFromWebSocket(msg)

      expect(store.conversations[0].last_message).toBeTruthy()
      expect(store.conversations[0].last_message!.content).toBe('New!')
    })

    it('updates conversation updated_at timestamp', () => {
      const store = useDMStore()
      store.conversations = [makeConversation({ id: 'conv-1', updated_at: '2026-01-01T00:00:00Z' })]

      const msg = makeMessage({
        id: 'msg-new',
        conversation_id: 'conv-1',
        created_at: '2026-03-17T12:00:00Z',
      })
      store.addFromWebSocket(msg)

      expect(store.conversations[0].updated_at).toBe('2026-03-17T12:00:00Z')
    })

    it('does not add message to messages array if viewing different conversation', () => {
      const store = useDMStore()
      store.activeConversationId = 'conv-other'
      store.conversations = [makeConversation({ id: 'conv-1' })]
      store.messages = []

      const msg = makeMessage({ id: 'msg-1', conversation_id: 'conv-1' })
      store.addFromWebSocket(msg)

      expect(store.messages).toHaveLength(0)
    })

    it('increments conversation unread_count when not active', () => {
      const store = useDMStore()
      store.activeConversationId = 'conv-other'
      store.conversations = [makeConversation({ id: 'conv-1', unread_count: 2 })]

      const msg = makeMessage({ id: 'msg-1', conversation_id: 'conv-1' })
      store.addFromWebSocket(msg)

      expect(store.conversations[0].unread_count).toBe(3)
    })

    it('does not increment conversation unread_count when active', () => {
      const store = useDMStore()
      store.activeConversationId = 'conv-1'
      store.conversations = [makeConversation({ id: 'conv-1', unread_count: 0 })]

      const msg = makeMessage({ id: 'msg-1', conversation_id: 'conv-1' })
      store.addFromWebSocket(msg)

      expect(store.conversations[0].unread_count).toBe(0)
    })
  })

  // ============ updateFromWebSocket (DM_EDITED) ============

  describe('updateFromWebSocket', () => {
    it('replaces message in messages array', () => {
      const store = useDMStore()
      store.messages = [makeMessage({ id: 'msg-1', content: 'Original' })]

      const updated = makeMessage({ id: 'msg-1', content: 'Edited!', is_edited: true })
      store.updateFromWebSocket(updated)

      expect(store.messages[0].content).toBe('Edited!')
      expect(store.messages[0].is_edited).toBe(true)
    })

    it('updates last_message in conversations if it matches', () => {
      const lastMsg = makeMessage({ id: 'msg-1', content: 'Old', conversation_id: 'conv-1' })
      const store = useDMStore()
      store.conversations = [makeConversation({ id: 'conv-1', last_message: lastMsg })]
      store.messages = [lastMsg]

      const updated = makeMessage({
        id: 'msg-1',
        content: 'New content',
        conversation_id: 'conv-1',
        is_edited: true,
      })
      store.updateFromWebSocket(updated)

      expect(store.conversations[0].last_message!.content).toBe('New content')
    })

    it('does not update last_message if different message id', () => {
      const lastMsg = makeMessage({ id: 'msg-2', content: 'Untouched', conversation_id: 'conv-1' })
      const store = useDMStore()
      store.conversations = [makeConversation({ id: 'conv-1', last_message: lastMsg })]
      store.messages = [makeMessage({ id: 'msg-1' })]

      const updated = makeMessage({ id: 'msg-1', content: 'Edited', conversation_id: 'conv-1' })
      store.updateFromWebSocket(updated)

      expect(store.conversations[0].last_message!.content).toBe('Untouched')
    })

    it('is a no-op if message not found in messages array', () => {
      const store = useDMStore()
      store.messages = [makeMessage({ id: 'msg-1', content: 'Untouched' })]

      store.updateFromWebSocket(makeMessage({ id: 'msg-nonexistent', content: 'Ghost' }))

      expect(store.messages[0].content).toBe('Untouched')
      expect(store.messages).toHaveLength(1)
    })

    it('does not modify other messages', () => {
      const store = useDMStore()
      store.messages = [
        makeMessage({ id: 'msg-1', content: 'First' }),
        makeMessage({ id: 'msg-2', content: 'Second' }),
      ]

      store.updateFromWebSocket(makeMessage({ id: 'msg-1', content: 'Updated', is_edited: true }))

      expect(store.messages[1].content).toBe('Second')
    })
  })

  // ============ recallFromWebSocket (DM_RECALLED) ============

  describe('recallFromWebSocket', () => {
    it('sets is_recalled to true on matching message', () => {
      const store = useDMStore()
      store.messages = [makeMessage({ id: 'msg-1', is_recalled: false })]

      store.recallFromWebSocket('msg-1', 'conv-1')

      expect(store.messages[0].is_recalled).toBe(true)
    })

    it('sets content to null on recalled message', () => {
      const store = useDMStore()
      store.messages = [makeMessage({ id: 'msg-1', content: 'Secret message' })]

      store.recallFromWebSocket('msg-1', 'conv-1')

      expect(store.messages[0].content).toBeNull()
    })

    it('sets attachment_url and attachment_name to null', () => {
      const store = useDMStore()
      store.messages = [
        makeMessage({
          id: 'msg-1',
          attachment_url: 'https://cdn.example.com/file.pdf',
          attachment_name: 'report.pdf',
        }),
      ]

      store.recallFromWebSocket('msg-1', 'conv-1')

      expect(store.messages[0].attachment_url).toBeNull()
      expect(store.messages[0].attachment_name).toBeNull()
    })

    it('updates last_message in conversations when recalled message is last', () => {
      const lastMsg = makeMessage({ id: 'msg-1', content: 'Secret', conversation_id: 'conv-1' })
      const store = useDMStore()
      store.conversations = [makeConversation({ id: 'conv-1', last_message: lastMsg })]
      store.messages = [lastMsg]

      store.recallFromWebSocket('msg-1', 'conv-1')

      expect(store.conversations[0].last_message!.is_recalled).toBe(true)
      expect(store.conversations[0].last_message!.content).toBeNull()
    })

    it('does not update last_message when different message is recalled', () => {
      const lastMsg = makeMessage({ id: 'msg-2', content: 'Latest', conversation_id: 'conv-1' })
      const store = useDMStore()
      store.conversations = [makeConversation({ id: 'conv-1', last_message: lastMsg })]
      store.messages = [makeMessage({ id: 'msg-1' }), lastMsg]

      store.recallFromWebSocket('msg-1', 'conv-1')

      expect(store.conversations[0].last_message!.content).toBe('Latest')
      expect(store.conversations[0].last_message!.is_recalled).toBe(false)
    })

    it('is a no-op if message not found', () => {
      const store = useDMStore()
      store.messages = [makeMessage({ id: 'msg-1', is_recalled: false })]

      store.recallFromWebSocket('msg-nonexistent', 'conv-1')

      expect(store.messages[0].is_recalled).toBe(false)
    })

    it('does not affect other messages', () => {
      const store = useDMStore()
      store.messages = [
        makeMessage({ id: 'msg-1', is_recalled: false }),
        makeMessage({ id: 'msg-2', is_recalled: false }),
      ]

      store.recallFromWebSocket('msg-1', 'conv-1')

      expect(store.messages[1].is_recalled).toBe(false)
    })
  })

  // ============ readReceiptFromWebSocket (DM_READ) ============

  describe('readReceiptFromWebSocket', () => {
    it('sets read_at only on own sent messages in active conversation', () => {
      const store = useDMStore()
      store.setCurrentUserId('user-1')
      store.activeConversationId = 'conv-1'
      store.messages = [
        // Own message (sender.id matches currentUserId)
        makeMessage({
          id: 'msg-1',
          conversation_id: 'conv-1',
          read_at: null,
          sender: makeSender({ id: 'user-1', display_name: 'Me' }),
        }),
        // Other user's message (sender.id does NOT match currentUserId)
        makeMessage({
          id: 'msg-2',
          conversation_id: 'conv-1',
          read_at: null,
          sender: makeSender({ id: 'user-2', display_name: 'Alice' }),
        }),
      ]

      store.readReceiptFromWebSocket('conv-1', '2026-03-17T01:00:00Z')

      // Own message should be marked as read
      expect(store.messages[0].read_at).toBe('2026-03-17T01:00:00Z')
      // Other user's message should NOT be marked as read
      expect(store.messages[1].read_at).toBeNull()
    })

    it('does not overwrite an existing read_at timestamp', () => {
      const store = useDMStore()
      store.activeConversationId = 'conv-1'
      store.messages = [
        makeMessage({ id: 'msg-1', conversation_id: 'conv-1', read_at: '2026-03-16T00:00:00Z' }),
      ]

      store.readReceiptFromWebSocket('conv-1', '2026-03-17T01:00:00Z')

      expect(store.messages[0].read_at).toBe('2026-03-16T00:00:00Z')
    })

    it('does not update messages if conversation is not active', () => {
      const store = useDMStore()
      store.activeConversationId = 'conv-other'
      store.messages = [makeMessage({ id: 'msg-1', conversation_id: 'conv-1', read_at: null })]

      store.readReceiptFromWebSocket('conv-1', '2026-03-17T01:00:00Z')

      expect(store.messages[0].read_at).toBeNull()
    })

    it('does NOT clear conversation unread_count (DM_READ means OTHER user read OUR messages)', () => {
      const store = useDMStore()
      store.activeConversationId = 'conv-1'
      store.conversations = [makeConversation({ id: 'conv-1', unread_count: 5 })]
      store.unreadCount = 8
      store.messages = []

      store.readReceiptFromWebSocket('conv-1', '2026-03-17T01:00:00Z')

      // Unread counts should be preserved — DM_READ is about the other user reading our messages
      expect(store.conversations[0].unread_count).toBe(5)
      expect(store.unreadCount).toBe(8)
    })
  })

  // ============ setActiveConversation ============

  describe('setActiveConversation', () => {
    it('sets activeConversationId', () => {
      const store = useDMStore()
      store.setActiveConversation('conv-42')
      expect(store.activeConversationId).toBe('conv-42')
    })

    it('can set to null to deactivate', () => {
      const store = useDMStore()
      store.activeConversationId = 'conv-1'
      store.setActiveConversation(null)
      expect(store.activeConversationId).toBeNull()
    })

    it('replaces previous active conversation', () => {
      const store = useDMStore()
      store.setActiveConversation('conv-1')
      store.setActiveConversation('conv-2')
      expect(store.activeConversationId).toBe('conv-2')
    })
  })

  // ============ currentUserId ============

  describe('setCurrentUserId', () => {
    it('sets currentUserId', () => {
      const store = useDMStore()
      store.setCurrentUserId('user-42')
      expect(store.currentUserId).toBe('user-42')
    })

    it('is cleared on resetState', () => {
      const store = useDMStore()
      store.setCurrentUserId('user-42')
      store.resetState()
      expect(store.currentUserId).toBe('')
    })
  })

  // ============ BUG-1: fetchId guard (stale response discard) ============

  describe('fetchConversations fetchId guard', () => {
    it('discards stale response when a newer fetch is in progress', async () => {
      const store = useDMStore()

      let resolveFirst!: (value: unknown) => void
      const firstPromise = new Promise((resolve) => {
        resolveFirst = resolve
      })
      mockListConversations.mockReturnValueOnce(firstPromise)

      const staleConvos = [makeConversation({ id: 'stale-conv' })]
      const freshConvos = [makeConversation({ id: 'fresh-conv' })]

      // Start first fetch (will be stale)
      const fetch1 = store.fetchConversations()

      // Start second fetch immediately (supersedes first)
      mockListConversations.mockResolvedValueOnce({
        conversations: freshConvos,
        total: 1,
      })
      const fetch2 = store.fetchConversations()

      // Resolve the stale first response
      resolveFirst({ conversations: staleConvos, total: 1 })

      await fetch1
      await fetch2

      // Only fresh data should be present
      expect(store.conversations).toHaveLength(1)
      expect(store.conversations[0].id).toBe('fresh-conv')
    })

    it('does not set loading false on stale response', async () => {
      const store = useDMStore()

      let resolveFirst!: (value: unknown) => void
      const firstPromise = new Promise((resolve) => {
        resolveFirst = resolve
      })
      mockListConversations.mockReturnValueOnce(firstPromise)

      // Start first fetch
      const fetch1 = store.fetchConversations()

      // Start second fetch (pending)
      let resolveSecond!: (value: unknown) => void
      const secondPromise = new Promise((resolve) => {
        resolveSecond = resolve
      })
      mockListConversations.mockReturnValueOnce(secondPromise)
      const fetch2 = store.fetchConversations()

      // Resolve the stale first response — loading should stay true
      resolveFirst({ conversations: [], total: 0 })
      await fetch1
      expect(store.loading).toBe(true) // second is still pending

      resolveSecond({ conversations: [], total: 0 })
      await fetch2
      expect(store.loading).toBe(false)
    })
  })

  describe('fetchMessages fetchId guard', () => {
    it('discards stale response when a newer fetch is in progress', async () => {
      const store = useDMStore()

      let resolveFirst!: (value: unknown) => void
      const firstPromise = new Promise((resolve) => {
        resolveFirst = resolve
      })
      mockListMessages.mockReturnValueOnce(firstPromise)

      const staleMessages = [makeMessage({ id: 'stale-msg' })]
      const freshMessages = [makeMessage({ id: 'fresh-msg' })]

      // Start first fetch (will be stale)
      const fetch1 = store.fetchMessages('conv-1')

      // Start second fetch immediately
      mockListMessages.mockResolvedValueOnce({
        messages: freshMessages,
        total: 1,
      })
      const fetch2 = store.fetchMessages('conv-1')

      // Resolve the stale first response
      resolveFirst({ messages: staleMessages, total: 1 })

      await fetch1
      await fetch2

      // Only fresh data should be present
      expect(store.messages).toHaveLength(1)
      expect(store.messages[0].id).toBe('fresh-msg')
    })
  })

  // ============ BUG-2: Own message dedup ============

  describe('addFromWebSocket own message handling', () => {
    it('skips unread increment for own messages', () => {
      const store = useDMStore()
      store.setCurrentUserId('user-1')
      store.activeConversationId = 'conv-other'
      store.unreadCount = 0
      store.conversations = [makeConversation({ id: 'conv-1' })]

      const ownMsg = makeMessage({
        id: 'my-msg',
        conversation_id: 'conv-1',
        sender: makeSender({ id: 'user-1' }),
      })
      store.addFromWebSocket(ownMsg)

      expect(store.unreadCount).toBe(0)
    })

    it('deduplicates own sent message already in array', () => {
      const store = useDMStore()
      store.setCurrentUserId('user-1')
      store.activeConversationId = 'conv-1'
      store.conversations = [makeConversation({ id: 'conv-1' })]

      const ownMsg = makeMessage({
        id: 'my-msg',
        conversation_id: 'conv-1',
        sender: makeSender({ id: 'user-1' }),
      })
      store.messages = [ownMsg]

      // WS echo arrives
      store.addFromWebSocket(ownMsg)

      expect(store.messages).toHaveLength(1)
    })

    it('still updates conversation last_message for own messages', () => {
      const store = useDMStore()
      store.setCurrentUserId('user-1')
      store.activeConversationId = 'conv-1'
      store.conversations = [makeConversation({ id: 'conv-1', last_message: null })]

      const ownMsg = makeMessage({
        id: 'my-msg',
        conversation_id: 'conv-1',
        sender: makeSender({ id: 'user-1' }),
        content: 'My message',
      })
      store.addFromWebSocket(ownMsg)

      expect(store.conversations[0].last_message).toBeTruthy()
      expect(store.conversations[0].last_message!.content).toBe('My message')
    })

    it('does not increment conversation unread_count for own messages', () => {
      const store = useDMStore()
      store.setCurrentUserId('user-1')
      store.activeConversationId = 'conv-other'
      store.conversations = [makeConversation({ id: 'conv-1', unread_count: 0 })]

      const ownMsg = makeMessage({
        id: 'my-msg',
        conversation_id: 'conv-1',
        sender: makeSender({ id: 'user-1' }),
      })
      store.addFromWebSocket(ownMsg)

      expect(store.conversations[0].unread_count).toBe(0)
    })
  })

  // ============ BUG-4: readReceiptFromWebSocket in-place update ============

  describe('readReceiptFromWebSocket in-place update', () => {
    it('mutates message read_at in place', () => {
      const store = useDMStore()
      store.setCurrentUserId('user-1')
      store.activeConversationId = 'conv-1'
      const origMsg = makeMessage({ id: 'msg-1', conversation_id: 'conv-1', read_at: null })
      store.messages = [origMsg]

      store.readReceiptFromWebSocket('conv-1', '2026-03-17T01:00:00Z')

      expect(store.messages[0].read_at).toBe('2026-03-17T01:00:00Z')
    })

    it('updates all unread messages from current user', () => {
      const store = useDMStore()
      store.setCurrentUserId('user-1')
      store.activeConversationId = 'conv-1'
      store.messages = [
        makeMessage({ id: 'msg-1', conversation_id: 'conv-1', read_at: null }),
        makeMessage({ id: 'msg-2', conversation_id: 'conv-1', read_at: '2026-03-16T00:00:00Z' }),
        makeMessage({ id: 'msg-3', conversation_id: 'conv-1', read_at: null }),
      ]

      store.readReceiptFromWebSocket('conv-1', '2026-03-17T01:00:00Z')

      expect(store.messages[0].read_at).toBe('2026-03-17T01:00:00Z')
      // Already-read message keeps its original timestamp
      expect(store.messages[1].read_at).toBe('2026-03-16T00:00:00Z')
      expect(store.messages[2].read_at).toBe('2026-03-17T01:00:00Z')
    })

    it('does NOT mutate conversation unread_count (DM_READ = other user read our messages)', () => {
      const store = useDMStore()
      store.activeConversationId = 'conv-1'
      const origConv = makeConversation({ id: 'conv-1', unread_count: 3 })
      store.conversations = [origConv]
      store.unreadCount = 3
      store.messages = []

      store.readReceiptFromWebSocket('conv-1', '2026-03-17T01:00:00Z')

      // Unread counts should be preserved
      expect(store.conversations[0].unread_count).toBe(3)
      expect(store.unreadCount).toBe(3)
    })
  })

  // ============ BUG-5: Stale activeConversationId / unknown conversation ============

  describe('fetchMessages clears active conversation on 404', () => {
    it('clears activeConversationId and messages on 404', async () => {
      const store = useDMStore()
      store.activeConversationId = 'conv-deleted'
      store.messages = [makeMessage({ id: 'old-msg' })]
      store.messagesTotal = 1

      const err404 = Object.assign(new Error('Not Found'), {
        response: { status: 404 },
      })
      mockListMessages.mockRejectedValueOnce(err404)

      await store.fetchMessages('conv-deleted')

      expect(store.activeConversationId).toBeNull()
      expect(store.messages).toEqual([])
      expect(store.messagesTotal).toBe(0)
      expect(store.error).toBeTruthy()
    })

    it('does NOT clear activeConversationId on non-404 errors', async () => {
      const store = useDMStore()
      store.activeConversationId = 'conv-1'

      mockListMessages.mockRejectedValueOnce(new Error('Server error'))

      await store.fetchMessages('conv-1')

      expect(store.activeConversationId).toBe('conv-1')
      expect(store.error).toBeTruthy()
    })

    it('sets user-friendly error message on 404', async () => {
      const store = useDMStore()
      const err404 = Object.assign(new Error('Not Found'), {
        response: { status: 404 },
      })
      mockListMessages.mockRejectedValueOnce(err404)

      await store.fetchMessages('conv-deleted')

      expect(store.error).toBe('This conversation no longer exists.')
    })
  })

  describe('addFromWebSocket unknown conversation refetch', () => {
    it('triggers fetchConversations for unknown conversation', async () => {
      mockListConversations.mockResolvedValueOnce({ conversations: [], total: 0 })
      const store = useDMStore()
      store.setCurrentUserId('user-1')
      // No conversations loaded — convIdx will be -1
      store.conversations = []

      const msg = makeMessage({
        id: 'msg-from-unknown',
        conversation_id: 'conv-unknown',
        sender: makeSender({ id: 'user-2' }),
      })
      store.addFromWebSocket(msg)

      expect(mockListConversations).toHaveBeenCalled()
    })

    it('increments unreadCount for unknown conversation from other user', () => {
      mockListConversations.mockResolvedValueOnce({ conversations: [], total: 0 })
      const store = useDMStore()
      store.setCurrentUserId('user-1')
      store.conversations = []
      store.unreadCount = 0

      const msg = makeMessage({
        id: 'msg-new',
        conversation_id: 'conv-unknown',
        sender: makeSender({ id: 'user-2' }),
      })
      store.addFromWebSocket(msg)

      expect(store.unreadCount).toBe(1)
    })

    it('does NOT increment unreadCount for unknown conversation from self', () => {
      mockListConversations.mockResolvedValueOnce({ conversations: [], total: 0 })
      const store = useDMStore()
      store.setCurrentUserId('user-1')
      store.conversations = []
      store.unreadCount = 0

      const msg = makeMessage({
        id: 'msg-new',
        conversation_id: 'conv-unknown',
        sender: makeSender({ id: 'user-1' }),
      })
      store.addFromWebSocket(msg)

      expect(store.unreadCount).toBe(0)
    })
  })

  // ============ resetState ============

  describe('resetState', () => {
    it('clears all state to defaults', () => {
      const store = useDMStore()
      store.conversations = [makeConversation()]
      store.conversationsTotal = 10
      store.messages = [makeMessage()]
      store.messagesTotal = 50
      store.unreadCount = 5
      store.activeConversationId = 'conv-1'
      store.loading = true
      store.error = 'some error'

      store.resetState()

      expect(store.conversations).toEqual([])
      expect(store.conversationsTotal).toBe(0)
      expect(store.messages).toEqual([])
      expect(store.messagesTotal).toBe(0)
      expect(store.unreadCount).toBe(0)
      expect(store.activeConversationId).toBeNull()
      expect(store.loading).toBe(false)
      expect(store.error).toBeNull()
    })

    it('is callable multiple times without error', () => {
      const store = useDMStore()
      store.resetState()
      store.resetState()
      expect(store.unreadCount).toBe(0)
    })

    it('resets error to null', () => {
      const store = useDMStore()
      store.error = 'Failed to load'
      store.resetState()
      expect(store.error).toBeNull()
    })
  })
})

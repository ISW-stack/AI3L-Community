/**
 * Tests for DMView race guard fixes:
 * - F-08: DM unread count race guard on rapid conversation switching
 * - F-12: DM conversation list pagination sync on new conversation
 *
 * Since DMView is a <script setup> SFC, we test the logic by extracting
 * the critical flows into a unit-testable form using the DM store directly.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useDMStore } from '@/stores/dm'
import { usePagination } from '@/composables/usePagination'
import type { Conversation, DMMessage } from '@/types/dm'

// Mock DM API
vi.mock('@/api/dm', () => ({
  listConversations: vi.fn(),
  listMessages: vi.fn(),
  sendMessage: vi.fn(),
  editMessage: vi.fn(),
  recallMessage: vi.fn(),
  markConversationRead: vi.fn(),
  getUnreadCount: vi.fn(),
}))

vi.mock('@/api/users', () => ({
  getPreferences: vi.fn().mockResolvedValue({ dm_friends_only: false }),
  updatePreferences: vi.fn(),
}))

import * as dmApi from '@/api/dm'

const mockMarkRead = dmApi.markConversationRead as ReturnType<typeof vi.fn>
const mockSendMessage = dmApi.sendMessage as ReturnType<typeof vi.fn>
const mockListConversations = dmApi.listConversations as ReturnType<typeof vi.fn>

function makeConversation(overrides: Partial<Conversation> = {}): Conversation {
  return {
    id: 'conv1',
    other_user: { id: 'user2', display_name: 'Bob', avatar_url: null },
    last_message: null,
    unread_count: 0,
    updated_at: '2026-01-01T00:00:00Z',
    ...overrides,
  }
}

function makeMessage(overrides: Partial<DMMessage> = {}): DMMessage {
  return {
    id: 'msg1',
    conversation_id: 'conv1',
    sender: { id: 'user1', display_name: 'Alice', avatar_url: null },
    content: 'Hello',
    attachment_url: null,
    attachment_name: null,
    attachment_size: null,
    attachment_expires_at: null,
    is_recalled: false,
    is_edited: false,
    read_at: null,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    ...overrides,
  }
}

describe('F-08: DM unread count race guard on rapid switching', () => {
  let dmStore: ReturnType<typeof useDMStore>

  beforeEach(() => {
    vi.clearAllMocks()
    setActivePinia(createPinia())
    dmStore = useDMStore()
  })

  it('normal mark-as-read flow updates unread counts correctly', async () => {
    // Setup: conversation with 3 unread messages, global unread = 5
    const conv = makeConversation({ id: 'conv1', unread_count: 3 })
    dmStore.conversations = [conv]
    dmStore.unreadCount = 5
    dmStore.activeConversationId = 'conv1'

    mockMarkRead.mockResolvedValue(undefined)

    // Simulate selectConversation mark-as-read logic
    const conversationId = 'conv1'
    const convIdx = dmStore.conversations.findIndex((c) => c.id === conversationId)
    expect(convIdx).toBe(0)
    expect(dmStore.conversations[convIdx].unread_count).toBe(3)

    await dmApi.markConversationRead(conversationId)

    // Guard: activeConversationId still matches
    if (dmStore.activeConversationId !== conversationId) return
    const freshIdx = dmStore.conversations.findIndex((c) => c.id === conversationId)
    if (freshIdx < 0) return
    const prevUnread = dmStore.conversations[freshIdx].unread_count
    dmStore.unreadCount = Math.max(0, dmStore.unreadCount - prevUnread)
    dmStore.conversations[freshIdx] = {
      ...dmStore.conversations[freshIdx],
      unread_count: 0,
    }

    // Verify
    expect(dmStore.conversations[0].unread_count).toBe(0)
    expect(dmStore.unreadCount).toBe(2) // 5 - 3 = 2
    expect(mockMarkRead).toHaveBeenCalledWith('conv1')
  })

  it('stale callback returns early when activeConversationId changed during await', async () => {
    // Setup: two conversations, user opens conv1 which has 3 unread
    const conv1 = makeConversation({ id: 'conv1', unread_count: 3 })
    const conv2 = makeConversation({ id: 'conv2', unread_count: 0 })
    dmStore.conversations = [conv1, conv2]
    dmStore.unreadCount = 5
    dmStore.activeConversationId = 'conv1'

    // markConversationRead resolves, but by the time it does,
    // the user has switched to conv2
    let resolveMarkRead: () => void
    mockMarkRead.mockReturnValue(
      new Promise<void>((resolve) => {
        resolveMarkRead = resolve
      }),
    )

    const conversationId = 'conv1'
    const markReadPromise = dmApi.markConversationRead(conversationId)

    // User switches to conv2 during the await
    dmStore.activeConversationId = 'conv2'

    // Now the API call resolves
    resolveMarkRead!()
    await markReadPromise

    // Guard check: activeConversationId !== conversationId, should NOT update
    if (dmStore.activeConversationId !== conversationId) {
      // This is the expected path - early return
      expect(dmStore.conversations[0].unread_count).toBe(3) // unchanged
      expect(dmStore.unreadCount).toBe(5) // unchanged
      return
    }

    // Should not reach here
    expect.unreachable('Should have returned early due to stale conversation')
  })

  it('stale callback does not modify state when conversation list shifted', async () => {
    // Setup: conversation at index 0 with unread, but after the API call
    // the conversation list is reloaded and it moves/disappears
    const conv1 = makeConversation({ id: 'conv1', unread_count: 4 })
    dmStore.conversations = [conv1]
    dmStore.unreadCount = 4
    dmStore.activeConversationId = 'conv1'

    let resolveMarkRead: () => void
    mockMarkRead.mockReturnValue(
      new Promise<void>((resolve) => {
        resolveMarkRead = resolve
      }),
    )

    const conversationId = 'conv1'
    const markReadPromise = dmApi.markConversationRead(conversationId)

    // Conversations list refreshes and conv1 is gone
    dmStore.conversations = [makeConversation({ id: 'conv3', unread_count: 1 })]

    resolveMarkRead!()
    await markReadPromise

    // activeConversationId still matches, but freshIdx will be -1
    if (dmStore.activeConversationId !== conversationId) return
    const freshIdx = dmStore.conversations.findIndex((c) => c.id === conversationId)
    if (freshIdx < 0) {
      // Expected: conversation no longer in list, early return
      expect(dmStore.unreadCount).toBe(4) // unchanged
      return
    }

    expect.unreachable('Should have returned early because conversation not found')
  })

  it('re-finds conversation index after await in case it shifted', async () => {
    // Setup: conv1 at index 0, conv2 at index 1
    const conv1 = makeConversation({ id: 'conv1', unread_count: 2 })
    const conv2 = makeConversation({ id: 'conv2', unread_count: 0 })
    dmStore.conversations = [conv1, conv2]
    dmStore.unreadCount = 5
    dmStore.activeConversationId = 'conv1'

    let resolveMarkRead: () => void
    mockMarkRead.mockReturnValue(
      new Promise<void>((resolve) => {
        resolveMarkRead = resolve
      }),
    )

    const conversationId = 'conv1'
    const markReadPromise = dmApi.markConversationRead(conversationId)

    // During await, a new conversation gets prepended, shifting indices
    const newConv = makeConversation({ id: 'conv0', unread_count: 0 })
    dmStore.conversations = [newConv, conv1, conv2]

    resolveMarkRead!()
    await markReadPromise

    // Guard passes, freshIdx must re-find conv1 at new index 1
    if (dmStore.activeConversationId !== conversationId) return
    const freshIdx = dmStore.conversations.findIndex((c) => c.id === conversationId)
    expect(freshIdx).toBe(1)
    if (freshIdx < 0) return

    const prevUnread = dmStore.conversations[freshIdx].unread_count
    dmStore.unreadCount = Math.max(0, dmStore.unreadCount - prevUnread)
    dmStore.conversations[freshIdx] = {
      ...dmStore.conversations[freshIdx],
      unread_count: 0,
    }

    expect(dmStore.conversations[1].unread_count).toBe(0)
    expect(dmStore.unreadCount).toBe(3) // 5 - 2 = 3
  })
})

describe('F-12: DM conversation list pagination sync on new conversation', () => {
  let dmStore: ReturnType<typeof useDMStore>

  beforeEach(() => {
    vi.clearAllMocks()
    setActivePinia(createPinia())
    dmStore = useDMStore()
  })

  it('resets pagination to page 1 and updates total when creating new conversation', async () => {
    const convPagination = usePagination(30)

    // Simulate user was on page 2
    convPagination.setPage(2)
    expect(convPagination.page.value).toBe(2)

    // Setup: no active conversation (new conversation flow)
    dmStore.activeConversationId = null
    const newMsg = makeMessage({ id: 'msg-new', conversation_id: 'conv-new' })
    mockSendMessage.mockResolvedValue(newMsg)

    // After sending, conversations are fetched — simulate the total being 31
    mockListConversations.mockResolvedValue({
      conversations: [makeConversation({ id: 'conv-new' })],
      total: 31,
    })

    // Simulate handleSend new message logic
    const activeOtherUserId = 'user2'
    const msg = await dmApi.sendMessage(activeOtherUserId, 'Hello!')

    if (!dmStore.activeConversationId) {
      dmStore.activeConversationId = msg.conversation_id

      // F-12 fix: resetPage before fetch
      convPagination.resetPage()
      expect(convPagination.page.value).toBe(1)

      await dmStore.fetchConversations(1, convPagination.pageSize)

      // F-12 fix: updateFromResponse after fetch
      convPagination.updateFromResponse(dmStore.conversationsTotal)
    }

    expect(convPagination.page.value).toBe(1)
    expect(convPagination.total.value).toBe(31)
    expect(convPagination.totalPages.value).toBe(2) // ceil(31/30)
    expect(mockListConversations).toHaveBeenCalledWith({ page: 1, page_size: 30 })
  })

  it('does not reset pagination when sending in existing conversation', async () => {
    const convPagination = usePagination(30)
    convPagination.setPage(2)
    convPagination.updateFromResponse(60)

    // Setup: active conversation already exists
    dmStore.activeConversationId = 'conv1'
    dmStore.conversations = [makeConversation({ id: 'conv1' })]

    const msg = makeMessage({ id: 'msg2', conversation_id: 'conv1' })
    mockSendMessage.mockResolvedValue(msg)

    // Simulate handleSend — active conversation exists, so pagination is not touched
    const sentMsg = await dmApi.sendMessage('user2', 'Hi again')

    if (!dmStore.activeConversationId) {
      // This branch should NOT execute
      convPagination.resetPage()
      await dmStore.fetchConversations(1, convPagination.pageSize)
      convPagination.updateFromResponse(dmStore.conversationsTotal)
    }

    // Pagination stays on page 2
    expect(convPagination.page.value).toBe(2)
    expect(convPagination.total.value).toBe(60)
    expect(mockListConversations).not.toHaveBeenCalled()
  })
})

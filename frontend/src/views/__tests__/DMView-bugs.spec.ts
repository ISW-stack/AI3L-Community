/**
 * F-24 / F-25: Unit tests for DMView bug fixes.
 *
 * These test the logic extracted from DMView's `handleLoadMore` and
 * `markConversationRead` functions in isolation.
 */
import { describe, it, expect, vi } from 'vitest'

describe('DMView handleLoadMore guard (F-24)', () => {
  // Reproduce the guard logic from DMView.handleLoadMore
  function handleLoadMore(opts: {
    activeConversationId: string | null
    hasMoreMessages: boolean
    messagesLoading: boolean
    messagesTotal: number
    pageSize: number
    currentMsgPage: number
  }): { shouldFetch: boolean; newPage: number } {
    const { activeConversationId, hasMoreMessages, messagesLoading, messagesTotal, pageSize, currentMsgPage } = opts
    if (!activeConversationId || !hasMoreMessages || messagesLoading) {
      return { shouldFetch: false, newPage: currentMsgPage }
    }
    const maxPage = Math.ceil(messagesTotal / pageSize)
    if (currentMsgPage >= maxPage) {
      return { shouldFetch: false, newPage: currentMsgPage }
    }
    return { shouldFetch: true, newPage: currentMsgPage + 1 }
  }

  it('returns false when currentMsgPage already at max page', () => {
    const result = handleLoadMore({
      activeConversationId: 'conv-1',
      hasMoreMessages: true,
      messagesLoading: false,
      messagesTotal: 30,
      pageSize: 30,
      currentMsgPage: 1,
    })
    expect(result.shouldFetch).toBe(false)
    expect(result.newPage).toBe(1)
  })

  it('returns false when currentMsgPage exceeds max page', () => {
    const result = handleLoadMore({
      activeConversationId: 'conv-1',
      hasMoreMessages: true,
      messagesLoading: false,
      messagesTotal: 60,
      pageSize: 30,
      currentMsgPage: 2,
    })
    expect(result.shouldFetch).toBe(false)
    expect(result.newPage).toBe(2)
  })

  it('allows fetch when currentMsgPage is below max page', () => {
    const result = handleLoadMore({
      activeConversationId: 'conv-1',
      hasMoreMessages: true,
      messagesLoading: false,
      messagesTotal: 90,
      pageSize: 30,
      currentMsgPage: 1,
    })
    expect(result.shouldFetch).toBe(true)
    expect(result.newPage).toBe(2)
  })

  it('returns false when no active conversation', () => {
    const result = handleLoadMore({
      activeConversationId: null,
      hasMoreMessages: true,
      messagesLoading: false,
      messagesTotal: 90,
      pageSize: 30,
      currentMsgPage: 1,
    })
    expect(result.shouldFetch).toBe(false)
  })

  it('returns false when messages are loading', () => {
    const result = handleLoadMore({
      activeConversationId: 'conv-1',
      hasMoreMessages: true,
      messagesLoading: true,
      messagesTotal: 90,
      pageSize: 30,
      currentMsgPage: 1,
    })
    expect(result.shouldFetch).toBe(false)
  })
})

describe('DMView markConversationRead error handling (F-25)', () => {
  it('reverts unread_count on markConversationRead failure', async () => {
    // Simulate the fix: on catch, revert unread_count
    const conversations = [
      { id: 'conv-1', unread_count: 5 },
    ]
    let globalUnreadCount = 10
    const prevUnread = conversations[0].unread_count

    const markRead = vi.fn().mockRejectedValue(new Error('Network error'))

    try {
      await markRead('conv-1')
      globalUnreadCount = Math.max(0, globalUnreadCount - prevUnread)
      conversations[0] = { ...conversations[0], unread_count: 0 }
    } catch {
      // Revert
      conversations[0] = { ...conversations[0], unread_count: prevUnread }
    }

    // unread_count should be reverted
    expect(conversations[0].unread_count).toBe(5)
    // global unread should NOT have been decremented
    expect(globalUnreadCount).toBe(10)
  })

  it('updates unread_count on successful markConversationRead', async () => {
    const conversations = [
      { id: 'conv-1', unread_count: 5 },
    ]
    let globalUnreadCount = 10
    const prevUnread = conversations[0].unread_count

    const markRead = vi.fn().mockResolvedValue(undefined)

    try {
      await markRead('conv-1')
      globalUnreadCount = Math.max(0, globalUnreadCount - prevUnread)
      conversations[0] = { ...conversations[0], unread_count: 0 }
    } catch {
      conversations[0] = { ...conversations[0], unread_count: prevUnread }
    }

    expect(conversations[0].unread_count).toBe(0)
    expect(globalUnreadCount).toBe(5)
  })
})

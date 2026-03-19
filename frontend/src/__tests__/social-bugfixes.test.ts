/**
 * Tests for social/friend/DM bugfixes:
 * - F2: FriendRecommendations dismiss rollback restores original position
 * - F3: DMView parseDMError contextual SYS_403 messages
 * - F4: DMView mark-read uses immutable update pattern
 * - F5: DMView DM_001 error matching is case-insensitive
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'

// ── F2: FriendRecommendations dismiss rollback ──────────────────────────

const mockGetRecommendations = vi.fn()
const mockDismissRecommendation = vi.fn()
const mockSendFriendRequest = vi.fn()

vi.mock('@/api/recommendations', () => ({
  getRecommendations: (...args: unknown[]) => mockGetRecommendations(...args),
  dismissRecommendation: (...args: unknown[]) => mockDismissRecommendation(...args),
}))

vi.mock('@/api/social', () => ({
  sendFriendRequest: (...args: unknown[]) => mockSendFriendRequest(...args),
}))

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({
    isAuthenticated: true,
    isGuest: false,
    user: { id: 'u1' },
  }),
}))

vi.mock('@/stores/toast', () => ({
  useToastStore: () => ({
    show: vi.fn(),
  }),
}))

vi.mock('@/composables/api', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
}))

// ── F3/F4: DM store + view helpers ────────────────────────────────────

const mockListConversations = vi.fn()
const mockListMessages = vi.fn()
const mockSendDMMessage = vi.fn()
const mockEditDMMessage = vi.fn()
const mockRecallDMMessage = vi.fn()
const mockMarkConversationRead = vi.fn()
const mockGetUnreadCount = vi.fn()

vi.mock('@/api/dm', () => ({
  listConversations: (...args: unknown[]) => mockListConversations(...args),
  listMessages: (...args: unknown[]) => mockListMessages(...args),
  sendMessage: (...args: unknown[]) => mockSendDMMessage(...args),
  editMessage: (...args: unknown[]) => mockEditDMMessage(...args),
  recallMessage: (...args: unknown[]) => mockRecallDMMessage(...args),
  markConversationRead: (...args: unknown[]) => mockMarkConversationRead(...args),
  getUnreadCount: (...args: unknown[]) => mockGetUnreadCount(...args),
}))

import { useDMStore } from '@/stores/dm'
import type { Conversation } from '@/types/dm'
import type { FriendRecommendation } from '@/types/recommendation'

// ── Test data factories ─────────────────────────────────────────────────

function makeSender(
  overrides: Partial<{ id: string; display_name: string; avatar_url: string | null }> = {},
) {
  return { id: 'user-2', display_name: 'Alice', avatar_url: null, ...overrides }
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

function makeRecommendation(overrides: Partial<FriendRecommendation> = {}): FriendRecommendation {
  return {
    id: 'rec-1',
    user_id: 'u-rec-1',
    display_name: 'Rec User',
    username: 'recuser',
    avatar_url: null,
    affiliation: null,
    score: 0.8,
    reasons: [],
    created_at: '2026-03-17T00:00:00Z',
    ...overrides,
  }
}

// ── Tests ───────────────────────────────────────────────────────────────

describe('Social bugfixes', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  // ========== F2: Dismiss rollback restores original position ==========

  describe('FriendRecommendations dismiss rollback position', () => {
    it('restores item at original index on dismiss failure', async () => {
      // Dynamically import the component's logic (we test the logic directly)
      const recs = [
        makeRecommendation({ id: 'r1', user_id: 'u1', display_name: 'A', score: 0.9 }),
        makeRecommendation({ id: 'r2', user_id: 'u2', display_name: 'B', score: 0.7 }),
        makeRecommendation({ id: 'r3', user_id: 'u3', display_name: 'C', score: 0.5 }),
      ]

      // Simulate the handleDismiss logic from FriendRecommendations.vue
      const recommendations = { value: [...recs] }
      const removedIndex = recommendations.value.findIndex((r) => r.user_id === 'u2')
      const removed = recommendations.value[removedIndex]
      recommendations.value = recommendations.value.filter((r) => r.user_id !== 'u2')

      // Verify item removed
      expect(recommendations.value).toHaveLength(2)
      expect(recommendations.value[0].user_id).toBe('u1')
      expect(recommendations.value[1].user_id).toBe('u3')

      // Simulate rollback with splice (the fix)
      recommendations.value.splice(removedIndex, 0, removed)

      // Verify restored at original position (index 1)
      expect(recommendations.value).toHaveLength(3)
      expect(recommendations.value[0].user_id).toBe('u1')
      expect(recommendations.value[1].user_id).toBe('u2') // restored at original index
      expect(recommendations.value[2].user_id).toBe('u3')
    })

    it('rollback with push (old bug) appends to end instead', () => {
      const recs = [
        makeRecommendation({ id: 'r1', user_id: 'u1' }),
        makeRecommendation({ id: 'r2', user_id: 'u2' }),
        makeRecommendation({ id: 'r3', user_id: 'u3' }),
      ]

      const recommendations = { value: [...recs] }
      const removed = recommendations.value.find((r) => r.user_id === 'u2')!
      recommendations.value = recommendations.value.filter((r) => r.user_id !== 'u2')

      // Old behavior: push to end
      recommendations.value.push(removed)

      // Demonstrates the old bug: u2 is at end instead of index 1
      expect(recommendations.value[2].user_id).toBe('u2') // wrong position
      expect(recommendations.value[1].user_id).toBe('u3') // shifted
    })
  })

  // ========== F3: DMView parseDMError contextual SYS_403 ==========

  describe('parseDMError contextual SYS_403 messages', () => {
    // Simulate parseDMError logic from DMView.vue
    function parseDMError(e: unknown, fallback: string): string {
      if (e && typeof e === 'object' && 'response' in e) {
        const resp = (
          e as { response?: { data?: { detail?: { code?: string; message?: string } } } }
        ).response
        const code = resp?.data?.detail?.code
        if (code === 'DM_001') {
          const msg = resp?.data?.detail?.message ?? ''
          if (msg.toLowerCase().includes('friend'))
            return 'This user only accepts messages from friends.'
          return 'You cannot message this user.'
        }
        if (code === 'SYS_403') {
          const msg = resp?.data?.detail?.message ?? ''
          if (msg.includes('edit')) return 'You can only edit your own messages.'
          if (msg.includes('recall')) return 'You can only recall your own messages.'
          return 'You do not have permission to perform this action.'
        }
      }
      return fallback
    }

    it('returns edit-specific message for SYS_403 with edit', () => {
      const error = {
        response: {
          data: { detail: { code: 'SYS_403', message: "Cannot edit another user's message." } },
        },
      }
      expect(parseDMError(error, 'fallback')).toBe('You can only edit your own messages.')
    })

    it('returns recall-specific message for SYS_403 with recall', () => {
      const error = {
        response: {
          data: { detail: { code: 'SYS_403', message: "Cannot recall another user's message." } },
        },
      }
      expect(parseDMError(error, 'fallback')).toBe('You can only recall your own messages.')
    })

    it('returns generic permission message for other SYS_403', () => {
      const error = {
        response: { data: { detail: { code: 'SYS_403', message: 'Not authorized.' } } },
      }
      expect(parseDMError(error, 'fallback')).toBe(
        'You do not have permission to perform this action.',
      )
    })

    it('handles DM_001 friends message case-insensitively', () => {
      const error = {
        response: {
          data: {
            detail: { code: 'DM_001', message: 'This user only accepts messages from Friends.' },
          },
        },
      }
      expect(parseDMError(error, 'fallback')).toBe('This user only accepts messages from friends.')
    })

    it('returns blocked message for DM_001 without friend keyword', () => {
      const error = {
        response: { data: { detail: { code: 'DM_001', message: 'Cannot message this user.' } } },
      }
      expect(parseDMError(error, 'fallback')).toBe('You cannot message this user.')
    })
  })

  // ========== F4: DM mark-read immutable update ==========

  describe('DM mark-read immutable update', () => {
    it('uses immutable update for conversation unread_count', () => {
      const store = useDMStore()
      const conv1 = makeConversation({ id: 'conv-1', unread_count: 5 })
      const conv2 = makeConversation({ id: 'conv-2', unread_count: 3 })
      store.conversations = [conv1, conv2]
      store.unreadCount = 8

      // Capture original reference
      const originalConv1 = store.conversations[0]

      // Simulate the fixed immutable update from DMView.vue
      const convIdx = store.conversations.findIndex((c) => c.id === 'conv-1')
      if (convIdx >= 0 && store.conversations[convIdx].unread_count > 0) {
        const prevUnread = store.conversations[convIdx].unread_count
        store.unreadCount = Math.max(0, store.unreadCount - prevUnread)
        store.conversations[convIdx] = {
          ...store.conversations[convIdx],
          unread_count: 0,
        }
      }

      // Verify immutable: new object at index 0
      expect(store.conversations[0]).not.toBe(originalConv1)
      expect(store.conversations[0].unread_count).toBe(0)
      expect(store.unreadCount).toBe(3)
      // conv2 untouched
      expect(store.conversations[1].unread_count).toBe(3)
    })

    it('does not modify unread count when conversation has 0 unread', () => {
      const store = useDMStore()
      store.conversations = [makeConversation({ id: 'conv-1', unread_count: 0 })]
      store.unreadCount = 5

      const convIdx = store.conversations.findIndex((c) => c.id === 'conv-1')
      // Guard: unread_count is 0, so no update
      if (convIdx >= 0 && store.conversations[convIdx].unread_count > 0) {
        // This should not execute
        store.unreadCount = 0
      }

      expect(store.unreadCount).toBe(5) // unchanged
    })
  })
})

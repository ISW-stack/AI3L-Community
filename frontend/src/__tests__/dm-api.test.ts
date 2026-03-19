import { describe, it, expect, vi, beforeEach } from 'vitest'

const mockGet = vi.fn()
const mockPost = vi.fn()
const mockPut = vi.fn()
const mockDelete = vi.fn()

vi.mock('@/composables/api', () => ({
  default: {
    get: (...args: unknown[]) => mockGet(...args),
    post: (...args: unknown[]) => mockPost(...args),
    put: (...args: unknown[]) => mockPut(...args),
    delete: (...args: unknown[]) => mockDelete(...args),
  },
}))

import {
  listConversations,
  listMessages,
  sendMessage,
  editMessage,
  recallMessage,
  markConversationRead,
  getUnreadCount,
} from '@/api/dm'

describe('DM API module', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  // ============ listConversations ============

  describe('listConversations', () => {
    it('calls GET /dm/conversations with params and returns data', async () => {
      const mockData = { conversations: [], total: 0 }
      mockGet.mockResolvedValue({ data: mockData })

      const result = await listConversations({ page: 1, page_size: 30 })

      expect(mockGet).toHaveBeenCalledWith('/dm/conversations', {
        params: { page: 1, page_size: 30 },
      })
      expect(result).toEqual(mockData)
    })

    it('passes custom page and page_size params', async () => {
      mockGet.mockResolvedValue({ data: { conversations: [], total: 0 } })

      await listConversations({ page: 2, page_size: 5 })

      expect(mockGet).toHaveBeenCalledWith('/dm/conversations', {
        params: { page: 2, page_size: 5 },
      })
    })

    it('returns typed response with conversations and total', async () => {
      const conv = {
        id: 'conv-1',
        other_user: { id: 'u2', display_name: 'Alice', avatar_url: null },
        last_message: null,
        unread_count: 0,
        updated_at: '2026-03-17T00:00:00Z',
      }
      mockGet.mockResolvedValue({ data: { conversations: [conv], total: 1 } })

      const result = await listConversations({})

      expect(result.conversations).toHaveLength(1)
      expect(result.conversations[0].id).toBe('conv-1')
      expect(result.total).toBe(1)
    })
  })

  // ============ listMessages ============

  describe('listMessages', () => {
    it('calls GET /dm/conversations/{id}/messages with params', async () => {
      mockGet.mockResolvedValue({ data: { messages: [], total: 0 } })

      await listMessages('conv-1', { page: 1, page_size: 20 })

      expect(mockGet).toHaveBeenCalledWith('/dm/conversations/conv-1/messages', {
        params: { page: 1, page_size: 20 },
      })
    })

    it('returns typed response with messages array', async () => {
      const msg = {
        id: 'msg-1',
        conversation_id: 'conv-1',
        content: 'Hello',
        sender: { id: 'u1', display_name: 'Bob', avatar_url: null },
      }
      mockGet.mockResolvedValue({ data: { messages: [msg], total: 1 } })

      const result = await listMessages('conv-1', {})

      expect(result.messages).toHaveLength(1)
      expect(result.messages[0].content).toBe('Hello')
    })

    it('includes conversation ID in URL path', async () => {
      mockGet.mockResolvedValue({ data: { messages: [], total: 0 } })

      await listMessages('abc-xyz', { page: 1 })

      expect(mockGet).toHaveBeenCalledWith('/dm/conversations/abc-xyz/messages', expect.any(Object))
    })
  })

  // ============ sendMessage ============

  describe('sendMessage', () => {
    it('sends text-only message as FormData with content', async () => {
      const mockResp = { id: 'msg-1', content: 'Hello' }
      mockPost.mockResolvedValue({ data: mockResp })

      const result = await sendMessage('user-2', 'Hello')

      expect(mockPost).toHaveBeenCalledWith(
        '/dm/conversations/user-2/messages',
        expect.any(FormData),
        { headers: { 'Content-Type': 'multipart/form-data' } },
      )
      expect(result).toEqual(mockResp)
    })

    it('sends file-only message with FormData containing file', async () => {
      const file = new File(['data'], 'test.pdf', { type: 'application/pdf' })
      mockPost.mockResolvedValue({ data: { id: 'msg-2' } })

      await sendMessage('user-2', undefined, file)

      expect(mockPost).toHaveBeenCalled()
      const formData = mockPost.mock.calls[0][1] as FormData
      expect(formData).toBeInstanceOf(FormData)
      expect(formData.get('file')).toBeTruthy()
    })

    it('sends text + file together in FormData', async () => {
      const file = new File(['img'], 'photo.jpg', { type: 'image/jpeg' })
      mockPost.mockResolvedValue({ data: { id: 'msg-3' } })

      await sendMessage('user-2', 'Check this', file)

      const formData = mockPost.mock.calls[0][1] as FormData
      expect(formData.get('content')).toBe('Check this')
      expect(formData.get('file')).toBeTruthy()
    })

    it('includes userId in the URL path', async () => {
      mockPost.mockResolvedValue({ data: { id: 'msg-4' } })

      await sendMessage('user-abc', 'Hi')

      expect(mockPost).toHaveBeenCalledWith(
        '/dm/conversations/user-abc/messages',
        expect.any(FormData),
        expect.any(Object),
      )
    })

    it('sets Content-Type header to multipart/form-data', async () => {
      mockPost.mockResolvedValue({ data: { id: 'msg-5' } })

      await sendMessage('user-2', 'Test')

      const options = mockPost.mock.calls[0][2]
      expect(options).toEqual({ headers: { 'Content-Type': 'multipart/form-data' } })
    })
  })

  // ============ editMessage ============

  describe('editMessage', () => {
    it('calls PUT /dm/messages/{id} with content body', async () => {
      const mockResp = { id: 'msg-1', content: 'Edited', is_edited: true }
      mockPut.mockResolvedValue({ data: mockResp })

      const result = await editMessage('msg-1', 'Edited')

      expect(mockPut).toHaveBeenCalledWith('/dm/messages/msg-1', { content: 'Edited' })
      expect(result).toEqual(mockResp)
    })

    it('includes message ID in URL', async () => {
      mockPut.mockResolvedValue({ data: { id: 'xyz' } })

      await editMessage('xyz', 'New')

      expect(mockPut).toHaveBeenCalledWith('/dm/messages/xyz', { content: 'New' })
    })

    it('returns typed DMMessage response', async () => {
      const resp = { id: 'msg-1', content: 'Updated', is_edited: true, conversation_id: 'conv-1' }
      mockPut.mockResolvedValue({ data: resp })

      const result = await editMessage('msg-1', 'Updated')

      expect(result.is_edited).toBe(true)
    })
  })

  // ============ recallMessage ============

  describe('recallMessage', () => {
    it('calls DELETE /dm/messages/{id}', async () => {
      mockDelete.mockResolvedValue({ data: { id: 'msg-1', is_recalled: true } })

      await recallMessage('msg-1')

      expect(mockDelete).toHaveBeenCalledWith('/dm/messages/msg-1')
    })

    it('includes message ID in URL', async () => {
      mockDelete.mockResolvedValue({ data: { id: 'abc-123' } })

      await recallMessage('abc-123')

      expect(mockDelete).toHaveBeenCalledWith('/dm/messages/abc-123')
    })

    it('returns the recalled message response', async () => {
      const resp = { id: 'msg-1', is_recalled: true, content: null }
      mockDelete.mockResolvedValue({ data: resp })

      const result = await recallMessage('msg-1')

      expect(result.is_recalled).toBe(true)
    })
  })

  // ============ markConversationRead ============

  describe('markConversationRead', () => {
    it('calls PUT /dm/conversations/{id}/read', async () => {
      mockPut.mockResolvedValue({})

      await markConversationRead('conv-1')

      expect(mockPut).toHaveBeenCalledWith('/dm/conversations/conv-1/read')
    })

    it('includes conversation ID in URL', async () => {
      mockPut.mockResolvedValue({})

      await markConversationRead('conv-xyz')

      expect(mockPut).toHaveBeenCalledWith('/dm/conversations/conv-xyz/read')
    })
  })

  // ============ getUnreadCount ============

  describe('getUnreadCount', () => {
    it('calls GET /dm/unread-count and returns typed response', async () => {
      mockGet.mockResolvedValue({ data: { unread_count: 5 } })

      const result = await getUnreadCount()

      expect(mockGet).toHaveBeenCalledWith('/dm/unread-count')
      expect(result).toEqual({ unread_count: 5 })
    })

    it('returns zero unread count', async () => {
      mockGet.mockResolvedValue({ data: { unread_count: 0 } })

      const result = await getUnreadCount()

      expect(result.unread_count).toBe(0)
    })
  })
})

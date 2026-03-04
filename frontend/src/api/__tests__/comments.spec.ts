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
  listComments,
  createComment,
  deleteComment,
  updateComment,
  toggleReaction,
} from '../comments'

describe('comments API', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('listComments', () => {
    it('calls GET /posts/{postId}/comments and returns data', async () => {
      const mockData = { comments: [], total: 0 }
      mockGet.mockResolvedValue({ data: mockData })

      const result = await listComments('post-1')

      expect(mockGet).toHaveBeenCalledWith('/posts/post-1/comments', { params: undefined })
      expect(result).toEqual(mockData)
    })

    it('passes page and page_size params', async () => {
      mockGet.mockResolvedValue({ data: { comments: [], total: 0 } })

      await listComments('post-1', { page: 2, page_size: 10 })

      expect(mockGet).toHaveBeenCalledWith('/posts/post-1/comments', {
        params: { page: 2, page_size: 10 },
      })
    })
  })

  describe('createComment', () => {
    it('calls POST /posts/{postId}/comments with content', async () => {
      const mockData = { id: 'c-1', content: 'Hello' }
      mockPost.mockResolvedValue({ data: mockData })

      const result = await createComment('post-1', { content: 'Hello' })

      expect(mockPost).toHaveBeenCalledWith('/posts/post-1/comments', { content: 'Hello' })
      expect(result).toEqual(mockData)
    })

    it('passes mentions array when provided', async () => {
      mockPost.mockResolvedValue({ data: { id: 'c-1' } })

      await createComment('post-1', { content: 'Hey @alice', mentions: ['alice'] })

      expect(mockPost).toHaveBeenCalledWith('/posts/post-1/comments', {
        content: 'Hey @alice',
        mentions: ['alice'],
      })
    })

    it('passes parent_id for replies', async () => {
      mockPost.mockResolvedValue({ data: { id: 'c-2' } })

      await createComment('post-1', { content: 'Reply', parent_id: 'c-1' })

      expect(mockPost).toHaveBeenCalledWith('/posts/post-1/comments', {
        content: 'Reply',
        parent_id: 'c-1',
      })
    })
  })

  describe('deleteComment', () => {
    it('calls DELETE /posts/{postId}/comments/{commentId}', async () => {
      mockDelete.mockResolvedValue({})

      await deleteComment('post-1', 'c-1')

      expect(mockDelete).toHaveBeenCalledWith('/posts/post-1/comments/c-1')
    })
  })

  describe('updateComment', () => {
    it('calls PUT /posts/{postId}/comments/{commentId} with content', async () => {
      const mockData = { id: 'c-1', content: 'Updated' }
      mockPut.mockResolvedValue({ data: mockData })

      const result = await updateComment('post-1', 'c-1', { content: 'Updated' })

      expect(mockPut).toHaveBeenCalledWith('/posts/post-1/comments/c-1', { content: 'Updated' })
      expect(result).toEqual(mockData)
    })
  })

  describe('toggleReaction', () => {
    it('calls POST /posts/{postId}/comments/{commentId}/reactions with reaction', async () => {
      mockPost.mockResolvedValue({})

      await toggleReaction('post-1', 'c-1', 'LIKE')

      expect(mockPost).toHaveBeenCalledWith('/posts/post-1/comments/c-1/reactions', {
        reaction: 'LIKE',
      })
    })
  })
})

import { describe, it, expect, vi, beforeEach } from 'vitest'

const mockGet = vi.fn()
const mockPost = vi.fn()
const mockDelete = vi.fn()

vi.mock('@/composables/api', () => ({
  default: {
    get: (...args: unknown[]) => mockGet(...args),
    post: (...args: unknown[]) => mockPost(...args),
    delete: (...args: unknown[]) => mockDelete(...args),
  },
}))

import { markBestAnswer, unmarkBestAnswer, voteOnAnswer, getUserVotes } from '../qa'

describe('qa API', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('markBestAnswer', () => {
    it('calls POST /qa/{postId}/best-answer with comment_id', async () => {
      mockPost.mockResolvedValue({ data: {} })

      await markBestAnswer('post-1', 'comment-1')

      expect(mockPost).toHaveBeenCalledWith('/qa/post-1/best-answer', {
        comment_id: 'comment-1',
      })
    })

    it('includes postId in the URL path', async () => {
      mockPost.mockResolvedValue({ data: {} })

      await markBestAnswer('abc-123', 'c-5')

      expect(mockPost).toHaveBeenCalledWith('/qa/abc-123/best-answer', {
        comment_id: 'c-5',
      })
    })
  })

  describe('unmarkBestAnswer', () => {
    it('calls DELETE /qa/{postId}/best-answer', async () => {
      mockDelete.mockResolvedValue({})

      await unmarkBestAnswer('post-1')

      expect(mockDelete).toHaveBeenCalledWith('/qa/post-1/best-answer')
    })

    it('includes postId in the URL path', async () => {
      mockDelete.mockResolvedValue({})

      await unmarkBestAnswer('xyz-789')

      expect(mockDelete).toHaveBeenCalledWith('/qa/xyz-789/best-answer')
    })
  })

  describe('voteOnAnswer', () => {
    it('calls POST /qa/comments/{commentId}/vote with upvote', async () => {
      mockPost.mockResolvedValue({ data: {} })

      await voteOnAnswer('c-1', 1)

      expect(mockPost).toHaveBeenCalledWith('/qa/comments/c-1/vote', { vote: 1 })
    })

    it('calls POST /qa/comments/{commentId}/vote with downvote', async () => {
      mockPost.mockResolvedValue({ data: {} })

      await voteOnAnswer('c-2', -1)

      expect(mockPost).toHaveBeenCalledWith('/qa/comments/c-2/vote', { vote: -1 })
    })

    it('calls POST /qa/comments/{commentId}/vote with zero (remove vote)', async () => {
      mockPost.mockResolvedValue({ data: {} })

      await voteOnAnswer('c-3', 0)

      expect(mockPost).toHaveBeenCalledWith('/qa/comments/c-3/vote', { vote: 0 })
    })
  })

  describe('getUserVotes', () => {
    it('calls GET /qa/{postId}/votes', async () => {
      const votes = [{ comment_id: 'c-1', vote: 1 }]
      mockGet.mockResolvedValue({ data: votes })

      const result = await getUserVotes('post-1')

      expect(mockGet).toHaveBeenCalledWith('/qa/post-1/votes')
      expect(result.data).toEqual(votes)
    })

    it('includes postId in the URL path', async () => {
      mockGet.mockResolvedValue({ data: [] })

      await getUserVotes('abc-xyz')

      expect(mockGet).toHaveBeenCalledWith('/qa/abc-xyz/votes')
    })

    it('returns empty array when user has no votes', async () => {
      mockGet.mockResolvedValue({ data: [] })

      const result = await getUserVotes('post-1')

      expect(result.data).toEqual([])
    })

    it('returns multiple votes for a post', async () => {
      const votes = [
        { comment_id: 'c-1', vote: 1 },
        { comment_id: 'c-2', vote: -1 },
      ]
      mockGet.mockResolvedValue({ data: votes })

      const result = await getUserVotes('post-1')

      expect(result.data).toHaveLength(2)
      expect(result.data[0]).toEqual({ comment_id: 'c-1', vote: 1 })
      expect(result.data[1]).toEqual({ comment_id: 'c-2', vote: -1 })
    })
  })
})

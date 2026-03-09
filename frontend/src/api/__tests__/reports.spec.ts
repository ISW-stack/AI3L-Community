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

import { createReport } from '../reports'

describe('reports API', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('createReport', () => {
    it('calls POST /posts/:postId/report with reason', async () => {
      mockPost.mockResolvedValue({})

      await createReport('post-1', 'Spam content')

      expect(mockPost).toHaveBeenCalledWith('/posts/post-1/report', { reason: 'Spam content' })
    })

    it('includes the post id in the URL path', async () => {
      const postId = 'abc-123'
      mockPost.mockResolvedValue({})

      await createReport(postId, 'Offensive')

      expect(mockPost).toHaveBeenCalledWith(`/posts/${postId}/report`, { reason: 'Offensive' })
    })

    it('calls POST exactly once', async () => {
      mockPost.mockResolvedValue({})

      await createReport('p1', 'reason')

      expect(mockPost).toHaveBeenCalledTimes(1)
    })

    it('does not use GET, PUT, or DELETE', async () => {
      mockPost.mockResolvedValue({})

      await createReport('p1', 'reason')

      expect(mockGet).not.toHaveBeenCalled()
      expect(mockPut).not.toHaveBeenCalled()
      expect(mockDelete).not.toHaveBeenCalled()
    })

    it('returns void', async () => {
      mockPost.mockResolvedValue({})

      const result = await createReport('p1', 'reason')

      expect(result).toBeUndefined()
    })

    it('propagates API errors', async () => {
      mockPost.mockRejectedValue(new Error('Forbidden'))

      await expect(createReport('p1', 'reason')).rejects.toThrow('Forbidden')
    })
  })
})

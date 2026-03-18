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

import { leaveCoAuthorship } from '../coauthors'

describe('coauthors API - leaveCoAuthorship', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('calls DELETE /co-authors/posts/{postId}/{coAuthorId}/leave', async () => {
    mockDelete.mockResolvedValue({})

    await leaveCoAuthorship('post-1', 'ca-1')

    expect(mockDelete).toHaveBeenCalledWith('/co-authors/posts/post-1/ca-1/leave')
  })

  it('calls DELETE exactly once', async () => {
    mockDelete.mockResolvedValue({})

    await leaveCoAuthorship('post-1', 'ca-1')

    expect(mockDelete).toHaveBeenCalledTimes(1)
  })

  it('does not use GET, POST, or PUT', async () => {
    mockDelete.mockResolvedValue({})

    await leaveCoAuthorship('post-1', 'ca-1')

    expect(mockGet).not.toHaveBeenCalled()
    expect(mockPost).not.toHaveBeenCalled()
    expect(mockPut).not.toHaveBeenCalled()
  })

  it('returns void', async () => {
    mockDelete.mockResolvedValue({})

    const result = await leaveCoAuthorship('post-1', 'ca-1')

    expect(result).toBeUndefined()
  })

  it('propagates API errors', async () => {
    mockDelete.mockRejectedValue(new Error('Forbidden'))

    await expect(leaveCoAuthorship('post-1', 'ca-1')).rejects.toThrow('Forbidden')
  })
})

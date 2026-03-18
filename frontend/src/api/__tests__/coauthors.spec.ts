import { describe, it, expect, vi, beforeEach } from 'vitest'

const mockGet = vi.fn()
const mockPost = vi.fn()
const mockDelete = vi.fn()
const mockPut = vi.fn()

vi.mock('@/composables/api', () => ({
  default: {
    get: (...args: unknown[]) => mockGet(...args),
    post: (...args: unknown[]) => mockPost(...args),
    delete: (...args: unknown[]) => mockDelete(...args),
    put: (...args: unknown[]) => mockPut(...args),
  },
}))

import {
  listCoAuthors,
  listAllCoAuthors,
  inviteCoAuthor,
  addExternalCoAuthor,
  removeCoAuthor,
  listMyInvitations,
  acceptInvitation,
  rejectInvitation,
  listCoAuthoredPosts,
  searchUsers,
} from '@/api/coauthors'

describe('coauthors API', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('listCoAuthors', () => {
    it('calls GET /co-authors/posts/{postId}', async () => {
      const mockData = { co_authors: [] }
      mockGet.mockResolvedValue({ data: mockData })

      const result = await listCoAuthors('post-123')

      expect(mockGet).toHaveBeenCalledWith('/co-authors/posts/post-123')
      expect(result).toEqual(mockData)
    })

    it('does NOT call /posts/{postId}/co-authors (old wrong URL)', async () => {
      mockGet.mockResolvedValue({ data: { co_authors: [] } })

      await listCoAuthors('post-abc')

      const calledUrl = mockGet.mock.calls[0][0] as string
      expect(calledUrl).not.toMatch(/^\/posts\//)
      expect(calledUrl).toBe('/co-authors/posts/post-abc')
    })
  })

  describe('listAllCoAuthors', () => {
    it('calls GET /co-authors/posts/{postId}/all', async () => {
      const mockData = { co_authors: [{ id: '1', status: 'PENDING' }] }
      mockGet.mockResolvedValue({ data: mockData })

      const result = await listAllCoAuthors('post-456')

      expect(mockGet).toHaveBeenCalledWith('/co-authors/posts/post-456/all')
      expect(result).toEqual(mockData)
    })
  })

  describe('inviteCoAuthor', () => {
    it('calls POST /co-authors/posts/{postId}/invite', async () => {
      mockPost.mockResolvedValue({ data: {} })
      const inviteData = { user_id: 'u-1', display_name: 'Test User' }

      await inviteCoAuthor('post-789', inviteData)

      expect(mockPost).toHaveBeenCalledWith('/co-authors/posts/post-789/invite', inviteData)
    })

    it('does NOT call /posts/{postId}/co-authors/invite (old wrong URL)', async () => {
      mockPost.mockResolvedValue({ data: {} })

      await inviteCoAuthor('post-x', { user_id: 'u-1' })

      const calledUrl = mockPost.mock.calls[0][0] as string
      expect(calledUrl).not.toMatch(/^\/posts\//)
    })
  })

  describe('addExternalCoAuthor', () => {
    it('calls POST /co-authors/posts/{postId}/external', async () => {
      mockPost.mockResolvedValue({ data: {} })
      const authorData = { display_name: 'External Author', affiliation: 'MIT' }

      await addExternalCoAuthor('post-ext', authorData)

      expect(mockPost).toHaveBeenCalledWith('/co-authors/posts/post-ext/external', authorData)
    })

    it('does NOT call /posts/{postId}/co-authors/external (old wrong URL)', async () => {
      mockPost.mockResolvedValue({ data: {} })

      await addExternalCoAuthor('post-y', { display_name: 'Author' })

      const calledUrl = mockPost.mock.calls[0][0] as string
      expect(calledUrl).not.toMatch(/^\/posts\//)
    })
  })

  describe('removeCoAuthor', () => {
    it('calls DELETE /co-authors/posts/{postId}/{coAuthorId}', async () => {
      mockDelete.mockResolvedValue({ data: {} })

      await removeCoAuthor('post-del', 'ca-1')

      expect(mockDelete).toHaveBeenCalledWith('/co-authors/posts/post-del/ca-1')
    })

    it('does NOT call /posts/{postId}/co-authors/{coAuthorId} (old wrong URL)', async () => {
      mockDelete.mockResolvedValue({ data: {} })

      await removeCoAuthor('post-z', 'ca-2')

      const calledUrl = mockDelete.mock.calls[0][0] as string
      expect(calledUrl).not.toMatch(/^\/posts\//)
    })
  })

  describe('listMyInvitations', () => {
    it('calls GET /users/me/co-author-invitations with pagination', async () => {
      const mockData = { invitations: [], total: 0 }
      mockGet.mockResolvedValue({ data: mockData })

      const result = await listMyInvitations(2, 10)

      expect(mockGet).toHaveBeenCalledWith('/users/me/co-author-invitations', {
        params: { page: 2, page_size: 10 },
      })
      expect(result).toEqual(mockData)
    })

    it('uses default pagination values', async () => {
      mockGet.mockResolvedValue({ data: { invitations: [], total: 0 } })

      await listMyInvitations()

      expect(mockGet).toHaveBeenCalledWith('/users/me/co-author-invitations', {
        params: { page: 1, page_size: 20 },
      })
    })
  })

  describe('acceptInvitation', () => {
    it('calls PUT /users/me/co-author-invitations/{id}/accept', async () => {
      mockPut.mockResolvedValue({ data: {} })

      await acceptInvitation('inv-1')

      expect(mockPut).toHaveBeenCalledWith('/users/me/co-author-invitations/inv-1/accept')
    })
  })

  describe('rejectInvitation', () => {
    it('calls PUT /users/me/co-author-invitations/{id}/reject', async () => {
      mockPut.mockResolvedValue({ data: {} })

      await rejectInvitation('inv-2')

      expect(mockPut).toHaveBeenCalledWith('/users/me/co-author-invitations/inv-2/reject')
    })
  })

  describe('listCoAuthoredPosts', () => {
    it('calls GET /co-authors/user/{userId}/posts with pagination', async () => {
      const mockData = { posts: [], total: 0 }
      mockGet.mockResolvedValue({ data: mockData })

      const result = await listCoAuthoredPosts('user-1', 1, 10)

      expect(mockGet).toHaveBeenCalledWith('/co-authors/user/user-1/posts', {
        params: { page: 1, page_size: 10 },
      })
      expect(result).toEqual(mockData)
    })
  })

  describe('searchUsers', () => {
    it('calls GET /users/search with query and limit', async () => {
      const mockData = [{ id: 'u-1', username: 'test', display_name: 'Test', avatar_url: null }]
      mockGet.mockResolvedValue({ data: mockData })

      const result = await searchUsers('test', 3)

      expect(mockGet).toHaveBeenCalledWith('/users/search', {
        params: { q: 'test', limit: 3 },
      })
      expect(result).toEqual(mockData)
    })

    it('uses default limit of 5', async () => {
      mockGet.mockResolvedValue({ data: [] })

      await searchUsers('query')

      expect(mockGet).toHaveBeenCalledWith('/users/search', {
        params: { q: 'query', limit: 5 },
      })
    })
  })
})

import { describe, it, expect, vi, beforeEach } from 'vitest'

const mockGet = vi.fn()
const mockPost = vi.fn()
const mockPut = vi.fn()
const mockDelete = vi.fn()
const mockPatch = vi.fn()

vi.mock('@/composables/api', () => ({
  default: {
    get: (...args: unknown[]) => mockGet(...args),
    post: (...args: unknown[]) => mockPost(...args),
    put: (...args: unknown[]) => mockPut(...args),
    delete: (...args: unknown[]) => mockDelete(...args),
    patch: (...args: unknown[]) => mockPatch(...args),
  },
}))

import {
  listPosts,
  getPost,
  createPost,
  updatePost,
  deletePost,
  searchPosts,
  getPostHistory,
  getTrendingPosts,
  togglePinPost,
} from '../posts'

describe('posts API', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('listPosts', () => {
    it('calls GET /posts with params and returns data', async () => {
      const params = { page: 1, page_size: 10, category_id: 'cat-1' }
      const mockData = { posts: [], total: 0 }
      mockGet.mockResolvedValue({ data: mockData })

      const result = await listPosts(params)

      expect(mockGet).toHaveBeenCalledWith('/posts', { params })
      expect(result).toEqual(mockData)
    })

    it('calls GET /posts with empty params object', async () => {
      mockGet.mockResolvedValue({ data: { posts: [], total: 0 } })

      await listPosts({})

      expect(mockGet).toHaveBeenCalledWith('/posts', { params: {} })
    })

    it('calls GET /posts with sort and author_id params', async () => {
      const params = { sort: 'trending', page: 2, page_size: 5, author_id: 'u-1' }
      mockGet.mockResolvedValue({ data: { posts: [], total: 0 } })

      await listPosts(params)

      expect(mockGet).toHaveBeenCalledWith('/posts', { params })
    })
  })

  describe('getPost', () => {
    it('calls GET /posts/{postId} and returns data', async () => {
      const mockData = { id: 'post-1', title: 'Test Post', content: 'Body' }
      mockGet.mockResolvedValue({ data: mockData })

      const result = await getPost('post-1')

      expect(mockGet).toHaveBeenCalledWith('/posts/post-1')
      expect(result).toEqual(mockData)
    })

    it('includes postId in the URL path', async () => {
      mockGet.mockResolvedValue({ data: { id: 'abc-123' } })

      await getPost('abc-123')

      expect(mockGet).toHaveBeenCalledWith('/posts/abc-123')
    })
  })

  describe('createPost', () => {
    it('calls POST /posts with payload and returns data', async () => {
      const payload = { title: 'New Post', content: '<p>Hello</p>', category_id: 'cat-1' }
      const mockData = { id: 'new-post-id', title: 'New Post' }
      mockPost.mockResolvedValue({ data: mockData })

      const result = await createPost(payload)

      expect(mockPost).toHaveBeenCalledWith('/posts', payload)
      expect(result).toEqual(mockData)
    })

    it('calls POST /posts with all optional fields', async () => {
      const payload = {
        title: 'Full Post',
        content: '<p>Content</p>',
        category_id: 'cat-2',
        sig_id: 'sig-1',
        keywords: ['ai', 'ml'],
        allow_comments: false,
      }
      mockPost.mockResolvedValue({ data: { id: 'p-1' } })

      await createPost(payload)

      expect(mockPost).toHaveBeenCalledWith('/posts', payload)
    })
  })

  describe('updatePost', () => {
    it('calls PUT /posts/{postId} with payload and returns data', async () => {
      const payload = { title: 'Updated Title', version: 2 }
      const mockData = { id: 'post-1', title: 'Updated Title' }
      mockPut.mockResolvedValue({ data: mockData })

      const result = await updatePost('post-1', payload)

      expect(mockPut).toHaveBeenCalledWith('/posts/post-1', payload)
      expect(result).toEqual(mockData)
    })

    it('includes postId in the URL path', async () => {
      mockPut.mockResolvedValue({ data: { id: 'xyz' } })

      await updatePost('xyz', { version: 1 })

      expect(mockPut).toHaveBeenCalledWith('/posts/xyz', { version: 1 })
    })
  })

  describe('deletePost', () => {
    it('calls DELETE /posts/{postId}', async () => {
      mockDelete.mockResolvedValue({})

      await deletePost('post-1')

      expect(mockDelete).toHaveBeenCalledWith('/posts/post-1')
    })

    it('includes postId in the URL path', async () => {
      mockDelete.mockResolvedValue({})

      await deletePost('abc-xyz')

      expect(mockDelete).toHaveBeenCalledWith('/posts/abc-xyz')
    })

    it('does not use GET, POST, or PUT', async () => {
      mockDelete.mockResolvedValue({})

      await deletePost('p1')

      expect(mockGet).not.toHaveBeenCalled()
      expect(mockPost).not.toHaveBeenCalled()
      expect(mockPut).not.toHaveBeenCalled()
    })
  })

  describe('searchPosts', () => {
    it('calls POST /posts/search with payload and returns data', async () => {
      const payload = { keyword: 'machine learning', page: 1, page_size: 10 }
      const mockData = { posts: [], total: 0 }
      mockPost.mockResolvedValue({ data: mockData })

      const result = await searchPosts(payload)

      expect(mockPost).toHaveBeenCalledWith('/posts/search', payload)
      expect(result).toEqual(mockData)
    })

    it('calls POST /posts/search with full payload', async () => {
      const payload = {
        keyword: 'ai',
        category_id: 'cat-1',
        keywords: ['nlp'],
        date_from: '2025-01-01',
        date_to: '2025-12-31',
        logic: 'AND',
        page: 2,
        page_size: 5,
      }
      mockPost.mockResolvedValue({ data: { posts: [], total: 0 } })

      await searchPosts(payload)

      expect(mockPost).toHaveBeenCalledWith('/posts/search', payload)
    })

    it('calls POST /posts/search with empty payload', async () => {
      mockPost.mockResolvedValue({ data: { posts: [], total: 0 } })

      await searchPosts({})

      expect(mockPost).toHaveBeenCalledWith('/posts/search', {})
    })
  })

  describe('getPostHistory', () => {
    it('calls GET /posts/{postId}/history and returns data.history', async () => {
      const history = [
        { id: 'h-1', title: 'Old Title', edited_at: '2025-01-01T00:00:00Z' },
        { id: 'h-2', title: 'Older Title', edited_at: '2024-12-31T00:00:00Z' },
      ]
      mockGet.mockResolvedValue({ data: { history } })

      const result = await getPostHistory('post-1')

      expect(mockGet).toHaveBeenCalledWith('/posts/post-1/history')
      expect(result).toEqual(history)
    })

    it('returns the history array directly, not the wrapper object', async () => {
      const history = [{ id: 'h-1' }]
      mockGet.mockResolvedValue({ data: { history } })

      const result = await getPostHistory('post-1')

      expect(Array.isArray(result)).toBe(true)
      expect(result).toHaveLength(1)
    })

    it('returns empty array when history is empty', async () => {
      mockGet.mockResolvedValue({ data: { history: [] } })

      const result = await getPostHistory('post-2')

      expect(result).toEqual([])
    })
  })

  describe('getTrendingPosts', () => {
    it('calls GET /posts/trending and returns data', async () => {
      const mockData = [
        { id: 't-1', title: 'Trending' },
        { id: 't-2', title: 'Popular' },
      ]
      mockGet.mockResolvedValue({ data: mockData })

      const result = await getTrendingPosts()

      expect(mockGet).toHaveBeenCalledWith('/posts/trending', { params: {} })
      expect(result).toEqual(mockData)
    })

    it('calls GET /posts/trending exactly once with no params', async () => {
      mockGet.mockResolvedValue({ data: [] })

      await getTrendingPosts()

      expect(mockGet).toHaveBeenCalledTimes(1)
      expect(mockGet).toHaveBeenCalledWith('/posts/trending', { params: {} })
    })

    it('passes type param when provided', async () => {
      mockGet.mockResolvedValue({ data: [] })

      await getTrendingPosts('question')

      expect(mockGet).toHaveBeenCalledWith('/posts/trending', { params: { type: 'question' } })
    })
  })

  describe('togglePinPost', () => {
    it('calls PATCH /posts/{postId}/pin with is_pinned true', async () => {
      const mockData = { is_pinned: true }
      mockPatch.mockResolvedValue({ data: mockData })

      const result = await togglePinPost('post-1', true)

      expect(mockPatch).toHaveBeenCalledWith('/posts/post-1/pin', { is_pinned: true })
      expect(result).toEqual(mockData)
    })

    it('calls PATCH /posts/{postId}/pin with is_pinned false', async () => {
      const mockData = { is_pinned: false }
      mockPatch.mockResolvedValue({ data: mockData })

      const result = await togglePinPost('post-2', false)

      expect(mockPatch).toHaveBeenCalledWith('/posts/post-2/pin', { is_pinned: false })
      expect(result).toEqual(mockData)
    })

    it('includes postId in the URL path', async () => {
      mockPatch.mockResolvedValue({ data: { is_pinned: true } })

      await togglePinPost('abc-xyz', true)

      expect(mockPatch).toHaveBeenCalledWith('/posts/abc-xyz/pin', { is_pinned: true })
    })

    it('returns the is_pinned boolean result', async () => {
      mockPatch.mockResolvedValue({ data: { is_pinned: true } })

      const result = await togglePinPost('post-1', true)

      expect(result.is_pinned).toBe(true)
    })
  })
})

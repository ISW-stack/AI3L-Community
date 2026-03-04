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
  listCategories,
  getCategory,
  createCategory,
  updateCategory,
  deleteCategory,
} from '../categories'

describe('categories API', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('listCategories', () => {
    it('calls GET /categories and returns categories array', async () => {
      const cats = [
        { id: 'c-1', name: 'Science', description: 'Science topics', post_count: 5 },
        { id: 'c-2', name: 'Tech', description: 'Tech topics', post_count: 3 },
      ]
      mockGet.mockResolvedValue({ data: { categories: cats } })

      const result = await listCategories()

      expect(mockGet).toHaveBeenCalledWith('/categories')
      expect(result).toEqual(cats)
    })

    it('returns empty array when no categories', async () => {
      mockGet.mockResolvedValue({ data: { categories: [] } })

      const result = await listCategories()

      expect(result).toEqual([])
    })
  })

  describe('getCategory', () => {
    it('calls GET /categories/{categoryId} and returns data', async () => {
      const mockData = { id: 'c-1', name: 'Science', description: 'Science topics', post_count: 5 }
      mockGet.mockResolvedValue({ data: mockData })

      const result = await getCategory('c-1')

      expect(mockGet).toHaveBeenCalledWith('/categories/c-1')
      expect(result).toEqual(mockData)
    })

    it('includes categoryId in the URL path', async () => {
      mockGet.mockResolvedValue({ data: { id: 'abc-123' } })

      await getCategory('abc-123')

      expect(mockGet).toHaveBeenCalledWith('/categories/abc-123')
    })

    it('returns category with post_count', async () => {
      const mockData = { id: 'c-1', name: 'AI', post_count: 42 }
      mockGet.mockResolvedValue({ data: mockData })

      const result = await getCategory('c-1')

      expect(result.post_count).toBe(42)
    })
  })

  describe('createCategory', () => {
    it('calls POST /categories with payload and returns data', async () => {
      const payload = { name: 'Science', description: 'Science topics' }
      const mockData = { id: 'c-new', name: 'Science', description: 'Science topics' }
      mockPost.mockResolvedValue({ data: mockData })

      const result = await createCategory(payload)

      expect(mockPost).toHaveBeenCalledWith('/categories', payload)
      expect(result).toEqual(mockData)
    })

    it('calls POST /categories with name only', async () => {
      const payload = { name: 'General' }
      mockPost.mockResolvedValue({ data: { id: 'c-new', name: 'General' } })

      await createCategory(payload)

      expect(mockPost).toHaveBeenCalledWith('/categories', payload)
    })
  })

  describe('updateCategory', () => {
    it('calls PUT /categories/{categoryId} with payload and returns data', async () => {
      const payload = { name: 'Updated Science', description: 'Updated' }
      const mockData = { id: 'c-1', name: 'Updated Science' }
      mockPut.mockResolvedValue({ data: mockData })

      const result = await updateCategory('c-1', payload)

      expect(mockPut).toHaveBeenCalledWith('/categories/c-1', payload)
      expect(result).toEqual(mockData)
    })

    it('includes categoryId in the URL path', async () => {
      mockPut.mockResolvedValue({ data: { id: 'xyz' } })

      await updateCategory('xyz', { name: 'New Name' })

      expect(mockPut).toHaveBeenCalledWith('/categories/xyz', { name: 'New Name' })
    })
  })

  describe('deleteCategory', () => {
    it('calls DELETE /categories/{categoryId}', async () => {
      mockDelete.mockResolvedValue({})

      await deleteCategory('c-1')

      expect(mockDelete).toHaveBeenCalledWith('/categories/c-1')
    })

    it('does not use GET, POST, or PUT', async () => {
      mockDelete.mockResolvedValue({})

      await deleteCategory('c-1')

      expect(mockGet).not.toHaveBeenCalled()
      expect(mockPost).not.toHaveBeenCalled()
      expect(mockPut).not.toHaveBeenCalled()
    })
  })
})

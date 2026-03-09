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
  listContributors,
  createContributor,
  updateContributor,
  deleteContributor,
} from '../contributors'

describe('contributors API', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('listContributors', () => {
    it('calls GET /about/admin/contributors and returns contributors array', async () => {
      const contributors = [
        { id: '1', name: 'Alice', github_username: 'alice', role: 'Developer' },
        { id: '2', name: 'Bob', github_username: 'bob', role: 'Designer' },
      ]
      mockGet.mockResolvedValue({ data: { contributors } })

      const result = await listContributors()

      expect(mockGet).toHaveBeenCalledWith('/about/admin/contributors')
      expect(result).toEqual(contributors)
    })

    it('calls GET exactly once', async () => {
      mockGet.mockResolvedValue({ data: { contributors: [] } })

      await listContributors()

      expect(mockGet).toHaveBeenCalledTimes(1)
    })

    it('returns empty array when no contributors', async () => {
      mockGet.mockResolvedValue({ data: { contributors: [] } })

      const result = await listContributors()

      expect(result).toEqual([])
    })

    it('propagates API errors', async () => {
      mockGet.mockRejectedValue(new Error('Network error'))

      await expect(listContributors()).rejects.toThrow('Network error')
    })
  })

  describe('createContributor', () => {
    it('calls POST /about/admin/contributors with payload and returns contributor', async () => {
      const payload = { name: 'Charlie', github_username: 'charlie', role: 'Tester' }
      const created = { id: '3', ...payload }
      mockPost.mockResolvedValue({ data: created })

      const result = await createContributor(payload as never)

      expect(mockPost).toHaveBeenCalledWith('/about/admin/contributors', payload)
      expect(result).toEqual(created)
    })

    it('calls POST exactly once', async () => {
      mockPost.mockResolvedValue({ data: { id: '3', name: 'C' } })

      await createContributor({ name: 'C' } as never)

      expect(mockPost).toHaveBeenCalledTimes(1)
    })

    it('propagates API errors', async () => {
      mockPost.mockRejectedValue(new Error('Forbidden'))

      await expect(createContributor({ name: 'X' } as never)).rejects.toThrow('Forbidden')
    })
  })

  describe('updateContributor', () => {
    it('calls PUT /about/admin/contributors/:id with payload and returns updated contributor', async () => {
      const payload = { name: 'Alice Updated' }
      const updated = { id: '1', name: 'Alice Updated', github_username: 'alice', role: 'Lead' }
      mockPut.mockResolvedValue({ data: updated })

      const result = await updateContributor('1', payload as never)

      expect(mockPut).toHaveBeenCalledWith('/about/admin/contributors/1', payload)
      expect(result).toEqual(updated)
    })

    it('includes the contributor id in the URL path', async () => {
      const id = 'abc-123'
      mockPut.mockResolvedValue({ data: { id } })

      await updateContributor(id, { name: 'Updated' } as never)

      expect(mockPut).toHaveBeenCalledWith(`/about/admin/contributors/${id}`, { name: 'Updated' })
    })

    it('propagates API errors', async () => {
      mockPut.mockRejectedValue(new Error('Not found'))

      await expect(updateContributor('999', {} as never)).rejects.toThrow('Not found')
    })
  })

  describe('deleteContributor', () => {
    it('calls DELETE /about/admin/contributors/:id', async () => {
      mockDelete.mockResolvedValue({})

      await deleteContributor('1')

      expect(mockDelete).toHaveBeenCalledWith('/about/admin/contributors/1')
    })

    it('includes the contributor id in the URL path', async () => {
      const id = 'xyz-789'
      mockDelete.mockResolvedValue({})

      await deleteContributor(id)

      expect(mockDelete).toHaveBeenCalledWith(`/about/admin/contributors/${id}`)
    })

    it('returns void', async () => {
      mockDelete.mockResolvedValue({})

      const result = await deleteContributor('1')

      expect(result).toBeUndefined()
    })

    it('propagates API errors', async () => {
      mockDelete.mockRejectedValue(new Error('Unauthorized'))

      await expect(deleteContributor('1')).rejects.toThrow('Unauthorized')
    })
  })
})

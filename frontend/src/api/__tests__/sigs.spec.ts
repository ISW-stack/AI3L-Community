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
  listSigs,
  getSig,
  updateSig,
  deleteSig,
  getSigPosts,
  getSigMembers,
  getSigForms,
  leaveSig,
  removeMember,
  assignSubAdmin,
  demoteSubAdmin,
  createSig,
  listMySigs,
  joinSig,
} from '../sigs'

describe('sigs API', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('listSigs', () => {
    it('calls GET /sigs and returns data', async () => {
      const mockData = { sigs: [], total: 0 }
      mockGet.mockResolvedValue({ data: mockData })

      const result = await listSigs()

      expect(mockGet).toHaveBeenCalledWith('/sigs')
      expect(result).toEqual(mockData)
    })
  })

  describe('getSig', () => {
    it('calls GET /sigs/{sigId} with correct URL', async () => {
      const sigId = 'sig-abc'
      const mockData = { id: sigId, name: 'Test SIG' }
      mockGet.mockResolvedValue({ data: mockData })

      const result = await getSig(sigId)

      expect(mockGet).toHaveBeenCalledWith(`/sigs/${sigId}`)
      expect(result).toEqual(mockData)
    })
  })

  describe('updateSig', () => {
    it('calls PUT /sigs/{sigId} with payload and returns data', async () => {
      const sigId = 'sig-123'
      const payload = { name: 'Updated SIG', description: 'New desc' }
      const mockData = { id: sigId, ...payload }
      mockPut.mockResolvedValue({ data: mockData })

      const result = await updateSig(sigId, payload)

      expect(mockPut).toHaveBeenCalledWith(`/sigs/${sigId}`, payload)
      expect(result).toEqual(mockData)
    })

    it('supports null description', async () => {
      const sigId = 'sig-456'
      const payload = { name: 'No Desc SIG', description: null }
      mockPut.mockResolvedValue({ data: { id: sigId, ...payload } })

      await updateSig(sigId, payload)

      expect(mockPut).toHaveBeenCalledWith(`/sigs/${sigId}`, payload)
    })
  })

  describe('deleteSig', () => {
    it('calls DELETE /sigs/{sigId} and returns undefined', async () => {
      mockDelete.mockResolvedValue({})
      const sigId = 'sig-del'

      const result = await deleteSig(sigId)

      expect(mockDelete).toHaveBeenCalledWith(`/sigs/${sigId}`)
      expect(result).toBeUndefined()
    })
  })

  describe('getSigPosts', () => {
    it('calls GET /sigs/{sigId}/posts and returns data', async () => {
      const sigId = 'sig-posts'
      const mockData = { posts: [], total: 0 }
      mockGet.mockResolvedValue({ data: mockData })

      const result = await getSigPosts(sigId)

      expect(mockGet).toHaveBeenCalledWith(`/sigs/${sigId}/posts`, { params: undefined })
      expect(result).toEqual(mockData)
    })
  })

  describe('getSigMembers', () => {
    it('calls GET /sigs/{sigId}/members and returns data', async () => {
      const sigId = 'sig-members'
      const mockData = { members: [], total: 0 }
      mockGet.mockResolvedValue({ data: mockData })

      const result = await getSigMembers(sigId)

      expect(mockGet).toHaveBeenCalledWith(`/sigs/${sigId}/members`, { params: undefined })
      expect(result).toEqual(mockData)
    })
  })

  describe('getSigForms', () => {
    it('calls GET /sigs/{sigId}/forms and returns data', async () => {
      const sigId = 'sig-forms'
      const mockData = { forms: [], total: 0 }
      mockGet.mockResolvedValue({ data: mockData })

      const result = await getSigForms(sigId)

      expect(mockGet).toHaveBeenCalledWith(`/sigs/${sigId}/forms`)
      expect(result).toEqual(mockData)
    })
  })

  describe('leaveSig', () => {
    it('calls DELETE /sigs/{sigId}/members/me and returns undefined', async () => {
      mockDelete.mockResolvedValue({})
      const sigId = 'sig-leave'

      const result = await leaveSig(sigId)

      expect(mockDelete).toHaveBeenCalledWith(`/sigs/${sigId}/members/me`)
      expect(result).toBeUndefined()
    })
  })

  describe('removeMember', () => {
    it('calls DELETE /sigs/{sigId}/members/{userId} and returns undefined', async () => {
      mockDelete.mockResolvedValue({})
      const sigId = 'sig-rm'
      const userId = 'user-rm'

      const result = await removeMember(sigId, userId)

      expect(mockDelete).toHaveBeenCalledWith(`/sigs/${sigId}/members/${userId}`)
      expect(result).toBeUndefined()
    })
  })

  describe('assignSubAdmin', () => {
    it('calls POST /sigs/{sigId}/sub-admin with user_id payload', async () => {
      const sigId = 'sig-sa'
      const userId = 'user-sa'
      const mockData = { id: userId, sig_role: 'SUB_ADMIN' }
      mockPost.mockResolvedValue({ data: mockData })

      const result = await assignSubAdmin(sigId, userId)

      expect(mockPost).toHaveBeenCalledWith(`/sigs/${sigId}/sub-admin`, { user_id: userId })
      expect(result).toEqual(mockData)
    })
  })

  describe('demoteSubAdmin', () => {
    it('calls POST /sigs/{sigId}/sub-admin/demote with user_id payload', async () => {
      const sigId = 'sig-sa'
      const userId = 'user-sa'
      const mockData = { id: userId, sig_role: 'MEMBER' }
      mockPost.mockResolvedValue({ data: mockData })

      const result = await demoteSubAdmin(sigId, userId)

      expect(mockPost).toHaveBeenCalledWith(`/sigs/${sigId}/sub-admin/demote`, { user_id: userId })
      expect(result).toEqual(mockData)
    })

    it('does not use DELETE or PUT for demotion', async () => {
      mockPost.mockResolvedValue({ data: {} })

      await demoteSubAdmin('sig-1', 'user-1')

      expect(mockDelete).not.toHaveBeenCalled()
      expect(mockPut).not.toHaveBeenCalled()
    })
  })

  describe('createSig', () => {
    it('calls POST /sigs with payload and returns data', async () => {
      const payload = { name: 'New SIG', description: 'A test SIG' }
      const mockData = { id: 'new-sig', ...payload }
      mockPost.mockResolvedValue({ data: mockData })

      const result = await createSig(payload)

      expect(mockPost).toHaveBeenCalledWith('/sigs', payload)
      expect(result).toEqual(mockData)
    })

    it('supports null description', async () => {
      const payload = { name: 'No Desc SIG', description: null }
      mockPost.mockResolvedValue({ data: { id: 'sig-nd', ...payload } })

      await createSig(payload)

      expect(mockPost).toHaveBeenCalledWith('/sigs', payload)
    })
  })

  describe('listMySigs', () => {
    it('calls GET /sigs/my and returns the inner sigs array', async () => {
      const sigsArray = [{ id: 'sig-1', name: 'My SIG' }]
      mockGet.mockResolvedValue({ data: { sigs: sigsArray } })

      const result = await listMySigs()

      expect(mockGet).toHaveBeenCalledWith('/sigs/my')
      expect(result).toEqual(sigsArray)
    })

    it('returns empty array when no sigs', async () => {
      mockGet.mockResolvedValue({ data: { sigs: [] } })

      const result = await listMySigs()

      expect(result).toEqual([])
    })
  })

  describe('joinSig', () => {
    it('calls POST /sigs/{sigId}/members/me and returns data', async () => {
      const sigId = 'sig-join'
      const mockData = { id: 'user-1', sig_role: 'MEMBER' }
      mockPost.mockResolvedValue({ data: mockData })

      const result = await joinSig(sigId)

      expect(mockPost).toHaveBeenCalledWith(`/sigs/${sigId}/members/me`)
      expect(result).toEqual(mockData)
    })
  })
})

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
  getDashboard,
  listUsers,
  createAccount,
  changeRole,
  banUser,
  unbanUser,
  getAuditLogs,
  listApplications,
  reviewApplication,
  listReports,
  reviewReport,
  listInviteCodes,
  createInviteCode,
  revokeInviteCode,
  deleteInviteCode,
} from '../admin'

describe('admin API', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('getDashboard', () => {
    it('calls GET /admin/dashboard and returns data', async () => {
      const mockData = { total_users: 10, total_posts: 5 }
      mockGet.mockResolvedValue({ data: mockData })

      const result = await getDashboard()

      expect(mockGet).toHaveBeenCalledWith('/admin/dashboard')
      expect(result).toEqual(mockData)
    })
  })

  describe('listUsers', () => {
    it('calls GET /users with params and returns data', async () => {
      const mockData = { users: [], total: 0 }
      mockGet.mockResolvedValue({ data: mockData })

      const result = await listUsers({ page: 1, page_size: 20 })

      expect(mockGet).toHaveBeenCalledWith('/users', { params: { page: 1, page_size: 20 } })
      expect(result).toEqual(mockData)
    })

    it('calls GET /users with search param', async () => {
      const mockData = { users: [{ id: 'u-1', username: 'alice' }], total: 1 }
      mockGet.mockResolvedValue({ data: mockData })

      const result = await listUsers({ page: 1, page_size: 20, search: 'alice' })

      expect(mockGet).toHaveBeenCalledWith('/users', {
        params: { page: 1, page_size: 20, search: 'alice' },
      })
      expect(result).toEqual(mockData)
    })

    it('calls GET /users with no params', async () => {
      mockGet.mockResolvedValue({ data: { users: [], total: 0 } })

      await listUsers()

      expect(mockGet).toHaveBeenCalledWith('/users', { params: undefined })
    })
  })

  describe('createAccount', () => {
    it('calls POST /users/admin/create-account with payload', async () => {
      const payload = {
        username: 'newuser',
        password: 'StrongPass1',
        display_name: 'New User',
        role: 'MEMBER',
      }
      mockPost.mockResolvedValue({ data: { id: 'u-new' } })

      const result = await createAccount(payload)

      expect(mockPost).toHaveBeenCalledWith('/users/admin/create-account', payload)
      expect(result).toEqual({ id: 'u-new' })
    })
  })

  describe('changeRole', () => {
    it('calls PUT /users/{userId}/role with role payload', async () => {
      const updatedUser = {
        id: 'u-1',
        username: 'alice',
        display_name: 'Alice',
        role: 'ADMIN',
        is_banned: false,
        ban_reason: null,
      }
      mockPut.mockResolvedValue({ data: updatedUser })

      const result = await changeRole('u-1', 'ADMIN')

      expect(mockPut).toHaveBeenCalledWith('/users/u-1/role', { role: 'ADMIN' })
      expect(result).toEqual(updatedUser)
    })

    it('returns the updated user object from the response', async () => {
      const updatedUser = {
        id: 'u-2',
        username: 'bob',
        display_name: 'Bob',
        role: 'MEMBER',
        is_banned: false,
        ban_reason: null,
      }
      mockPut.mockResolvedValue({ data: updatedUser })

      const result = await changeRole('u-2', 'MEMBER')

      expect(result).toEqual(updatedUser)
      expect(result.role).toBe('MEMBER')
    })
  })

  describe('banUser', () => {
    it('calls POST /users/{userId}/ban with reason', async () => {
      mockPost.mockResolvedValue({})

      await banUser('u-1', 'Spam')

      expect(mockPost).toHaveBeenCalledWith('/users/u-1/ban', { reason: 'Spam' })
    })
  })

  describe('unbanUser', () => {
    it('calls POST /users/{userId}/unban', async () => {
      mockPost.mockResolvedValue({})

      await unbanUser('u-1')

      expect(mockPost).toHaveBeenCalledWith('/users/u-1/unban')
    })
  })

  describe('getAuditLogs', () => {
    it('calls GET /users/admin/audit-logs with basic params', async () => {
      const mockData = { logs: [], total: 0 }
      mockGet.mockResolvedValue({ data: mockData })

      const result = await getAuditLogs({ page: 1, page_size: 50 })

      expect(mockGet).toHaveBeenCalledWith('/users/admin/audit-logs', {
        params: { page: 1, page_size: 50 },
      })
      expect(result).toEqual(mockData)
    })

    it('calls GET /users/admin/audit-logs with filter params', async () => {
      const mockData = { logs: [], total: 0 }
      mockGet.mockResolvedValue({ data: mockData })

      const result = await getAuditLogs({
        page: 1,
        page_size: 50,
        user_id: 'uid-123',
        date_from: '2025-01-01',
        date_to: '2025-12-31',
      })

      expect(mockGet).toHaveBeenCalledWith('/users/admin/audit-logs', {
        params: {
          page: 1,
          page_size: 50,
          user_id: 'uid-123',
          date_from: '2025-01-01',
          date_to: '2025-12-31',
        },
      })
      expect(result).toEqual(mockData)
    })

    it('calls GET /users/admin/audit-logs with only date_from', async () => {
      mockGet.mockResolvedValue({ data: { logs: [], total: 0 } })

      await getAuditLogs({ page: 1, page_size: 50, date_from: '2025-06-01' })

      expect(mockGet).toHaveBeenCalledWith('/users/admin/audit-logs', {
        params: { page: 1, page_size: 50, date_from: '2025-06-01' },
      })
    })
  })

  describe('listApplications', () => {
    it('calls GET /admin/applications with params', async () => {
      const mockData = { applications: [], total: 0 }
      mockGet.mockResolvedValue({ data: mockData })

      const result = await listApplications({ status: 'PENDING' })

      expect(mockGet).toHaveBeenCalledWith('/admin/applications', {
        params: { status: 'PENDING' },
      })
      expect(result).toEqual(mockData)
    })
  })

  describe('reviewApplication', () => {
    it('calls PUT /admin/applications/{id}/review with action', async () => {
      mockPut.mockResolvedValue({})

      await reviewApplication('app-1', 'APPROVED')

      expect(mockPut).toHaveBeenCalledWith('/admin/applications/app-1/review', {
        action: 'APPROVED',
      })
    })
  })

  describe('listReports', () => {
    it('calls GET /admin/reports with params', async () => {
      const mockData = { reports: [], total: 0 }
      mockGet.mockResolvedValue({ data: mockData })

      const result = await listReports({ status_filter: 'PENDING', page: 1, page_size: 20 })

      expect(mockGet).toHaveBeenCalledWith('/admin/reports', {
        params: { status_filter: 'PENDING', page: 1, page_size: 20 },
      })
      expect(result).toEqual(mockData)
    })
  })

  describe('reviewReport', () => {
    it('calls PUT /admin/reports/{id}/review with status', async () => {
      mockPut.mockResolvedValue({})

      await reviewReport('rpt-1', 'RESOLVED')

      expect(mockPut).toHaveBeenCalledWith('/admin/reports/rpt-1/review', { status: 'RESOLVED' })
    })
  })

  describe('listInviteCodes', () => {
    it('calls GET /admin/invite-codes with status param', async () => {
      const mockData = { codes: [], total: 0 }
      mockGet.mockResolvedValue({ data: mockData })

      const result = await listInviteCodes({ status: 'active' })

      expect(mockGet).toHaveBeenCalledWith('/admin/invite-codes', {
        params: { status: 'active' },
      })
      expect(result).toEqual(mockData)
    })

    it('converts page/page_size to offset/limit', async () => {
      const mockData = { codes: [], total: 0 }
      mockGet.mockResolvedValue({ data: mockData })

      await listInviteCodes({ status: 'active', page: 3, page_size: 50 })

      expect(mockGet).toHaveBeenCalledWith('/admin/invite-codes', {
        params: { status: 'active', offset: 100, limit: 50 },
      })
    })
  })

  describe('createInviteCode', () => {
    it('calls POST /auth/invite-code and returns invite code', async () => {
      const mockData = { invite_code: 'ABC123' }
      mockPost.mockResolvedValue({ data: mockData })

      const result = await createInviteCode()

      expect(mockPost).toHaveBeenCalledWith('/auth/invite-code')
      expect(result).toEqual({ invite_code: 'ABC123' })
    })
  })

  describe('revokeInviteCode', () => {
    it('calls PATCH /admin/invite-codes/{id}/revoke', async () => {
      const mockData = { message: 'Invite code revoked.' }
      mockPatch.mockResolvedValue({ data: mockData })

      const result = await revokeInviteCode('code-123')

      expect(mockPatch).toHaveBeenCalledWith('/admin/invite-codes/code-123/revoke')
      expect(result).toEqual({ message: 'Invite code revoked.' })
    })
  })

  describe('deleteInviteCode', () => {
    it('calls DELETE /admin/invite-codes/{id}', async () => {
      mockDelete.mockResolvedValue({ status: 204 })

      await deleteInviteCode('code-456')

      expect(mockDelete).toHaveBeenCalledWith('/admin/invite-codes/code-456')
    })
  })
})

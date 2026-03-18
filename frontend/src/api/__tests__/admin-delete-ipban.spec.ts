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

import { deleteUser, listIpBans, createIpBan, deleteIpBan } from '../admin'

describe('deleteUser', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('calls DELETE /users/:id with reason', async () => {
    mockDelete.mockResolvedValue({ data: {} })

    await deleteUser('user-123', 'spam account')

    expect(mockDelete).toHaveBeenCalledWith('/users/user-123', { data: { reason: 'spam account' } })
  })

  it('calls DELETE /users/:id with empty reason by default', async () => {
    mockDelete.mockResolvedValue({ data: {} })

    await deleteUser('user-456')

    expect(mockDelete).toHaveBeenCalledWith('/users/user-456', { data: { reason: '' } })
  })

  it('includes user ID in URL path', async () => {
    mockDelete.mockResolvedValue({ data: {} })

    await deleteUser('abc-def-ghi', 'test')

    expect(mockDelete).toHaveBeenCalledWith('/users/abc-def-ghi', expect.any(Object))
  })

  it('propagates errors from the API call', async () => {
    mockDelete.mockRejectedValue(new Error('Forbidden'))

    await expect(deleteUser('user-1', 'reason')).rejects.toThrow('Forbidden')
  })
})

describe('listIpBans', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('calls GET /admin/ip-bans with params and returns data', async () => {
    const mockData = { bans: [], total: 0 }
    mockGet.mockResolvedValue({ data: mockData })

    const result = await listIpBans({ page: 1, page_size: 10 })

    expect(mockGet).toHaveBeenCalledWith('/admin/ip-bans', { params: { page: 1, page_size: 10 } })
    expect(result).toEqual(mockData)
  })

  it('calls GET /admin/ip-bans with no params', async () => {
    mockGet.mockResolvedValue({ data: { bans: [], total: 0 } })

    await listIpBans()

    expect(mockGet).toHaveBeenCalledWith('/admin/ip-bans', { params: undefined })
  })

  it('returns typed response with bans array and total', async () => {
    const ban = {
      id: 'ban-1',
      ip_address: '192.168.1.100',
      reason: 'DDoS',
      banned_by: 'admin-1',
      expires_at: '2026-12-31T00:00:00Z',
      created_at: '2026-01-01T00:00:00Z',
    }
    mockGet.mockResolvedValue({ data: { bans: [ban], total: 1 } })

    const result = await listIpBans({ page: 1, page_size: 20 })

    expect(result.bans).toHaveLength(1)
    expect(result.bans[0].ip_address).toBe('192.168.1.100')
    expect(result.total).toBe(1)
  })

  it('passes custom page and page_size params', async () => {
    mockGet.mockResolvedValue({ data: { bans: [], total: 0 } })

    await listIpBans({ page: 3, page_size: 50 })

    expect(mockGet).toHaveBeenCalledWith('/admin/ip-bans', {
      params: { page: 3, page_size: 50 },
    })
  })
})

describe('createIpBan', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('calls POST /admin/ip-bans with ip_address and reason', async () => {
    const banData = {
      id: 'ban-1',
      ip_address: '1.2.3.4',
      reason: 'spam',
      banned_by: null,
      expires_at: null,
      created_at: '2026-01-01T00:00:00Z',
    }
    mockPost.mockResolvedValue({ data: banData })

    const result = await createIpBan({ ip_address: '1.2.3.4', reason: 'spam' })

    expect(mockPost).toHaveBeenCalledWith('/admin/ip-bans', {
      ip_address: '1.2.3.4',
      reason: 'spam',
    })
    expect(result).toEqual(banData)
  })

  it('calls POST /admin/ip-bans with ip_address only', async () => {
    mockPost.mockResolvedValue({
      data: {
        id: 'ban-2',
        ip_address: '10.0.0.1',
        reason: '',
        banned_by: null,
        expires_at: null,
        created_at: '2026-01-01T00:00:00Z',
      },
    })

    await createIpBan({ ip_address: '10.0.0.1' })

    expect(mockPost).toHaveBeenCalledWith('/admin/ip-bans', { ip_address: '10.0.0.1' })
  })

  it('includes expires_at when provided', async () => {
    mockPost.mockResolvedValue({
      data: {
        id: 'ban-3',
        ip_address: '5.5.5.5',
        reason: 'temp ban',
        banned_by: null,
        expires_at: '2026-06-01T00:00:00Z',
        created_at: '2026-01-01T00:00:00Z',
      },
    })

    await createIpBan({
      ip_address: '5.5.5.5',
      reason: 'temp ban',
      expires_at: '2026-06-01T00:00:00Z',
    })

    expect(mockPost).toHaveBeenCalledWith('/admin/ip-bans', {
      ip_address: '5.5.5.5',
      reason: 'temp ban',
      expires_at: '2026-06-01T00:00:00Z',
    })
  })

  it('returns a typed IpBan object', async () => {
    const ban = {
      id: 'ban-4',
      ip_address: '8.8.8.8',
      reason: 'test',
      banned_by: 'admin-1',
      expires_at: null,
      created_at: '2026-03-18T00:00:00Z',
    }
    mockPost.mockResolvedValue({ data: ban })

    const result = await createIpBan({ ip_address: '8.8.8.8', reason: 'test' })

    expect(result.id).toBe('ban-4')
    expect(result.ip_address).toBe('8.8.8.8')
    expect(result.banned_by).toBe('admin-1')
  })

  it('propagates errors from the API call', async () => {
    mockPost.mockRejectedValue(new Error('Invalid IP'))

    await expect(createIpBan({ ip_address: 'not-an-ip' })).rejects.toThrow('Invalid IP')
  })
})

describe('deleteIpBan', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('calls DELETE /admin/ip-bans/:id', async () => {
    mockDelete.mockResolvedValue({ data: {} })

    await deleteIpBan('ban-123')

    expect(mockDelete).toHaveBeenCalledWith('/admin/ip-bans/ban-123')
  })

  it('includes ban ID in URL path', async () => {
    mockDelete.mockResolvedValue({ data: {} })

    await deleteIpBan('abc-def')

    expect(mockDelete).toHaveBeenCalledWith('/admin/ip-bans/abc-def')
  })

  it('propagates errors from the API call', async () => {
    mockDelete.mockRejectedValue(new Error('Not found'))

    await expect(deleteIpBan('nonexistent')).rejects.toThrow('Not found')
  })
})

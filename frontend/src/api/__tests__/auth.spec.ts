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

import { getCaptcha, login, guestLogin, register, logout, heartbeat } from '../auth'

describe('auth API', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('getCaptcha', () => {
    it('calls GET /auth/captcha and returns data', async () => {
      const mockData = { captcha_id: 'cap-1', image_base64: 'base64data' }
      mockGet.mockResolvedValue({ data: mockData })

      const result = await getCaptcha()

      expect(mockGet).toHaveBeenCalledWith('/auth/captcha')
      expect(result).toEqual(mockData)
    })

    it('calls GET /auth/captcha exactly once', async () => {
      mockGet.mockResolvedValue({ data: { captcha_id: 'x', image_base64: 'y' } })

      await getCaptcha()

      expect(mockGet).toHaveBeenCalledTimes(1)
    })
  })

  describe('login', () => {
    it('calls POST /auth/login with full credentials payload', async () => {
      const payload = {
        username: 'alice',
        password: 'Pass1!',
        captcha_id: 'c1',
        captcha_code: 'ABC',
      }
      const mockData = { role: 'MEMBER', expires_in: 3600 }
      mockPost.mockResolvedValue({ data: mockData })

      const result = await login(payload)

      expect(mockPost).toHaveBeenCalledWith('/auth/login', payload)
      expect(result).toEqual(mockData)
    })

    it('returns AuthResponse with requires_consent field', async () => {
      const payload = { username: 'bob', password: 'Pass2!', captcha_id: 'c2', captcha_code: 'XYZ' }
      const mockData = { role: 'MEMBER', expires_in: 3600, requires_consent: true }
      mockPost.mockResolvedValue({ data: mockData })

      const result = await login(payload)

      expect(result.requires_consent).toBe(true)
    })

    it('calls POST /auth/login exactly once', async () => {
      mockPost.mockResolvedValue({ data: { role: 'MEMBER', expires_in: 3600 } })

      await login({ username: 'u', password: 'p', captcha_id: 'c', captcha_code: 'cc' })

      expect(mockPost).toHaveBeenCalledTimes(1)
    })
  })

  describe('guestLogin', () => {
    it('calls POST /auth/guest/{inviteCode} with encoded invite code', async () => {
      const inviteCode = 'INVITE-123'
      const payload = { display_name: 'Guest User', captcha_id: 'cid', captcha_code: 'code' }
      const mockData = { role: 'GUEST', expires_in: 1800 }
      mockPost.mockResolvedValue({ data: mockData })

      const result = await guestLogin(inviteCode, payload)

      expect(mockPost).toHaveBeenCalledWith(
        `/auth/guest/${encodeURIComponent(inviteCode)}`,
        payload,
      )
      expect(result).toEqual(mockData)
    })

    it('URL-encodes invite codes with special characters', async () => {
      const inviteCode = 'CODE/WITH SPACES&MORE'
      const payload = { display_name: 'Visitor', captcha_id: 'cid', captcha_code: 'cc' }
      mockPost.mockResolvedValue({ data: { role: 'GUEST', expires_in: 1800 } })

      await guestLogin(inviteCode, payload)

      expect(mockPost).toHaveBeenCalledWith(
        `/auth/guest/${encodeURIComponent(inviteCode)}`,
        payload,
      )
    })

    it('returns AuthResponse from guestLogin', async () => {
      const mockData = { role: 'GUEST', expires_in: 900 }
      mockPost.mockResolvedValue({ data: mockData })

      const result = await guestLogin('CODE', {
        display_name: 'G',
        captcha_id: 'c',
        captcha_code: 'cc',
      })

      expect(result.role).toBe('GUEST')
      expect(result.expires_in).toBe(900)
    })
  })

  describe('register', () => {
    it('calls POST /auth/register with full registration payload', async () => {
      const payload = {
        username: 'newuser',
        password: 'Secure1!',
        display_name: 'New User',
        invite_code: 'INV-ABC',
        captcha_id: 'cid',
        captcha_code: 'code',
      }
      const mockData = { role: 'MEMBER', expires_in: 7200 }
      mockPost.mockResolvedValue({ data: mockData })

      const result = await register(payload)

      expect(mockPost).toHaveBeenCalledWith('/auth/register', payload)
      expect(result).toEqual(mockData)
    })

    it('returns AuthResponse from register', async () => {
      const mockData = { role: 'MEMBER', expires_in: 7200, requires_consent: false }
      mockPost.mockResolvedValue({ data: mockData })

      const result = await register({
        username: 'u',
        password: 'p',
        display_name: 'd',
        invite_code: 'i',
        captcha_id: 'c',
        captcha_code: 'cc',
      })

      expect(result).toEqual(mockData)
    })
  })

  describe('logout', () => {
    it('calls POST /auth/logout', async () => {
      mockPost.mockResolvedValue({})

      await logout()

      expect(mockPost).toHaveBeenCalledWith('/auth/logout')
    })

    it('calls POST /auth/logout exactly once', async () => {
      mockPost.mockResolvedValue({})

      await logout()

      expect(mockPost).toHaveBeenCalledTimes(1)
    })

    it('does not use any other HTTP method', async () => {
      mockPost.mockResolvedValue({})

      await logout()

      expect(mockGet).not.toHaveBeenCalled()
      expect(mockPut).not.toHaveBeenCalled()
      expect(mockDelete).not.toHaveBeenCalled()
    })
  })

  describe('heartbeat', () => {
    it('calls POST /auth/heartbeat', async () => {
      mockPost.mockResolvedValue({})

      await heartbeat()

      expect(mockPost).toHaveBeenCalledWith('/auth/heartbeat')
    })

    it('calls POST /auth/heartbeat exactly once', async () => {
      mockPost.mockResolvedValue({})

      await heartbeat()

      expect(mockPost).toHaveBeenCalledTimes(1)
    })

    it('does not use any other HTTP method', async () => {
      mockPost.mockResolvedValue({})

      await heartbeat()

      expect(mockGet).not.toHaveBeenCalled()
      expect(mockPut).not.toHaveBeenCalled()
      expect(mockDelete).not.toHaveBeenCalled()
    })
  })
})

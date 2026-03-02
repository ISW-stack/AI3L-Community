import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useAuthStore } from '../auth'

// Mock api module
const mockPost = vi.fn()
const mockGet = vi.fn()

vi.mock('@/composables/api', () => ({
  default: {
    post: (...args: unknown[]) => mockPost(...args),
    get: (...args: unknown[]) => mockGet(...args),
  },
}))

vi.mock('@/constants', () => ({
  HEARTBEAT_INTERVAL_MS: 30000,
}))

describe('useAuthStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    vi.useFakeTimers()
    mockPost.mockReset()
    mockGet.mockReset()
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.restoreAllMocks()
  })

  // ---------- setSession ----------

  describe('setSession', () => {
    it('should store role and expiresAt in state and localStorage', () => {
      const auth = useAuthStore()
      auth.setSession('MEMBER', 3600)

      expect(auth.role).toBe('MEMBER')
      expect(auth.isAuthenticated).toBe(true)
      expect(localStorage.getItem('role')).toBe('MEMBER')
      expect(localStorage.getItem('expiresAt')).toBeTruthy()
    })

    it('should compute expiresAt as Date.now() + expiresIn * 1000', () => {
      vi.setSystemTime(new Date('2025-01-01T00:00:00Z'))
      const auth = useAuthStore()
      auth.setSession('MEMBER', 3600)

      const expectedExpiry = new Date('2025-01-01T00:00:00Z').getTime() + 3600 * 1000
      expect(auth.expiresAt).toBe(expectedExpiry)
      expect(localStorage.getItem('expiresAt')).toBe(String(expectedExpiry))
    })

    it('should start heartbeat timer', () => {
      const auth = useAuthStore()
      mockPost.mockResolvedValue({})
      auth.setSession('MEMBER', 3600)

      // Advance past heartbeat interval (30s)
      vi.advanceTimersByTime(30000)
      expect(mockPost).toHaveBeenCalledWith('/auth/heartbeat')
    })
  })

  // ---------- clearSession ----------

  describe('clearSession', () => {
    it('should clear all auth state and localStorage', () => {
      const auth = useAuthStore()
      auth.setSession('ADMIN', 3600)
      auth.clearSession()

      expect(auth.role).toBeNull()
      expect(auth.expiresAt).toBe(0)
      expect(auth.user).toBeNull()
      expect(auth.requiresConsent).toBe(false)
      expect(localStorage.getItem('role')).toBeNull()
      expect(localStorage.getItem('expiresAt')).toBeNull()
    })

    it('should stop the heartbeat timer', () => {
      const auth = useAuthStore()
      mockPost.mockResolvedValue({})
      auth.setSession('MEMBER', 3600)
      auth.clearSession()

      // Reset mock count after clearSession
      mockPost.mockClear()

      // Advance past heartbeat interval; heartbeat should NOT fire
      vi.advanceTimersByTime(60000)
      expect(mockPost).not.toHaveBeenCalledWith('/auth/heartbeat')
    })
  })

  // ---------- computed roles ----------

  describe('computed roles', () => {
    it('isAuthenticated should be true when role is set and not expired', () => {
      const auth = useAuthStore()
      auth.setSession('MEMBER', 3600)
      expect(auth.isAuthenticated).toBe(true)
    })

    it('isAuthenticated should be false when session is expired', () => {
      vi.setSystemTime(new Date('2025-06-01T00:00:00Z'))
      const auth = useAuthStore()
      auth.setSession('MEMBER', 3600)

      // Advance system time past the expiry (1 hour + 1ms)
      vi.setSystemTime(new Date('2025-06-01T01:00:01Z'))
      expect(auth.isAuthenticated).toBe(false)
    })

    it('isAuthenticated should be false when role is null', () => {
      const auth = useAuthStore()
      expect(auth.isAuthenticated).toBe(false)
    })

    it('isAdmin should be true for ADMIN role', () => {
      const auth = useAuthStore()
      auth.setSession('ADMIN', 3600)
      expect(auth.isAdmin).toBe(true)
      expect(auth.isSuperAdmin).toBe(false)
    })

    it('isAdmin should be true for SUPER_ADMIN role', () => {
      const auth = useAuthStore()
      auth.setSession('SUPER_ADMIN', 3600)
      expect(auth.isAdmin).toBe(true)
      expect(auth.isSuperAdmin).toBe(true)
    })

    it('isAdmin should be false for MEMBER role', () => {
      const auth = useAuthStore()
      auth.setSession('MEMBER', 3600)
      expect(auth.isAdmin).toBe(false)
    })

    it('isGuest should be true for GUEST role', () => {
      const auth = useAuthStore()
      auth.setSession('GUEST', 3600)
      expect(auth.isGuest).toBe(true)
      expect(auth.isAdmin).toBe(false)
    })

    it('isGuest should be false for MEMBER role', () => {
      const auth = useAuthStore()
      auth.setSession('MEMBER', 3600)
      expect(auth.isGuest).toBe(false)
    })
  })

  // ---------- login ----------

  describe('login', () => {
    it('should call API, set session, and fetch profile', async () => {
      const auth = useAuthStore()
      mockPost.mockResolvedValueOnce({
        data: { role: 'MEMBER', expires_in: 3600, requires_consent: false },
      })
      mockGet.mockResolvedValueOnce({
        data: { id: '1', username: 'testuser', display_name: 'Test', role: 'MEMBER' },
      })

      await auth.login('testuser', 'password123', 'captcha-id', 'captcha-code')

      expect(mockPost).toHaveBeenCalledWith('/auth/login', {
        username: 'testuser',
        password: 'password123',
        captcha_id: 'captcha-id',
        captcha_code: 'captcha-code',
      })
      expect(auth.role).toBe('MEMBER')
      expect(auth.isAuthenticated).toBe(true)
      expect(auth.requiresConsent).toBe(false)
      // fetchProfile should have been called (for non-guest)
      expect(mockGet).toHaveBeenCalledWith('/users/me')
    })

    it('should set requiresConsent from API response', async () => {
      const auth = useAuthStore()
      mockPost.mockResolvedValueOnce({
        data: { role: 'MEMBER', expires_in: 3600, requires_consent: true },
      })
      mockGet.mockResolvedValueOnce({ data: { id: '1', display_name: 'Test' } })

      await auth.login('user', 'pass', 'cid', 'ccode')
      expect(auth.requiresConsent).toBe(true)
    })
  })

  // ---------- logout ----------

  describe('logout', () => {
    it('should call API and clear session', async () => {
      const auth = useAuthStore()
      auth.setSession('MEMBER', 3600)
      mockPost.mockResolvedValueOnce({})

      await auth.logout()

      expect(mockPost).toHaveBeenCalledWith('/auth/logout')
      expect(auth.role).toBeNull()
      expect(auth.isAuthenticated).toBe(false)
    })

    it('should clear session even if API call fails', async () => {
      const auth = useAuthStore()
      auth.setSession('MEMBER', 3600)
      mockPost.mockRejectedValueOnce(new Error('Network error'))

      await auth.logout()

      expect(auth.role).toBeNull()
      expect(auth.isAuthenticated).toBe(false)
    })
  })

  // ---------- register ----------

  describe('register', () => {
    it('should call API, set session, and fetch profile', async () => {
      const auth = useAuthStore()
      mockPost.mockResolvedValueOnce({
        data: { role: 'MEMBER', expires_in: 7200 },
      })
      mockGet.mockResolvedValueOnce({
        data: { id: '2', username: 'newuser', display_name: 'New User' },
      })

      await auth.register('newuser', 'pass123', 'New User', 'INV-CODE', 'cid', 'ccode')

      expect(mockPost).toHaveBeenCalledWith('/auth/register', {
        username: 'newuser',
        password: 'pass123',
        display_name: 'New User',
        invite_code: 'INV-CODE',
        captcha_id: 'cid',
        captcha_code: 'ccode',
      })
      expect(auth.role).toBe('MEMBER')
      expect(mockGet).toHaveBeenCalledWith('/users/me')
    })
  })

  // ---------- guestLogin ----------

  describe('guestLogin', () => {
    it('should call API and set session without fetching profile', async () => {
      const auth = useAuthStore()
      mockPost.mockResolvedValueOnce({
        data: { role: 'GUEST', expires_in: 1800 },
      })

      await auth.guestLogin('INVITE123', 'Guest User', 'cid', 'ccode')

      expect(mockPost).toHaveBeenCalledWith('/auth/guest/INVITE123', {
        display_name: 'Guest User',
        captcha_id: 'cid',
        captcha_code: 'ccode',
      })
      expect(auth.role).toBe('GUEST')
      expect(auth.isGuest).toBe(true)
      // Guest login does not call fetchProfile
      expect(mockGet).not.toHaveBeenCalled()
    })
  })

  // ---------- fetchProfile ----------

  describe('fetchProfile', () => {
    it('should not fetch profile if user is a guest', async () => {
      const auth = useAuthStore()
      auth.setSession('GUEST', 3600)

      await auth.fetchProfile()
      expect(mockGet).not.toHaveBeenCalled()
    })

    it('should not fetch profile if not authenticated', async () => {
      const auth = useAuthStore()

      await auth.fetchProfile()
      expect(mockGet).not.toHaveBeenCalled()
    })

    it('should fetch and set user profile for non-guest authenticated users', async () => {
      const auth = useAuthStore()
      auth.setSession('MEMBER', 3600)
      const profileData = {
        id: '1',
        username: 'alice',
        display_name: 'Alice',
        role: 'MEMBER',
      }
      mockGet.mockResolvedValueOnce({ data: profileData })

      await auth.fetchProfile()

      expect(mockGet).toHaveBeenCalledWith('/users/me')
      expect(auth.user).toEqual(profileData)
    })

    it('should not throw if profile fetch fails', async () => {
      const auth = useAuthStore()
      auth.setSession('MEMBER', 3600)
      mockGet.mockRejectedValueOnce(new Error('API Error'))

      await expect(auth.fetchProfile()).resolves.toBeUndefined()
      expect(auth.user).toBeNull()
    })
  })

  // ---------- heartbeat ----------

  describe('heartbeat', () => {
    it('should clear session if not authenticated when heartbeat fires', () => {
      vi.setSystemTime(new Date('2025-06-01T00:00:00Z'))
      const auth = useAuthStore()
      // Set a session that expires in 1 second
      auth.setSession('MEMBER', 1)
      mockPost.mockResolvedValue({})

      // Advance system time past expiry so isAuthenticated becomes false
      vi.setSystemTime(new Date('2025-06-01T00:00:32Z'))

      // Advance timers to trigger the heartbeat interval (30s)
      vi.advanceTimersByTime(30000)

      // After heartbeat check, session should be cleared because isAuthenticated is false
      expect(auth.role).toBeNull()
    })
  })
})

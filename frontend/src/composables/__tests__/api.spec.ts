import { describe, it, expect, vi, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import type { AxiosError, InternalAxiosRequestConfig } from 'axios'

// We need to capture interceptor callbacks to test them directly.
// The approach: mock axios.create to return a mock instance whose interceptors
// we can capture and invoke manually.

const mockClearSession = vi.fn()
const mockToastShow = vi.fn()
const mockRouterPush = vi.fn()
let mockIsAuthenticated = true

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({
    clearSession: mockClearSession,
    get isAuthenticated() {
      return mockIsAuthenticated
    },
  }),
}))

vi.mock('@/stores/toast', () => ({
  useToastStore: () => ({
    show: mockToastShow,
  }),
}))

vi.mock('@/router', () => ({
  default: { push: mockRouterPush },
}))

describe('api composable', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    mockClearSession.mockReset()
    mockToastShow.mockReset()
    mockRouterPush.mockReset()
    mockIsAuthenticated = true
    // Reset module cache so api.ts re-runs
    vi.resetModules()
  })

  it('should create axios instance with baseURL /api/v1', async () => {
    const { default: api } = await import('../api')
    expect(api.defaults.baseURL).toBe('/api/v1')
  })

  it('should set withCredentials to true', async () => {
    const { default: api } = await import('../api')
    expect(api.defaults.withCredentials).toBe(true)
  })

  it('should set timeout to 15000', async () => {
    const { default: api } = await import('../api')
    expect(api.defaults.timeout).toBe(15000)
  })

  describe('request interceptor — CSRF token injection', () => {
    it('should add X-CSRF-Token header for POST requests when csrf_token cookie exists', async () => {
      // Set a csrf_token cookie
      Object.defineProperty(document, 'cookie', {
        writable: true,
        value: 'csrf_token=test-csrf-token-123',
      })

      const { default: api } = await import('../api')

      // Access the request interceptor — axios stores them in interceptors.request.handlers
      const requestInterceptors = (
        api.interceptors.request as unknown as {
          handlers: Array<{
            fulfilled: (config: InternalAxiosRequestConfig) => InternalAxiosRequestConfig
          }>
        }
      ).handlers
      const interceptor = requestInterceptors[0].fulfilled

      const config = {
        method: 'post',
        headers: {} as Record<string, string>,
      } as InternalAxiosRequestConfig

      const result = interceptor(config)
      expect(result.headers['X-CSRF-Token']).toBe('test-csrf-token-123')
    })

    it('should NOT add X-CSRF-Token header for GET requests', async () => {
      Object.defineProperty(document, 'cookie', {
        writable: true,
        value: 'csrf_token=test-csrf-token-123',
      })

      const { default: api } = await import('../api')
      const requestInterceptors = (
        api.interceptors.request as unknown as {
          handlers: Array<{
            fulfilled: (config: InternalAxiosRequestConfig) => InternalAxiosRequestConfig
          }>
        }
      ).handlers
      const interceptor = requestInterceptors[0].fulfilled

      const config = {
        method: 'get',
        headers: {} as Record<string, string>,
      } as InternalAxiosRequestConfig

      const result = interceptor(config)
      expect(result.headers['X-CSRF-Token']).toBeUndefined()
    })

    it('should NOT add X-CSRF-Token for HEAD requests', async () => {
      Object.defineProperty(document, 'cookie', {
        writable: true,
        value: 'csrf_token=test-csrf-token-123',
      })

      const { default: api } = await import('../api')
      const requestInterceptors = (
        api.interceptors.request as unknown as {
          handlers: Array<{
            fulfilled: (config: InternalAxiosRequestConfig) => InternalAxiosRequestConfig
          }>
        }
      ).handlers
      const interceptor = requestInterceptors[0].fulfilled

      const config = {
        method: 'head',
        headers: {} as Record<string, string>,
      } as InternalAxiosRequestConfig

      const result = interceptor(config)
      expect(result.headers['X-CSRF-Token']).toBeUndefined()
    })

    it('should add X-CSRF-Token for PUT requests', async () => {
      Object.defineProperty(document, 'cookie', {
        writable: true,
        value: 'csrf_token=my-token',
      })

      const { default: api } = await import('../api')
      const requestInterceptors = (
        api.interceptors.request as unknown as {
          handlers: Array<{
            fulfilled: (config: InternalAxiosRequestConfig) => InternalAxiosRequestConfig
          }>
        }
      ).handlers
      const interceptor = requestInterceptors[0].fulfilled

      const config = {
        method: 'put',
        headers: {} as Record<string, string>,
      } as InternalAxiosRequestConfig

      const result = interceptor(config)
      expect(result.headers['X-CSRF-Token']).toBe('my-token')
    })

    it('should add X-CSRF-Token for DELETE requests', async () => {
      Object.defineProperty(document, 'cookie', {
        writable: true,
        value: 'csrf_token=delete-token',
      })

      const { default: api } = await import('../api')
      const requestInterceptors = (
        api.interceptors.request as unknown as {
          handlers: Array<{
            fulfilled: (config: InternalAxiosRequestConfig) => InternalAxiosRequestConfig
          }>
        }
      ).handlers
      const interceptor = requestInterceptors[0].fulfilled

      const config = {
        method: 'delete',
        headers: {} as Record<string, string>,
      } as InternalAxiosRequestConfig

      const result = interceptor(config)
      expect(result.headers['X-CSRF-Token']).toBe('delete-token')
    })
  })

  describe('response interceptor — error handling', () => {
    async function getErrorInterceptor() {
      const { default: api } = await import('../api')
      const responseInterceptors = (
        api.interceptors.response as unknown as {
          handlers: Array<{ rejected: (error: AxiosError) => Promise<never> }>
        }
      ).handlers
      return responseInterceptors[0].rejected
    }

    function makeAxiosError(status: number, detail?: unknown, headers?: Record<string, string>) {
      return {
        response: {
          status,
          data: { detail },
          headers: headers || {},
        },
      } as unknown as AxiosError
    }

    it('should clear session and redirect on AUTH_001 (token expired)', async () => {
      const errorHandler = await getErrorInterceptor()
      const error = makeAxiosError(401, { code: 'AUTH_001', message: 'Token expired' })

      await expect(errorHandler(error)).rejects.toBe(error)

      expect(mockClearSession).toHaveBeenCalled()
      expect(mockRouterPush).toHaveBeenCalledWith({ name: 'login' })
    })

    it('should show session expired toast on AUTH_001 when user was logged in', async () => {
      mockIsAuthenticated = true
      const errorHandler = await getErrorInterceptor()
      const error = makeAxiosError(401, { code: 'AUTH_001', message: 'Token expired' })

      await expect(errorHandler(error)).rejects.toBe(error)

      expect(mockToastShow).toHaveBeenCalledWith('Session expired. Please log in again.', 'warning')
    })

    it('should NOT show toast on AUTH_001 when user was not logged in', async () => {
      mockIsAuthenticated = false
      const errorHandler = await getErrorInterceptor()
      const error = makeAxiosError(401, { code: 'AUTH_001', message: 'Token expired' })

      await expect(errorHandler(error)).rejects.toBe(error)

      expect(mockClearSession).toHaveBeenCalled()
      expect(mockToastShow).not.toHaveBeenCalled()
    })

    it('should clear session and redirect on AUTH_002 (token revoked)', async () => {
      const errorHandler = await getErrorInterceptor()
      const error = makeAxiosError(401, { code: 'AUTH_002', message: 'Token revoked' })

      await expect(errorHandler(error)).rejects.toBe(error)

      expect(mockClearSession).toHaveBeenCalled()
      expect(mockRouterPush).toHaveBeenCalledWith({ name: 'login' })
    })

    it('should show revoked session toast on AUTH_002 when user was logged in', async () => {
      mockIsAuthenticated = true
      const errorHandler = await getErrorInterceptor()
      const error = makeAxiosError(401, { code: 'AUTH_002', message: 'Token revoked' })

      await expect(errorHandler(error)).rejects.toBe(error)

      expect(mockToastShow).toHaveBeenCalledWith('Invalid or revoked session.', 'warning')
    })

    it('should clear session and redirect on plain 401 (no error code)', async () => {
      const errorHandler = await getErrorInterceptor()
      const error = makeAxiosError(401, 'Unauthorized')

      await expect(errorHandler(error)).rejects.toBe(error)

      expect(mockClearSession).toHaveBeenCalled()
      expect(mockRouterPush).toHaveBeenCalledWith({ name: 'login' })
    })

    it('should show session expired toast on plain 401 when user was logged in', async () => {
      mockIsAuthenticated = true
      const errorHandler = await getErrorInterceptor()
      const error = makeAxiosError(401, 'Unauthorized')

      await expect(errorHandler(error)).rejects.toBe(error)

      expect(mockToastShow).toHaveBeenCalledWith('Session expired. Please log in again.', 'warning')
    })

    it('should clear session, show toast, and redirect on AUTH_004 (banned)', async () => {
      const errorHandler = await getErrorInterceptor()
      const error = makeAxiosError(403, { code: 'AUTH_004', message: 'You have been banned.' })

      await expect(errorHandler(error)).rejects.toBe(error)

      expect(mockClearSession).toHaveBeenCalled()
      expect(mockToastShow).toHaveBeenCalledWith('Your account has been banned.', 'error')
      expect(mockRouterPush).toHaveBeenCalledWith({ name: 'login' })
    })

    it('should show default banned message if AUTH_004 has no message', async () => {
      const errorHandler = await getErrorInterceptor()
      const error = makeAxiosError(403, { code: 'AUTH_004' })

      await expect(errorHandler(error)).rejects.toBe(error)

      expect(mockToastShow).toHaveBeenCalledWith('Your account has been banned.', 'error')
    })

    it('should show warning toast on AUTH_003 (guest capacity)', async () => {
      const errorHandler = await getErrorInterceptor()
      const error = makeAxiosError(403, { code: 'AUTH_003', message: 'Guest slots full' })

      await expect(errorHandler(error)).rejects.toBe(error)

      expect(mockToastShow).toHaveBeenCalledWith(
        'Guest capacity reached. Please try again later.',
        'warning',
      )
      // Should NOT clear session or redirect
      expect(mockClearSession).not.toHaveBeenCalled()
      expect(mockRouterPush).not.toHaveBeenCalled()
    })

    it('should show rate limit toast with retry-after on 429', async () => {
      const errorHandler = await getErrorInterceptor()
      const error = makeAxiosError(
        429,
        { code: 'RATE_LIMIT', message: 'Too fast' },
        { 'retry-after': '30' },
      )

      await expect(errorHandler(error)).rejects.toBe(error)

      expect(mockToastShow).toHaveBeenCalledWith(
        'Too many requests. Please retry after 30 seconds.',
        'warning',
      )
    })

    it('should show generic rate limit toast when no retry-after header', async () => {
      const errorHandler = await getErrorInterceptor()
      const error = makeAxiosError(429, { code: 'RATE_LIMIT', message: 'Rate limited' })

      await expect(errorHandler(error)).rejects.toBe(error)

      expect(mockToastShow).toHaveBeenCalledWith(
        'Too many requests. Please try again later.',
        'warning',
      )
    })

    it('should show toast for generic structured error codes', async () => {
      const errorHandler = await getErrorInterceptor()
      const error = makeAxiosError(400, { code: 'VALIDATION_001', message: 'Invalid input' })

      await expect(errorHandler(error)).rejects.toBe(error)

      expect(mockToastShow).toHaveBeenCalledWith('Invalid input', 'error')
    })

    it('should not show toast when no code or message in error response', async () => {
      const errorHandler = await getErrorInterceptor()
      const error = makeAxiosError(500, 'Internal Server Error')

      await expect(errorHandler(error)).rejects.toBe(error)

      expect(mockToastShow).not.toHaveBeenCalled()
    })
  })
})

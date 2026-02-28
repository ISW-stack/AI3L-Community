import axios from 'axios'
import { useAuthStore } from '@/stores/auth'
import router from '@/router'

const api = axios.create({
  baseURL: '/api/v1',
  timeout: 15000,
  headers: { 'Content-Type': 'application/json' },
})

// Request: inject Authorization header
api.interceptors.request.use((config) => {
  const auth = useAuthStore()
  if (auth.token) {
    config.headers.Authorization = `Bearer ${auth.token}`
  }
  return config
})

// Response: handle structured error codes, 401, 429
api.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error.response?.status
    const detail = error.response?.data?.detail
    const code: string | undefined = typeof detail === 'object' ? detail?.code : undefined
    const message: string =
      typeof detail === 'object' ? detail?.message : typeof detail === 'string' ? detail : ''

    // AUTH_004 — account banned
    if (code === 'AUTH_004') {
      const auth = useAuthStore()
      auth.clearSession()
      window.dispatchEvent(
        new CustomEvent('app:toast', {
          detail: { message: message || 'Your account has been banned.', type: 'error' },
        }),
      )
      router.push({ name: 'login' })
      return Promise.reject(error)
    }

    // AUTH_001 / AUTH_002 — token expired or revoked
    if (code === 'AUTH_001' || code === 'AUTH_002' || (status === 401 && !code)) {
      const auth = useAuthStore()
      auth.clearSession()
      router.push({ name: 'login' })
      return Promise.reject(error)
    }

    // AUTH_003 — guest capacity reached
    if (code === 'AUTH_003') {
      window.dispatchEvent(
        new CustomEvent('app:toast', {
          detail: { message: message || 'Guest capacity reached. Please try again later.', type: 'warning' },
        }),
      )
      return Promise.reject(error)
    }

    // 429 — rate limit
    if (status === 429) {
      const retryAfter = error.response.headers['retry-after']
      const msg = retryAfter
        ? `Too many requests. Please retry after ${retryAfter} seconds.`
        : message || 'Too many requests. Please try again later.'
      window.dispatchEvent(new CustomEvent('app:toast', { detail: { message: msg, type: 'warning' } }))
      return Promise.reject(error)
    }

    // Generic structured error — dispatch toast with message if available
    if (code && message) {
      window.dispatchEvent(
        new CustomEvent('app:toast', {
          detail: { message, type: 'error' },
        }),
      )
    }

    return Promise.reject(error)
  },
)

export default api

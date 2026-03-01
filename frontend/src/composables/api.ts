import axios from 'axios'
import { useAuthStore } from '@/stores/auth'
import { useToastStore } from '@/stores/toast'
import router from '@/router'

function getCookie(name: string): string | null {
  const match = document.cookie.match(new RegExp('(^| )' + name + '=([^;]+)'))
  return match ? decodeURIComponent(match[2]) : null
}

const api = axios.create({
  baseURL: '/api/v1',
  timeout: 15000,
  headers: { 'Content-Type': 'application/json' },
  withCredentials: true,
})

// Request: inject CSRF token header (read from csrf_token cookie)
api.interceptors.request.use((config) => {
  const csrfToken = getCookie('csrf_token')
  if (
    csrfToken &&
    config.method &&
    !['get', 'head', 'options'].includes(config.method.toLowerCase())
  ) {
    config.headers['X-CSRF-Token'] = csrfToken
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
      useToastStore().show(message || 'Your account has been banned.', 'error')
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
      useToastStore().show(message || 'Guest capacity reached. Please try again later.', 'warning')
      return Promise.reject(error)
    }

    // 429 — rate limit
    if (status === 429) {
      const retryAfter = error.response.headers['retry-after']
      const msg = retryAfter
        ? `Too many requests. Please retry after ${retryAfter} seconds.`
        : message || 'Too many requests. Please try again later.'
      useToastStore().show(msg, 'warning')
      return Promise.reject(error)
    }

    // Generic structured error — show toast with message if available
    if (code && message) {
      useToastStore().show(message, 'error')
    }

    return Promise.reject(error)
  },
)

export default api

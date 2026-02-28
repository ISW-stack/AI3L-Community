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

// Response: handle 401 and 429
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      const auth = useAuthStore()
      auth.clearSession()
      router.push({ name: 'login' })
    }

    if (error.response?.status === 429) {
      const retryAfter = error.response.headers['retry-after']
      const msg = retryAfter
        ? `Too many requests. Please retry after ${retryAfter} seconds.`
        : 'Too many requests. Please try again later.'
      // Dispatch a custom event for toast notification
      window.dispatchEvent(new CustomEvent('app:toast', { detail: { message: msg, type: 'warning' } }))
    }

    return Promise.reject(error)
  },
)

export default api

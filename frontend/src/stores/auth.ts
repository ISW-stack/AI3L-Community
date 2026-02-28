import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import api from '@/composables/api'

interface UserProfile {
  id: string
  username: string
  display_name: string
  role: string
  avatar_url: string | null
  orcid: string | null
  affiliation: string | null
  bio: string | null
}

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(localStorage.getItem('token'))
  const role = ref<string | null>(localStorage.getItem('role'))
  const expiresAt = ref<number>(Number(localStorage.getItem('expiresAt') || '0'))
  const user = ref<UserProfile | null>(null)

  let heartbeatTimer: ReturnType<typeof setInterval> | null = null

  const isAuthenticated = computed(() => !!token.value && Date.now() < expiresAt.value)
  const isAdmin = computed(() => role.value === 'SUPER_ADMIN' || role.value === 'ADMIN')
  const isSuperAdmin = computed(() => role.value === 'SUPER_ADMIN')
  const isGuest = computed(() => role.value === 'GUEST')

  function setSession(newToken: string, newRole: string, expiresIn: number) {
    token.value = newToken
    role.value = newRole
    expiresAt.value = Date.now() + expiresIn * 1000

    localStorage.setItem('token', newToken)
    localStorage.setItem('role', newRole)
    localStorage.setItem('expiresAt', String(expiresAt.value))

    startHeartbeat()
  }

  function clearSession() {
    token.value = null
    role.value = null
    expiresAt.value = 0
    user.value = null

    localStorage.removeItem('token')
    localStorage.removeItem('role')
    localStorage.removeItem('expiresAt')

    stopHeartbeat()
  }

  async function login(username: string, password: string, captchaId: string, captchaCode: string) {
    const { data } = await api.post('/auth/login', {
      username,
      password,
      captcha_id: captchaId,
      captcha_code: captchaCode,
    })
    setSession(data.token, data.role, data.expires_in)
    await fetchProfile()
  }

  async function guestLogin(inviteCode: string, displayName: string, captchaId: string, captchaCode: string) {
    const { data } = await api.post(`/auth/guest/${encodeURIComponent(inviteCode)}`, {
      display_name: displayName,
      captcha_id: captchaId,
      captcha_code: captchaCode,
    })
    setSession(data.token, data.role, data.expires_in)
  }

  async function register(username: string, password: string, displayName: string, captchaId: string, captchaCode: string) {
    const { data } = await api.post('/auth/register', {
      username,
      password,
      display_name: displayName,
      captcha_id: captchaId,
      captcha_code: captchaCode,
    })
    setSession(data.token, data.role, data.expires_in)
    await fetchProfile()
  }

  async function logout() {
    try {
      await api.post('/auth/logout')
    } catch {
      // Ignore errors on logout
    }
    clearSession()
  }

  async function fetchProfile() {
    if (!token.value || role.value === 'GUEST') return
    try {
      const { data } = await api.get('/users/me')
      user.value = data
    } catch {
      // Profile fetch failed
    }
  }

  function startHeartbeat() {
    stopHeartbeat()
    heartbeatTimer = setInterval(async () => {
      if (!isAuthenticated.value) {
        clearSession()
        return
      }
      try {
        await api.post('/auth/heartbeat')
      } catch {
        // Heartbeat failed — session may be expired
      }
    }, 30_000) // 30 seconds
  }

  function stopHeartbeat() {
    if (heartbeatTimer) {
      clearInterval(heartbeatTimer)
      heartbeatTimer = null
    }
  }

  // Auto-start heartbeat if already authenticated
  if (isAuthenticated.value) {
    startHeartbeat()
    fetchProfile()
  }

  return {
    token,
    role,
    expiresAt,
    user,
    isAuthenticated,
    isAdmin,
    isSuperAdmin,
    isGuest,
    setSession,
    clearSession,
    login,
    guestLogin,
    register,
    logout,
    fetchProfile,
  }
})

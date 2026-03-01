import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import api from '@/composables/api'
import { HEARTBEAT_INTERVAL_MS } from '@/constants'
import type { UserProfile } from '@/types/user'

export const useAuthStore = defineStore('auth', () => {
  // Role is non-sensitive — kept in localStorage for UI state across page reloads
  const role = ref<string | null>(localStorage.getItem('role'))
  const expiresAt = ref<number>(Number(localStorage.getItem('expiresAt') || '0'))
  const user = ref<UserProfile | null>(null)
  const requiresConsent = ref<boolean>(false)

  let heartbeatTimer: ReturnType<typeof setInterval> | null = null

  // Token is now in HttpOnly cookie — we infer auth state from role + expiresAt
  const isAuthenticated = computed(() => !!role.value && Date.now() < expiresAt.value)
  const isAdmin = computed(() => role.value === 'SUPER_ADMIN' || role.value === 'ADMIN')
  const isSuperAdmin = computed(() => role.value === 'SUPER_ADMIN')
  const isGuest = computed(() => role.value === 'GUEST')

  function setSession(newRole: string, expiresIn: number) {
    role.value = newRole
    expiresAt.value = Date.now() + expiresIn * 1000

    localStorage.setItem('role', newRole)
    localStorage.setItem('expiresAt', String(expiresAt.value))

    startHeartbeat()
  }

  function clearSession() {
    role.value = null
    expiresAt.value = 0
    user.value = null
    requiresConsent.value = false

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
    setSession(data.role, data.expires_in)
    requiresConsent.value = data.requires_consent ?? false
    await fetchProfile()
  }

  async function guestLogin(
    inviteCode: string,
    displayName: string,
    captchaId: string,
    captchaCode: string,
  ) {
    const { data } = await api.post(`/auth/guest/${encodeURIComponent(inviteCode)}`, {
      display_name: displayName,
      captcha_id: captchaId,
      captcha_code: captchaCode,
    })
    setSession(data.role, data.expires_in)
    requiresConsent.value = data.requires_consent ?? false
  }

  async function register(
    username: string,
    password: string,
    displayName: string,
    inviteCode: string,
    captchaId: string,
    captchaCode: string,
  ) {
    const { data } = await api.post('/auth/register', {
      username,
      password,
      display_name: displayName,
      invite_code: inviteCode,
      captcha_id: captchaId,
      captcha_code: captchaCode,
    })
    setSession(data.role, data.expires_in)
    requiresConsent.value = data.requires_consent ?? false
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
    if (!isAuthenticated.value || role.value === 'GUEST') return
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
    }, HEARTBEAT_INTERVAL_MS)
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
    role,
    expiresAt,
    user,
    requiresConsent,
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

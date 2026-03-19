import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import {
  login as apiLogin,
  guestLogin as apiGuestLogin,
  register as apiRegister,
  logout as apiLogout,
  heartbeat as apiHeartbeat,
} from '@/api/auth'
import { getProfile } from '@/api/users'
import { HEARTBEAT_INTERVAL_MS } from '@/constants'
import type { UserProfile } from '@/types/user'
import { useNotificationStore } from '@/stores/notifications'
import { useToastStore } from '@/stores/toast'
import { useDMStore } from '@/stores/dm'
import router from '@/router'
import { i18n } from '@/locales'

export const useAuthStore = defineStore('auth', () => {
  // Role is non-sensitive — kept in localStorage for UI state across page reloads
  const role = ref<string | null>(localStorage.getItem('role'))
  const expiresAt = ref<number>(Number(localStorage.getItem('expiresAt') || '0'))
  const user = ref<UserProfile | null>(null)
  const requiresConsent = ref<boolean>(false)
  const pendingSigRoleChange = ref<{ sigId: string; newRole: string } | null>(null)

  let heartbeatTimer: ReturnType<typeof setInterval> | null = null
  let heartbeatFailures = 0
  const MAX_HEARTBEAT_FAILURES = 3

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

  function setSigRoleChange(sigId: string, newRole: string) {
    pendingSigRoleChange.value = { sigId, newRole }
  }

  function clearSigRoleChange() {
    pendingSigRoleChange.value = null
  }

  function clearSession() {
    role.value = null
    expiresAt.value = 0
    user.value = null
    requiresConsent.value = false
    pendingSigRoleChange.value = null

    localStorage.removeItem('role')
    localStorage.removeItem('expiresAt')

    stopHeartbeat()

    // Reset other stores so stale data from the previous session is cleared.
    // Use lazy calls inside clearSession to avoid circular dependency at module level.
    const notifStore = useNotificationStore()
    const toastStore = useToastStore()
    const dmStore = useDMStore()
    notifStore.resetState()
    toastStore.clearAll()
    dmStore.resetState()
  }

  async function login(username: string, password: string, captchaId: string, captchaCode: string) {
    const data = await apiLogin({
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
    const data = await apiGuestLogin(inviteCode, {
      display_name: displayName,
      captcha_id: captchaId,
      captcha_code: captchaCode,
    })
    setSession(data.role, data.expires_in)
    requiresConsent.value = data.requires_consent ?? false
    await fetchProfile()
  }

  async function register(
    username: string,
    password: string,
    displayName: string,
    inviteCode: string,
    captchaId: string,
    captchaCode: string,
  ) {
    const data = await apiRegister({
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
      await apiLogout()
    } catch {
      // Ignore errors on logout
    }
    clearSession()
  }

  async function fetchProfile() {
    if (!isAuthenticated.value || role.value === 'GUEST') return
    try {
      const data = await getProfile()
      user.value = data
      // Sync role from server — handles demotion and localStorage tampering
      if (data.role && data.role !== role.value) {
        role.value = data.role
        localStorage.setItem('role', data.role)
      }
      // Sync locale preference from DB (uses global i18n instance — safe outside setup)
      if (data.preferred_language) {
        const { syncLocaleFromProfile } = await import('@/composables/useLocale')
        syncLocaleFromProfile(data.preferred_language)
      }
    } catch {
      // 401/403 is already handled by the axios interceptor (clears session)
    }
  }

  function startHeartbeat() {
    stopHeartbeat()
    heartbeatFailures = 0
    heartbeatTimer = setInterval(async () => {
      if (!isAuthenticated.value) {
        clearSession()
        return
      }
      try {
        await apiHeartbeat()
        heartbeatFailures = 0
      } catch {
        // 401/AUTH errors already handled by axios interceptor (clears session).
        // For network errors and 5xx, clear session after consecutive failures.
        heartbeatFailures++
        if (heartbeatFailures >= MAX_HEARTBEAT_FAILURES) {
          const toast = useToastStore()
          toast.showKey('errors.sessionExpired', 'warning')
          clearSession()
          router.push({ name: 'login' })
        }
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
    fetchProfile().catch(() => {})
  }

  return {
    role,
    expiresAt,
    user,
    requiresConsent,
    pendingSigRoleChange,
    isAuthenticated,
    isAdmin,
    isSuperAdmin,
    isGuest,
    setSession,
    clearSession,
    setSigRoleChange,
    clearSigRoleChange,
    login,
    guestLogin,
    register,
    logout,
    fetchProfile,
  }
})

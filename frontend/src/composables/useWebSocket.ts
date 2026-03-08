import { ref, onUnmounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useNotificationStore } from '@/stores/notifications'
import { useToastStore } from '@/stores/toast'
import { useRouter } from 'vue-router'
import api from '@/composables/api'

import { WS_INITIAL_BACKOFF_MS, WS_MAX_BACKOFF_MS } from '@/constants'

// Module-level guard: prevents registering the visibilitychange listener more
// than once when useWebSocket() is called from multiple component instances.
let _visibilityListenerRegistered = false

export function useWebSocket() {
  const auth = useAuthStore()
  const notificationStore = useNotificationStore()
  const toastStore = useToastStore()
  const router = useRouter()

  let ws: WebSocket | null = null
  let backoff = WS_INITIAL_BACKOFF_MS
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null
  const connected = ref(false)

  async function getWsUrl(): Promise<string | null> {
    try {
      // Request a one-time ticket from the server
      const { data } = await api.post('/auth/ws-ticket')
      const protocol = location.protocol === 'https:' ? 'wss' : 'ws'
      return `${protocol}://${location.host}/api/v1/ws?ticket=${encodeURIComponent(data.ticket)}`
    } catch {
      return null
    }
  }

  async function connect() {
    if (!auth.isAuthenticated) return
    cleanup()

    const url = await getWsUrl()
    if (!url) {
      scheduleReconnect()
      return
    }

    ws = new WebSocket(url)

    ws.onopen = () => {
      connected.value = true
      backoff = WS_INITIAL_BACKOFF_MS
    }

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data)
        if (msg.type === 'PING') {
          ws?.send(JSON.stringify({ type: 'PONG' }))
        } else if (msg.type === 'FORCE_LOGOUT') {
          auth.clearSession()
          router.push({ name: 'login' })
        } else if (msg.type === 'NEW_NOTIFICATION') {
          notificationStore.addFromWebSocket(msg.notification)
          toastStore.show(msg.notification?.message || 'New notification', 'info')
        }
      } catch {
        // ignore parse errors
      }
    }

    ws.onclose = () => {
      connected.value = false
      scheduleReconnect()
    }

    ws.onerror = () => {
      ws?.close()
    }
  }

  function scheduleReconnect() {
    if (!auth.isAuthenticated) return
    if (document.hidden) return

    reconnectTimer = setTimeout(() => {
      connect()
    }, backoff)

    backoff = Math.min(backoff * 2, WS_MAX_BACKOFF_MS)
  }

  function cleanup() {
    if (reconnectTimer) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
    if (ws) {
      ws.onclose = null
      ws.onerror = null
      ws.onmessage = null
      ws.close()
      ws = null
    }
    connected.value = false
  }

  function handleVisibility() {
    if (document.hidden) {
      cleanup()
    } else if (auth.isAuthenticated) {
      backoff = WS_INITIAL_BACKOFF_MS
      connect()
    }
  }

  if (!_visibilityListenerRegistered) {
    document.addEventListener('visibilitychange', handleVisibility)
    _visibilityListenerRegistered = true
  }

  onUnmounted(() => {
    document.removeEventListener('visibilitychange', handleVisibility)
    _visibilityListenerRegistered = false
    cleanup()
  })

  return { connected, connect, cleanup }
}

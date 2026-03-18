import { ref, onUnmounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useDMStore } from '@/stores/dm'
import { useNotificationStore } from '@/stores/notifications'
import { useToastStore } from '@/stores/toast'
import { useRouter } from 'vue-router'
import api from '@/composables/api'

import { WS_INITIAL_BACKOFF_MS, WS_MAX_BACKOFF_MS } from '@/constants'

// Reference-counting guard: tracks how many component instances are using
// the shared visibilitychange listener. The listener is only removed when
// the last consumer unmounts.
let _visibilityConsumers = 0
let _currentHandleVisibility: (() => void) | null = null

/** Reset module-level state (test-only). */
export function _resetVisibilityState(): void {
  if (_currentHandleVisibility) {
    document.removeEventListener('visibilitychange', _currentHandleVisibility)
    _currentHandleVisibility = null
  }
  _visibilityConsumers = 0
}

export function useWebSocket() {
  const auth = useAuthStore()
  const dmStore = useDMStore()
  const notificationStore = useNotificationStore()
  const toastStore = useToastStore()
  const router = useRouter()

  let ws: WebSocket | null = null
  let backoff = WS_INITIAL_BACKOFF_MS
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null
  let connecting = false
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
    if (connecting) return // Already connecting, skip duplicate call
    connecting = true
    try {
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
            return
          }
          // Guard: don't process non-PING messages after auth is cleared
          if (!auth.isAuthenticated) return

          if (msg.type === 'FORCE_LOGOUT') {
            auth.clearSession()
            router.push({ name: 'login' })
          } else if (msg.type === 'NEW_NOTIFICATION') {
            if (msg.notification) {
              notificationStore.addFromWebSocket(msg.notification)
            }
            toastStore.show(msg.notification?.message || 'New notification', 'info')
          } else if (msg.type === 'NEW_DM') {
            dmStore.addFromWebSocket(msg.message)
            if (dmStore.activeConversationId !== msg.message.conversation_id) {
              toastStore.show(
                `New message from ${msg.message.sender.display_name}`,
                'info',
              )
            }
          } else if (msg.type === 'DM_EDITED') {
            dmStore.updateFromWebSocket(msg.message)
          } else if (msg.type === 'DM_RECALLED') {
            dmStore.recallFromWebSocket(msg.message_id, msg.conversation_id)
          } else if (msg.type === 'DM_READ') {
            dmStore.readReceiptFromWebSocket(msg.conversation_id, msg.read_at)
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
    } finally {
      connecting = false
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

  _visibilityConsumers++
  if (_visibilityConsumers === 1) {
    _currentHandleVisibility = handleVisibility
    document.addEventListener('visibilitychange', _currentHandleVisibility)
  }

  onUnmounted(() => {
    try {
      _visibilityConsumers = Math.max(0, _visibilityConsumers - 1)
      if (_visibilityConsumers === 0 && _currentHandleVisibility) {
        document.removeEventListener('visibilitychange', _currentHandleVisibility)
        _currentHandleVisibility = null
      }
      cleanup()
    } catch {
      // Ensure cleanup runs even if listener removal fails
      cleanup()
    }
  })

  return { connected, connect, cleanup }
}

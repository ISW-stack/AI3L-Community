import { ref, onUnmounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useDMStore } from '@/stores/dm'
import { useNotificationStore } from '@/stores/notifications'
import { useToastStore } from '@/stores/toast'
import { useRouter } from 'vue-router'
import api from '@/composables/api'

import { WS_INITIAL_BACKOFF_MS, WS_MAX_BACKOFF_MS } from '@/constants'

// Stores all active visibility-change handlers from each consumer so that
// every consumer's closure is invoked when visibility changes (not just the last one).
const _visibilityHandlers = new Set<() => void>()
let _sharedVisibilityListener: (() => void) | null = null

function _installSharedListener(): void {
  if (_sharedVisibilityListener) return
  _sharedVisibilityListener = () => {
    for (const handler of _visibilityHandlers) {
      try {
        handler()
      } catch {
        // Don't let one handler's error break others
      }
    }
  }
  document.addEventListener('visibilitychange', _sharedVisibilityListener)
}

function _removeSharedListener(): void {
  if (_sharedVisibilityListener && _visibilityHandlers.size === 0) {
    document.removeEventListener('visibilitychange', _sharedVisibilityListener)
    _sharedVisibilityListener = null
  }
}

/** Reset module-level state (test-only). */
export function _resetVisibilityState(): void {
  if (_sharedVisibilityListener) {
    document.removeEventListener('visibilitychange', _sharedVisibilityListener)
    _sharedVisibilityListener = null
  }
  _visibilityHandlers.clear()
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
  // Rate-limit PONG responses to prevent PING flood from a malicious server
  let lastPongTimestamp = 0
  const PONG_MIN_INTERVAL_MS = 5000
  // Tracks whether the WS has ever successfully connected in this instance's
  // lifetime. Used to distinguish the initial connection from a reconnection.
  let hasConnectedOnce = false
  const connected = ref(false)

  // Registry of callbacks to invoke after a successful reconnection.
  const _reconnectCallbacks: (() => void)[] = []

  /** Register a callback to be called each time the WebSocket reconnects
   *  (i.e. re-establishes after a prior drop). The callback is NOT called
   *  on the very first connection.
   */
  function onReconnect(cb: () => void): void {
    _reconnectCallbacks.push(cb)
  }

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
        const isReconnect = hasConnectedOnce
        connected.value = true
        backoff = WS_INITIAL_BACKOFF_MS
        hasConnectedOnce = true
        if (isReconnect) {
          for (const cb of _reconnectCallbacks) {
            try {
              cb()
            } catch {
              // Ignore errors in individual callbacks to not block others
            }
          }
        }
      }

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data)
          if (!msg || typeof msg !== 'object' || typeof msg.type !== 'string') return
          if (msg.type === 'PING') {
            const now = Date.now()
            if (now - lastPongTimestamp >= PONG_MIN_INTERVAL_MS) {
              ws?.send(JSON.stringify({ type: 'PONG' }))
              lastPongTimestamp = now
            }
            return
          }
          // Guard: don't process non-PING messages after auth is cleared
          if (!auth.isAuthenticated) return

          if (msg.type === 'FORCE_LOGOUT' || msg.type === 'ROLE_CHANGED') {
            auth.clearSession()
            router.push({ name: 'login' })
          } else if (msg.type === 'NEW_NOTIFICATION') {
            if (msg.notification && typeof msg.notification === 'object') {
              notificationStore.addFromWebSocket(msg.notification)
            }
            toastStore.show(msg.notification?.message || 'New notification', 'info')
          } else if (msg.type === 'NEW_DM') {
            if (
              msg.message &&
              typeof msg.message === 'object' &&
              typeof msg.message.id === 'string' &&
              typeof msg.message.conversation_id === 'string'
            ) {
              dmStore.addFromWebSocket(msg.message)
              // F-09: Don't show toast for own echoed messages (multi-tab sync)
              if (
                dmStore.activeConversationId !== msg.message.conversation_id &&
                msg.message.sender?.id !== auth.user?.id
              ) {
                const rawName = msg.message.sender?.display_name ?? 'someone'
                const senderName = rawName.length > 50 ? rawName.slice(0, 50) + '\u2026' : rawName
                toastStore.show(`New message from ${senderName}`, 'info')
              }
            }
          } else if (msg.type === 'DM_EDITED') {
            if (
              msg.message &&
              typeof msg.message === 'object' &&
              typeof msg.message.id === 'string'
            ) {
              dmStore.updateFromWebSocket(msg.message)
            }
          } else if (msg.type === 'DM_RECALLED') {
            if (typeof msg.message_id === 'string' && typeof msg.conversation_id === 'string') {
              dmStore.recallFromWebSocket(msg.message_id, msg.conversation_id)
            }
          } else if (msg.type === 'DM_READ') {
            if (typeof msg.conversation_id === 'string' && typeof msg.read_at === 'string') {
              // L-05: Validate timestamp before using
              const ts = new Date(msg.read_at).getTime()
              if (!isNaN(ts)) {
                dmStore.readReceiptFromWebSocket(msg.conversation_id, msg.read_at)
              }
            }
          } else if (msg.type === 'SIG_ROLE_CHANGED') {
            if (typeof msg.sig_id === 'string' && typeof msg.new_role === 'string') {
              auth.setSigRoleChange(msg.sig_id, msg.new_role)
            }
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

  _visibilityHandlers.add(handleVisibility)
  _installSharedListener()

  onUnmounted(() => {
    try {
      _visibilityHandlers.delete(handleVisibility)
      _removeSharedListener()
      cleanup()
    } catch {
      // Ensure cleanup runs even if listener removal fails
      cleanup()
    }
  })

  return { connected, connect, cleanup, onReconnect }
}

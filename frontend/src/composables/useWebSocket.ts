import { ref, onUnmounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useRouter } from 'vue-router'

const MAX_BACKOFF = 30_000
const INITIAL_BACKOFF = 1_000

export function useWebSocket() {
  const auth = useAuthStore()
  const router = useRouter()

  let ws: WebSocket | null = null
  let backoff = INITIAL_BACKOFF
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null
  const connected = ref(false)

  function getWsUrl(): string {
    const protocol = location.protocol === 'https:' ? 'wss' : 'ws'
    return `${protocol}://${location.host}/api/v1/ws?token=${encodeURIComponent(auth.token || '')}`
  }

  function connect() {
    if (!auth.isAuthenticated || !auth.token) return
    cleanup()

    ws = new WebSocket(getWsUrl())

    ws.onopen = () => {
      connected.value = true
      backoff = INITIAL_BACKOFF
    }

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data)
        if (msg.type === 'PING') {
          ws?.send(JSON.stringify({ type: 'PONG' }))
        } else if (msg.type === 'FORCE_LOGOUT') {
          auth.clearSession()
          router.push({ name: 'login' })
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

    backoff = Math.min(backoff * 2, MAX_BACKOFF)
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
      backoff = INITIAL_BACKOFF
      connect()
    }
  }

  document.addEventListener('visibilitychange', handleVisibility)

  onUnmounted(() => {
    document.removeEventListener('visibilitychange', handleVisibility)
    cleanup()
  })

  return { connected, connect, cleanup }
}

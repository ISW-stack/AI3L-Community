import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

// ---------------------------------------------------------------------------
// Hoisted mocks — vi.hoisted() runs before vi.mock() factories
// ---------------------------------------------------------------------------

const {
  onUnmountedCallbacks,
  mockClearSession,
  mockIsAuthenticatedRef,
  mockAddFromWebSocket,
  mockToastShow,
  mockRouterPush,
  mockApiPost,
  mockDmAddFromWebSocket,
  mockDmUpdateFromWebSocket,
  mockDmRecallFromWebSocket,
  mockDmReadReceiptFromWebSocket,
  mockDmActiveConversationId,
  mockSetSigRoleChange,
} = vi.hoisted(() => ({
  onUnmountedCallbacks: [] as (() => void)[],
  mockClearSession: vi.fn(),
  mockIsAuthenticatedRef: { value: true },
  mockAddFromWebSocket: vi.fn(),
  mockToastShow: vi.fn(),
  mockRouterPush: vi.fn(),
  mockApiPost: vi.fn(),
  mockDmAddFromWebSocket: vi.fn(),
  mockDmUpdateFromWebSocket: vi.fn(),
  mockDmRecallFromWebSocket: vi.fn(),
  mockDmReadReceiptFromWebSocket: vi.fn(),
  mockDmActiveConversationId: { value: null as string | null },
  mockSetSigRoleChange: vi.fn(),
}))

// ---------------------------------------------------------------------------
// Module mocks
// ---------------------------------------------------------------------------

vi.mock('vue', async () => {
  const actual = await vi.importActual<typeof import('vue')>('vue')
  return {
    ...actual,
    onUnmounted: vi.fn((cb: () => void) => {
      onUnmountedCallbacks.push(cb)
    }),
  }
})

vi.mock('@/constants', () => ({
  WS_INITIAL_BACKOFF_MS: 1000,
  WS_MAX_BACKOFF_MS: 30000,
}))

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({
    get isAuthenticated() {
      return mockIsAuthenticatedRef.value
    },
    clearSession: mockClearSession,
    setSigRoleChange: mockSetSigRoleChange,
  }),
}))

vi.mock('@/stores/notifications', () => ({
  useNotificationStore: () => ({
    addFromWebSocket: mockAddFromWebSocket,
  }),
}))

vi.mock('@/stores/dm', () => ({
  useDMStore: () => ({
    addFromWebSocket: mockDmAddFromWebSocket,
    updateFromWebSocket: mockDmUpdateFromWebSocket,
    recallFromWebSocket: mockDmRecallFromWebSocket,
    readReceiptFromWebSocket: mockDmReadReceiptFromWebSocket,
    get activeConversationId() {
      return mockDmActiveConversationId.value
    },
  }),
}))

vi.mock('@/stores/toast', () => ({
  useToastStore: () => ({
    show: mockToastShow,
  }),
}))

vi.mock('vue-router', () => ({
  useRouter: () => ({
    push: mockRouterPush,
  }),
}))

vi.mock('@/composables/api', () => ({
  default: {
    post: mockApiPost,
  },
}))

// ---------------------------------------------------------------------------
// WebSocket mock class
// ---------------------------------------------------------------------------

type WsHandler = ((event: unknown) => void) | null

class MockWebSocket {
  static instances: MockWebSocket[] = []

  url: string
  onopen: WsHandler = null
  onclose: WsHandler = null
  onerror: WsHandler = null
  onmessage: WsHandler = null
  close = vi.fn(() => {
    // Trigger onclose if it exists (simulates real WebSocket behavior)
    if (this.onclose) this.onclose({})
  })
  send = vi.fn()

  constructor(url: string) {
    this.url = url
    MockWebSocket.instances.push(this)
  }

  // Test helpers
  simulateOpen() {
    this.onopen?.({})
  }
  simulateClose() {
    this.onclose?.({})
  }
  simulateError() {
    this.onerror?.({})
  }
  simulateMessage(data: unknown) {
    this.onmessage?.({ data: JSON.stringify(data) })
  }
  simulateRawMessage(data: string) {
    this.onmessage?.({ data })
  }
}

// ---------------------------------------------------------------------------
// Import under test (after all mocks)
// ---------------------------------------------------------------------------

import { useWebSocket, _resetVisibilityState } from '../useWebSocket'

// ---------------------------------------------------------------------------
// Test suite
// ---------------------------------------------------------------------------

describe('useWebSocket', () => {
  beforeEach(() => {
    _resetVisibilityState()
    onUnmountedCallbacks.length = 0
    vi.clearAllMocks()
    vi.useFakeTimers()
    MockWebSocket.instances = []
    mockIsAuthenticatedRef.value = true

    // Default: ticket request succeeds
    mockApiPost.mockResolvedValue({ data: { ticket: 'test-ticket-123' } })

    // Stub global WebSocket
    vi.stubGlobal('WebSocket', MockWebSocket)

    // Stub location for URL construction
    vi.stubGlobal('location', { protocol: 'http:', host: 'localhost:8080' })

    // Ensure document.hidden is false by default
    Object.defineProperty(document, 'hidden', { value: false, configurable: true })
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
  })

  // -------------------------------------------------------------------------
  // Connection establishment
  // -------------------------------------------------------------------------

  describe('connect', () => {
    it('requests a WS ticket and opens a WebSocket', async () => {
      const { connect } = useWebSocket()
      await connect()

      expect(mockApiPost).toHaveBeenCalledWith('/auth/ws-ticket')
      expect(MockWebSocket.instances).toHaveLength(1)
      expect(MockWebSocket.instances[0].url).toBe(
        'ws://localhost:8080/api/v1/ws?ticket=test-ticket-123',
      )
    })

    it('uses wss protocol when location.protocol is https', async () => {
      vi.stubGlobal('location', { protocol: 'https:', host: 'example.com' })

      const { connect } = useWebSocket()
      await connect()

      expect(MockWebSocket.instances[0].url.startsWith('wss://')).toBe(true)
    })

    it('encodes the ticket in the URL', async () => {
      mockApiPost.mockResolvedValue({ data: { ticket: 'ticket with spaces&special=chars' } })

      const { connect } = useWebSocket()
      await connect()

      expect(MockWebSocket.instances[0].url).toContain(
        encodeURIComponent('ticket with spaces&special=chars'),
      )
    })

    it('does nothing when user is not authenticated', async () => {
      mockIsAuthenticatedRef.value = false

      const { connect } = useWebSocket()
      await connect()

      expect(mockApiPost).not.toHaveBeenCalled()
      expect(MockWebSocket.instances).toHaveLength(0)
    })

    it('schedules reconnect when ticket request fails', async () => {
      mockApiPost.mockRejectedValue(new Error('Network error'))

      const { connect, connected } = useWebSocket()
      await connect()

      expect(MockWebSocket.instances).toHaveLength(0)
      expect(connected.value).toBe(false)

      // A reconnect timer should have been scheduled
      // Advance past initial backoff (1000ms)
      mockApiPost.mockResolvedValue({ data: { ticket: 'retry-ticket' } })
      await vi.advanceTimersByTimeAsync(1000)

      // Should attempt reconnect
      expect(mockApiPost).toHaveBeenCalledTimes(2)
    })
  })

  // -------------------------------------------------------------------------
  // Connection state management
  // -------------------------------------------------------------------------

  describe('connection state', () => {
    it('sets connected to true on ws open', async () => {
      const { connect, connected } = useWebSocket()
      await connect()

      expect(connected.value).toBe(false)

      MockWebSocket.instances[0].simulateOpen()
      expect(connected.value).toBe(true)
    })

    it('sets connected to false on ws close', async () => {
      const { connect, connected } = useWebSocket()
      await connect()
      const ws = MockWebSocket.instances[0]

      ws.simulateOpen()
      expect(connected.value).toBe(true)

      ws.simulateClose()
      expect(connected.value).toBe(false)
    })

    it('resets backoff on successful open', async () => {
      // Force a failed connect first to increase backoff
      mockApiPost.mockRejectedValueOnce(new Error('fail'))

      const { connect } = useWebSocket()
      await connect() // fails, backoff goes 1000 -> 2000

      // Now succeed
      mockApiPost.mockResolvedValue({ data: { ticket: 'ticket' } })
      await vi.advanceTimersByTimeAsync(1000)
      const ws = MockWebSocket.instances[0]
      ws.simulateOpen()

      // Close to trigger reconnect — backoff should be reset to 1000
      ws.simulateClose()

      // If backoff was reset, reconnect attempt happens at 1000ms, not 2000ms
      mockApiPost.mockResolvedValue({ data: { ticket: 'ticket2' } })
      await vi.advanceTimersByTimeAsync(1000)
      expect(MockWebSocket.instances).toHaveLength(2)
    })
  })

  // -------------------------------------------------------------------------
  // Message handling
  // -------------------------------------------------------------------------

  describe('message handling', () => {
    it('responds to PING with PONG', async () => {
      const { connect } = useWebSocket()
      await connect()
      const ws = MockWebSocket.instances[0]
      ws.simulateOpen()

      ws.simulateMessage({ type: 'PING' })

      expect(ws.send).toHaveBeenCalledWith(JSON.stringify({ type: 'PONG' }))
    })

    it('handles FORCE_LOGOUT by clearing session and navigating to login', async () => {
      const { connect } = useWebSocket()
      await connect()
      const ws = MockWebSocket.instances[0]
      ws.simulateOpen()

      ws.simulateMessage({ type: 'FORCE_LOGOUT' })

      expect(mockClearSession).toHaveBeenCalled()
      expect(mockRouterPush).toHaveBeenCalledWith({ name: 'login' })
    })

    it('handles ROLE_CHANGED by clearing session and navigating to login', async () => {
      const { connect } = useWebSocket()
      await connect()
      const ws = MockWebSocket.instances[0]
      ws.simulateOpen()

      ws.simulateMessage({ type: 'ROLE_CHANGED', new_role: 'MEMBER' })

      expect(mockClearSession).toHaveBeenCalled()
      expect(mockRouterPush).toHaveBeenCalledWith({ name: 'login' })
    })

    it('handles NEW_NOTIFICATION by adding to store and showing toast', async () => {
      const notification = { id: 'n1', message: 'You have a reply' }

      const { connect } = useWebSocket()
      await connect()
      const ws = MockWebSocket.instances[0]
      ws.simulateOpen()

      ws.simulateMessage({ type: 'NEW_NOTIFICATION', notification })

      expect(mockAddFromWebSocket).toHaveBeenCalledWith(notification)
      expect(mockToastShow).toHaveBeenCalledWith('You have a reply', 'info')
    })

    it('shows fallback toast message when notification.message is missing', async () => {
      const { connect } = useWebSocket()
      await connect()
      const ws = MockWebSocket.instances[0]
      ws.simulateOpen()

      ws.simulateMessage({ type: 'NEW_NOTIFICATION', notification: {} })

      expect(mockToastShow).toHaveBeenCalledWith('New notification', 'info')
    })

    it('does not call addFromWebSocket when notification is null', async () => {
      const { connect } = useWebSocket()
      await connect()
      const ws = MockWebSocket.instances[0]
      ws.simulateOpen()

      ws.simulateMessage({ type: 'NEW_NOTIFICATION', notification: null })

      expect(mockAddFromWebSocket).not.toHaveBeenCalled()
      expect(mockToastShow).toHaveBeenCalledWith('New notification', 'info')
    })

    it('does not call addFromWebSocket when notification is undefined', async () => {
      const { connect } = useWebSocket()
      await connect()
      const ws = MockWebSocket.instances[0]
      ws.simulateOpen()

      ws.simulateMessage({ type: 'NEW_NOTIFICATION' })

      expect(mockAddFromWebSocket).not.toHaveBeenCalled()
      expect(mockToastShow).toHaveBeenCalledWith('New notification', 'info')
    })

    it('ignores NEW_NOTIFICATION after FORCE_LOGOUT clears auth', async () => {
      const { connect } = useWebSocket()
      await connect()
      const ws = MockWebSocket.instances[0]
      ws.simulateOpen()

      // FORCE_LOGOUT clears auth state
      ws.simulateMessage({ type: 'FORCE_LOGOUT' })
      expect(mockClearSession).toHaveBeenCalled()

      // After FORCE_LOGOUT, isAuthenticated is now false
      mockIsAuthenticatedRef.value = false
      mockClearSession.mockClear()
      mockAddFromWebSocket.mockClear()
      mockToastShow.mockClear()

      // Subsequent NEW_NOTIFICATION should be ignored
      ws.simulateMessage({ type: 'NEW_NOTIFICATION', notification: { id: 'n1', message: 'Hello' } })

      expect(mockAddFromWebSocket).not.toHaveBeenCalled()
      expect(mockToastShow).not.toHaveBeenCalled()
    })

    it('still responds to PING after auth is cleared', async () => {
      const { connect } = useWebSocket()
      await connect()
      const ws = MockWebSocket.instances[0]
      ws.simulateOpen()

      // Clear auth
      mockIsAuthenticatedRef.value = false

      // PING should still work (keepalive must always respond)
      ws.simulateMessage({ type: 'PING' })
      expect(ws.send).toHaveBeenCalledWith(JSON.stringify({ type: 'PONG' }))
    })

    it('calls setSigRoleChange on SIG_ROLE_CHANGED event', async () => {
      const { connect } = useWebSocket()
      await connect()
      const ws = MockWebSocket.instances[0]
      ws.simulateOpen()

      const sigId = 'sig-uuid-123'
      ws.simulateMessage({ type: 'SIG_ROLE_CHANGED', sig_id: sigId, new_role: 'MEMBER' })

      expect(mockSetSigRoleChange).toHaveBeenCalledWith(sigId, 'MEMBER')
    })

    it('calls setSigRoleChange with SUB_ADMIN on promotion event', async () => {
      const { connect } = useWebSocket()
      await connect()
      const ws = MockWebSocket.instances[0]
      ws.simulateOpen()

      ws.simulateMessage({ type: 'SIG_ROLE_CHANGED', sig_id: 'sig-abc', new_role: 'SUB_ADMIN' })

      expect(mockSetSigRoleChange).toHaveBeenCalledWith('sig-abc', 'SUB_ADMIN')
    })

    it('ignores unknown message types without error', async () => {
      const { connect } = useWebSocket()
      await connect()
      const ws = MockWebSocket.instances[0]
      ws.simulateOpen()

      // Should not throw
      ws.simulateMessage({ type: 'UNKNOWN_TYPE', data: 'whatever' })

      expect(mockClearSession).not.toHaveBeenCalled()
      expect(mockAddFromWebSocket).not.toHaveBeenCalled()
    })

    it('ignores malformed (non-JSON) messages', async () => {
      const { connect } = useWebSocket()
      await connect()
      const ws = MockWebSocket.instances[0]
      ws.simulateOpen()

      // Should not throw
      ws.simulateRawMessage('not valid json {{{')

      expect(mockClearSession).not.toHaveBeenCalled()
      expect(mockAddFromWebSocket).not.toHaveBeenCalled()
    })
  })

  // -------------------------------------------------------------------------
  // Error handling
  // -------------------------------------------------------------------------

  describe('error handling', () => {
    it('closes the socket on error', async () => {
      const { connect } = useWebSocket()
      await connect()
      const ws = MockWebSocket.instances[0]

      ws.simulateError()

      expect(ws.close).toHaveBeenCalled()
    })
  })

  // -------------------------------------------------------------------------
  // Reconnection logic
  // -------------------------------------------------------------------------

  describe('reconnection', () => {
    it('schedules reconnect on close', async () => {
      const { connect } = useWebSocket()
      await connect()
      const ws = MockWebSocket.instances[0]
      ws.simulateOpen()

      // Reset mock to track reconnect call
      mockApiPost.mockResolvedValue({ data: { ticket: 'reconnect-ticket' } })

      ws.simulateClose()

      // Should not reconnect immediately
      expect(MockWebSocket.instances).toHaveLength(1)

      // Advance past backoff
      await vi.advanceTimersByTimeAsync(1000)

      expect(MockWebSocket.instances).toHaveLength(2)
    })

    it('uses exponential backoff', async () => {
      const { connect } = useWebSocket()

      // First connect fails at ticket level to trigger backoff increases
      mockApiPost.mockRejectedValue(new Error('fail'))
      await connect() // backoff: 1000 -> scheduleReconnect sets timer at 1000, then doubles to 2000

      // Advance to trigger first reconnect (at 1000ms)
      await vi.advanceTimersByTimeAsync(1000)
      expect(mockApiPost).toHaveBeenCalledTimes(2)

      // Advance 2000ms for second reconnect
      await vi.advanceTimersByTimeAsync(2000)
      expect(mockApiPost).toHaveBeenCalledTimes(3)

      // Advance 4000ms for third reconnect
      await vi.advanceTimersByTimeAsync(4000)
      expect(mockApiPost).toHaveBeenCalledTimes(4)
    })

    it('caps backoff at WS_MAX_BACKOFF_MS (30000)', async () => {
      const { connect } = useWebSocket()
      mockApiPost.mockRejectedValue(new Error('fail'))

      await connect() // backoff starts at 1000

      // Run through multiple reconnects to exceed max:
      // 1000, 2000, 4000, 8000, 16000, 32000 -> capped at 30000
      for (const delay of [1000, 2000, 4000, 8000, 16000]) {
        await vi.advanceTimersByTimeAsync(delay)
      }

      const callsBefore = mockApiPost.mock.calls.length

      // Next reconnect should be at 30000ms (capped), not 32000ms
      await vi.advanceTimersByTimeAsync(30000)
      expect(mockApiPost).toHaveBeenCalledTimes(callsBefore + 1)
    })

    it('does not schedule reconnect when not authenticated', async () => {
      const { connect } = useWebSocket()
      await connect()
      const ws = MockWebSocket.instances[0]
      ws.simulateOpen()

      // User logs out while connected
      mockIsAuthenticatedRef.value = false
      ws.simulateClose()

      mockApiPost.mockResolvedValue({ data: { ticket: 'ticket' } })
      await vi.advanceTimersByTimeAsync(5000)

      // No new WebSocket should have been created
      expect(MockWebSocket.instances).toHaveLength(1)
    })

    it('does not schedule reconnect when document is hidden', async () => {
      const { connect } = useWebSocket()
      await connect()
      const ws = MockWebSocket.instances[0]
      ws.simulateOpen()

      // Simulate hidden document
      Object.defineProperty(document, 'hidden', { value: true, configurable: true })

      ws.simulateClose()

      mockApiPost.mockResolvedValue({ data: { ticket: 'ticket' } })
      await vi.advanceTimersByTimeAsync(5000)

      // No reconnect
      expect(MockWebSocket.instances).toHaveLength(1)

      // Restore
      Object.defineProperty(document, 'hidden', { value: false, configurable: true })
    })
  })

  // -------------------------------------------------------------------------
  // Cleanup
  // -------------------------------------------------------------------------

  describe('cleanup', () => {
    it('closes WebSocket and clears reconnect timer', async () => {
      const { connect, cleanup, connected } = useWebSocket()
      await connect()
      const ws = MockWebSocket.instances[0]

      // Prevent close handler from scheduling reconnect
      ws.close = vi.fn()
      ws.simulateOpen()
      expect(connected.value).toBe(true)

      cleanup()

      expect(ws.close).toHaveBeenCalled()
      expect(connected.value).toBe(false)
    })

    it('nullifies WebSocket event handlers before closing', async () => {
      const { connect, cleanup } = useWebSocket()
      await connect()
      const ws = MockWebSocket.instances[0]
      ws.close = vi.fn() // prevent triggering onclose

      cleanup()

      expect(ws.onclose).toBeNull()
      expect(ws.onerror).toBeNull()
      expect(ws.onmessage).toBeNull()
    })

    it('cancels pending reconnect timer', async () => {
      mockApiPost.mockRejectedValue(new Error('fail'))

      const { connect, cleanup } = useWebSocket()
      await connect() // This will fail and schedule a reconnect

      cleanup()

      // Advance past what would have been the reconnect
      mockApiPost.mockResolvedValue({ data: { ticket: 'ticket' } })
      await vi.advanceTimersByTimeAsync(5000)

      // No new WebSocket should be created since cleanup cancelled the timer
      expect(MockWebSocket.instances).toHaveLength(0)
    })

    it('cleans up previous WebSocket when connect is called again', async () => {
      const { connect } = useWebSocket()
      await connect()
      const firstWs = MockWebSocket.instances[0]
      firstWs.close = vi.fn() // prevent side effects

      await connect()

      expect(firstWs.close).toHaveBeenCalled()
      expect(MockWebSocket.instances).toHaveLength(2)
    })

    // B10: concurrent connect() calls should not create duplicate WebSocket instances
    it('concurrent connect() calls do not create duplicate WebSocket instances', async () => {
      // Make getWsUrl take some time to simulate the race window
      let resolveTicket: (value: { data: { ticket: string } }) => void
      mockApiPost.mockImplementation(
        () =>
          new Promise((resolve) => {
            resolveTicket = resolve
          }),
      )

      const { connect } = useWebSocket()

      // Fire two connect() calls concurrently (simulating rapid tab switch)
      const first = connect()
      const second = connect() // should be skipped due to connecting guard

      // Resolve the ticket for the first call
      resolveTicket!({ data: { ticket: 'only-ticket' } })
      await first
      await second

      // Only one WebSocket should have been created
      expect(MockWebSocket.instances).toHaveLength(1)
      expect(mockApiPost).toHaveBeenCalledTimes(1)
    })

    it('connecting flag is reset after connect completes, allowing subsequent calls', async () => {
      const { connect } = useWebSocket()

      await connect()
      expect(MockWebSocket.instances).toHaveLength(1)

      // Second sequential call should work (connecting flag was reset)
      await connect()
      expect(MockWebSocket.instances).toHaveLength(2)
    })

    it('connecting flag is reset even when getWsUrl fails', async () => {
      mockApiPost.mockRejectedValueOnce(new Error('fail'))

      const { connect } = useWebSocket()
      await connect() // fails, but connecting should be reset

      // Next call should proceed
      mockApiPost.mockResolvedValue({ data: { ticket: 'retry-ticket' } })
      await connect()

      expect(MockWebSocket.instances).toHaveLength(1)
    })

    it('is safe to call cleanup when no WebSocket exists', () => {
      const { cleanup } = useWebSocket()

      // Should not throw
      expect(() => cleanup()).not.toThrow()
    })
  })

  // -------------------------------------------------------------------------
  // onUnmounted lifecycle
  // -------------------------------------------------------------------------

  describe('onUnmounted', () => {
    it('registers an onUnmounted callback', () => {
      useWebSocket()
      expect(onUnmountedCallbacks.length).toBeGreaterThan(0)
    })

    it('onUnmounted callback cleans up WebSocket', async () => {
      const { connect } = useWebSocket()
      await connect()
      const ws = MockWebSocket.instances[0]
      ws.close = vi.fn()

      // Simulate component unmount
      const unmountCb = onUnmountedCallbacks[onUnmountedCallbacks.length - 1]
      unmountCb()

      expect(ws.close).toHaveBeenCalled()
    })
  })

  // -------------------------------------------------------------------------
  // Visibility change handling
  // -------------------------------------------------------------------------

  describe('visibility change', () => {
    it('registers visibilitychange listener', () => {
      const addSpy = vi.spyOn(document, 'addEventListener')
      useWebSocket()
      expect(addSpy).toHaveBeenCalledWith('visibilitychange', expect.any(Function))
      addSpy.mockRestore()
    })

    it('replaces stale handler when second consumer registers', () => {
      const addSpy = vi.spyOn(document, 'addEventListener')
      const removeSpy = vi.spyOn(document, 'removeEventListener')

      useWebSocket()
      // First consumer registers a listener
      expect(addSpy).toHaveBeenCalledTimes(1)

      useWebSocket()
      // Second consumer replaces the stale handler: remove old + add new
      expect(removeSpy).toHaveBeenCalledWith('visibilitychange', expect.any(Function))
      expect(addSpy).toHaveBeenCalledTimes(2)

      addSpy.mockRestore()
      removeSpy.mockRestore()
    })

    it('removes visibilitychange listener only when last consumer unmounts', () => {
      const removeSpy = vi.spyOn(document, 'removeEventListener')

      // Two consumers share the same listener
      useWebSocket()
      useWebSocket()

      // Clear spy to reset call counts from registration-time replacement
      removeSpy.mockClear()

      // First unmount: listener should NOT be fully removed (still 1 consumer)
      const firstUnmount = onUnmountedCallbacks[0]
      firstUnmount()
      expect(removeSpy).not.toHaveBeenCalledWith('visibilitychange', expect.any(Function))

      // Second unmount: listener should be removed (0 consumers)
      const secondUnmount = onUnmountedCallbacks[1]
      secondUnmount()
      expect(removeSpy).toHaveBeenCalledWith('visibilitychange', expect.any(Function))

      removeSpy.mockRestore()
    })
  })

  // -------------------------------------------------------------------------
  // onReconnect callbacks (DM-02)
  // -------------------------------------------------------------------------

  describe('onReconnect', () => {
    it('does NOT fire callback on the first connection', async () => {
      const cb = vi.fn()
      const { connect, onReconnect } = useWebSocket()
      onReconnect(cb)

      await connect()
      MockWebSocket.instances[0].simulateOpen()

      expect(cb).not.toHaveBeenCalled()
    })

    it('fires callback on reconnection after a prior connection drops', async () => {
      const cb = vi.fn()
      const { connect, onReconnect } = useWebSocket()
      onReconnect(cb)

      // Initial connection
      await connect()
      MockWebSocket.instances[0].simulateOpen()
      expect(cb).not.toHaveBeenCalled()

      // Connection drops → schedules reconnect
      mockApiPost.mockResolvedValue({ data: { ticket: 'reconnect-ticket' } })
      MockWebSocket.instances[0].simulateClose()

      // Reconnect fires
      await vi.advanceTimersByTimeAsync(1000)
      MockWebSocket.instances[1].simulateOpen()

      expect(cb).toHaveBeenCalledTimes(1)
    })

    it('fires all registered callbacks on reconnection', async () => {
      const cb1 = vi.fn()
      const cb2 = vi.fn()
      const { connect, onReconnect } = useWebSocket()
      onReconnect(cb1)
      onReconnect(cb2)

      await connect()
      MockWebSocket.instances[0].simulateOpen()

      mockApiPost.mockResolvedValue({ data: { ticket: 'ticket2' } })
      MockWebSocket.instances[0].simulateClose()
      await vi.advanceTimersByTimeAsync(1000)
      MockWebSocket.instances[1].simulateOpen()

      expect(cb1).toHaveBeenCalledTimes(1)
      expect(cb2).toHaveBeenCalledTimes(1)
    })

    it('fires callback on each subsequent reconnection', async () => {
      const cb = vi.fn()
      const { connect, onReconnect } = useWebSocket()
      onReconnect(cb)

      await connect()
      MockWebSocket.instances[0].simulateOpen()

      // First reconnect
      mockApiPost.mockResolvedValue({ data: { ticket: 't2' } })
      MockWebSocket.instances[0].simulateClose()
      await vi.advanceTimersByTimeAsync(1000)
      MockWebSocket.instances[1].simulateOpen()
      expect(cb).toHaveBeenCalledTimes(1)

      // Second reconnect
      mockApiPost.mockResolvedValue({ data: { ticket: 't3' } })
      MockWebSocket.instances[1].simulateClose()
      await vi.advanceTimersByTimeAsync(1000)
      MockWebSocket.instances[2].simulateOpen()
      expect(cb).toHaveBeenCalledTimes(2)
    })

    it('continues firing remaining callbacks even if one throws', async () => {
      const throwing = vi.fn(() => {
        throw new Error('callback error')
      })
      const safe = vi.fn()
      const { connect, onReconnect } = useWebSocket()
      onReconnect(throwing)
      onReconnect(safe)

      await connect()
      MockWebSocket.instances[0].simulateOpen()

      mockApiPost.mockResolvedValue({ data: { ticket: 'ticket2' } })
      MockWebSocket.instances[0].simulateClose()
      await vi.advanceTimersByTimeAsync(1000)
      MockWebSocket.instances[1].simulateOpen()

      expect(throwing).toHaveBeenCalledTimes(1)
      expect(safe).toHaveBeenCalledTimes(1)
    })
  })

  // -------------------------------------------------------------------------
  // Return value
  // -------------------------------------------------------------------------

  describe('return value', () => {
    it('returns connected ref, connect, cleanup and onReconnect functions', () => {
      const result = useWebSocket()

      expect(result).toHaveProperty('connected')
      expect(result).toHaveProperty('connect')
      expect(result).toHaveProperty('cleanup')
      expect(result).toHaveProperty('onReconnect')
      expect(typeof result.connect).toBe('function')
      expect(typeof result.cleanup).toBe('function')
      expect(typeof result.onReconnect).toBe('function')
    })
  })
})

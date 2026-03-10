import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import NotificationBell from '../NotificationBell.vue'

// Mock api to prevent axios initialization
vi.mock('@/composables/api', () => ({
  default: {
    post: vi.fn(),
    get: vi.fn(),
  },
}))

vi.mock('@/constants', () => ({
  HEARTBEAT_INTERVAL_MS: 30000,
  WS_INITIAL_BACKOFF_MS: 1000,
  WS_MAX_BACKOFF_MS: 30000,
}))

// Mock notification store
const mockFetchUnreadCount = vi.fn()
const mockFetchRecent = vi.fn()
const mockMarkRead = vi.fn()
const mockMarkAllRead = vi.fn()

vi.mock('@/stores/notifications', () => ({
  useNotificationStore: () => ({
    unreadCount: 0,
    items: [],
    loading: false,
    fetchUnreadCount: mockFetchUnreadCount,
    fetchRecent: mockFetchRecent,
    markRead: mockMarkRead,
    markAllRead: mockMarkAllRead,
    addFromWebSocket: vi.fn(),
  }),
}))

// Mock auth store (used transitively)
vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({
    role: 'MEMBER',
    isAuthenticated: true,
    isAdmin: false,
    isSuperAdmin: false,
    isGuest: false,
    clearSession: vi.fn(),
  }),
}))

// Mock toast store
vi.mock('@/stores/toast', () => ({
  useToastStore: () => ({
    toasts: [],
    show: vi.fn(),
    dismiss: vi.fn(),
    clearAll: vi.fn(),
  }),
}))

// Mock datetime utility
vi.mock('@/utils/datetime', () => ({
  relativeTime: (date: string) => date,
}))

function createTestRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: { template: '<div />' } },
      { path: '/notifications', component: { template: '<div />' } },
      { path: '/forum/:id', component: { template: '<div />' } },
    ],
  })
}

function mountBell() {
  const router = createTestRouter()
  const pinia = createPinia()
  setActivePinia(pinia)

  const wrapper = mount(NotificationBell, {
    global: {
      plugins: [pinia, router],
      stubs: {
        Bell: { template: '<span class="icon-bell" />' },
        Settings: { template: '<span class="icon-settings" />' },
        User: { template: '<span class="icon-user" />' },
        RouterLink: { template: '<a><slot /></a>' },
      },
    },
  })

  return { wrapper }
}

describe('NotificationBell', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    mockFetchUnreadCount.mockReset()
    mockFetchRecent.mockReset()
    mockMarkRead.mockReset()
    mockMarkAllRead.mockReset()
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.restoreAllMocks()
  })

  // ---------- event listener registration ----------

  describe('click outside listener', () => {
    it('adds a click listener on mount', () => {
      const addSpy = vi.spyOn(document, 'addEventListener')

      const { wrapper } = mountBell()

      const clickCalls = addSpy.mock.calls.filter(([type]) => type === 'click')
      expect(clickCalls.length).toBeGreaterThanOrEqual(1)

      wrapper.unmount()
      addSpy.mockRestore()
    })

    it('removes the SAME listener reference on unmount', () => {
      const registeredHandlers: EventListener[] = []
      const removedHandlers: EventListener[] = []

      const addSpy = vi
        .spyOn(document, 'addEventListener')
        .mockImplementation((type: string, handler: EventListenerOrEventListenerObject) => {
          if (type === 'click') {
            registeredHandlers.push(handler as EventListener)
          }
        })

      const removeSpy = vi
        .spyOn(document, 'removeEventListener')
        .mockImplementation((type: string, handler: EventListenerOrEventListenerObject) => {
          if (type === 'click') {
            removedHandlers.push(handler as EventListener)
          }
        })

      const { wrapper } = mountBell()
      expect(registeredHandlers).toHaveLength(1)

      wrapper.unmount()
      expect(removedHandlers).toHaveLength(1)

      // The exact same reference must be used for both add and remove
      expect(registeredHandlers[0]).toBe(removedHandlers[0])

      addSpy.mockRestore()
      removeSpy.mockRestore()
    })

    it('does not accumulate listeners on remount', () => {
      const registeredHandlers: EventListener[] = []
      const removedHandlers: EventListener[] = []

      const addSpy = vi
        .spyOn(document, 'addEventListener')
        .mockImplementation((type: string, handler: EventListenerOrEventListenerObject) => {
          if (type === 'click') {
            registeredHandlers.push(handler as EventListener)
          }
        })

      const removeSpy = vi
        .spyOn(document, 'removeEventListener')
        .mockImplementation((type: string, handler: EventListenerOrEventListenerObject) => {
          if (type === 'click') {
            removedHandlers.push(handler as EventListener)
          }
        })

      const router = createTestRouter()
      const pinia = createPinia()
      setActivePinia(pinia)

      const mountOptions = {
        global: {
          plugins: [pinia, router],
          stubs: {
            Bell: { template: '<span class="icon-bell" />' },
            Settings: { template: '<span class="icon-settings" />' },
            User: { template: '<span class="icon-user" />' },
            RouterLink: { template: '<a><slot /></a>' },
          },
        },
      }

      // First mount
      const wrapper1 = mount(NotificationBell, mountOptions)
      expect(registeredHandlers).toHaveLength(1)

      // Unmount — should remove the listener
      wrapper1.unmount()
      expect(removedHandlers).toHaveLength(1)

      // Second mount — should add exactly one new listener (no accumulation)
      const wrapper2 = mount(NotificationBell, mountOptions)
      expect(registeredHandlers).toHaveLength(2)

      wrapper2.unmount()
      expect(removedHandlers).toHaveLength(2)

      addSpy.mockRestore()
      removeSpy.mockRestore()
    })

    it('closes dropdown when clicking outside the wrapper', async () => {
      const { wrapper } = mountBell()

      // Open the dropdown first
      const button = wrapper.find('button[aria-label="Notifications"]')
      await button.trigger('click')

      // Verify dropdown is open
      expect(wrapper.find('.notification-bell-wrapper div').exists()).toBe(true)

      // Simulate a click outside by dispatching a click on document.body
      // (body is not inside .notification-bell-wrapper)
      const clickEvent = new MouseEvent('click', { bubbles: true })
      Object.defineProperty(clickEvent, 'target', { value: document.body, writable: false })

      // Manually invoke the handler captured during mount — trigger via document
      document.dispatchEvent(clickEvent)

      // Wait for Vue reactivity to flush
      await wrapper.vm.$nextTick()

      // Dropdown should now be closed
      expect(wrapper.find('[aria-expanded="true"]').exists()).toBe(false)

      wrapper.unmount()
    })
  })

  // ---------- basic rendering ----------

  describe('initial render', () => {
    it('renders the notification bell button', () => {
      const { wrapper } = mountBell()

      const button = wrapper.find('button[aria-label="Notifications"]')
      expect(button.exists()).toBe(true)

      wrapper.unmount()
    })

    it('calls fetchUnreadCount on mount', () => {
      const { wrapper } = mountBell()

      expect(mockFetchUnreadCount).toHaveBeenCalledOnce()

      wrapper.unmount()
    })
  })
})

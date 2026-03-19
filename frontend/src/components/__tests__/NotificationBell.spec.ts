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

const mockStoreState = {
  unreadCount: 0,
  items: [] as Array<Record<string, unknown>>,
  loading: false,
}

vi.mock('@/stores/notifications', () => ({
  useNotificationStore: () => ({
    get unreadCount() {
      return mockStoreState.unreadCount
    },
    get items() {
      return mockStoreState.items
    },
    get loading() {
      return mockStoreState.loading
    },
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
      { path: '/friends', component: { template: '<div />' } },
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
    mockStoreState.unreadCount = 0
    mockStoreState.items = []
    mockStoreState.loading = false
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

  // ---------- avatar alt text & error handling ----------

  describe('avatar alt text', () => {
    it('renders avatar img with descriptive alt text including actor name', async () => {
      mockStoreState.items = [
        {
          id: 'n1',
          action_type: 'COMMENT',
          entity_type: 'post',
          entity_id: 'p1',
          message: 'Alice commented on your post',
          is_read: false,
          created_at: '2026-01-01T00:00:00Z',
          trigger_user: {
            id: 'u1',
            display_name: 'Alice',
            avatar_url: 'https://example.com/alice.jpg',
          },
        },
      ]

      const { wrapper } = mountBell()

      // Open the dropdown
      const button = wrapper.find('button[aria-label="Notifications"]')
      await button.trigger('click')
      await wrapper.vm.$nextTick()

      const img = wrapper.find('img')
      expect(img.exists()).toBe(true)
      expect(img.attributes('alt')).toBe("Alice's avatar")

      wrapper.unmount()
    })

    it('shows initials fallback when avatar image fails to load', async () => {
      mockStoreState.items = [
        {
          id: 'n2',
          action_type: 'COMMENT',
          entity_type: 'post',
          entity_id: 'p1',
          message: 'Bob commented on your post',
          is_read: false,
          created_at: '2026-01-01T00:00:00Z',
          trigger_user: {
            id: 'u2',
            display_name: 'Bob',
            avatar_url: 'https://example.com/broken.jpg',
          },
        },
      ]

      const { wrapper } = mountBell()

      const button = wrapper.find('button[aria-label="Notifications"]')
      await button.trigger('click')
      await wrapper.vm.$nextTick()

      // Trigger img error
      const img = wrapper.find('img')
      expect(img.exists()).toBe(true)
      await img.trigger('error')
      await wrapper.vm.$nextTick()

      // Image should be gone, initials shown
      expect(wrapper.find('img').exists()).toBe(false)
      const initials = wrapper.find('.text-xs.font-semibold')
      expect(initials.exists()).toBe(true)
      expect(initials.text()).toBe('B')

      wrapper.unmount()
    })
  })

  // ---------- dropdown responsive width ----------

  describe('dropdown responsive width', () => {
    it('has both w-80 and max-w-[calc(100vw-2rem)] for responsive width', async () => {
      const { wrapper } = mountBell()

      const button = wrapper.find('button[aria-label="Notifications"]')
      await button.trigger('click')
      await wrapper.vm.$nextTick()

      const dropdown = wrapper.find('.w-80')
      expect(dropdown.exists()).toBe(true)
      expect(dropdown.classes()).toContain('max-w-[calc(100vw-2rem)]')

      wrapper.unmount()
    })
  })

  // ---------- duplicate fetchRecent guard ----------

  describe('fetchRecent deduplication', () => {
    it('calls fetchRecent exactly once when opening dropdown via click', async () => {
      const { wrapper } = mountBell()

      const button = wrapper.find('button[aria-label="Notifications"]')
      await button.trigger('click')
      await wrapper.vm.$nextTick()

      expect(mockFetchRecent).toHaveBeenCalledTimes(1)

      wrapper.unmount()
    })

    it('calls fetchRecent exactly once when opening dropdown via ArrowDown keyboard nav', async () => {
      const { wrapper } = mountBell()

      const wrapperEl = wrapper.find('.notification-bell-wrapper')
      await wrapperEl.trigger('keydown', { key: 'ArrowDown' })
      await wrapper.vm.$nextTick()

      expect(mockFetchRecent).toHaveBeenCalledTimes(1)

      wrapper.unmount()
    })

    it('does not call fetchRecent again if dropdown is already open', async () => {
      const { wrapper } = mountBell()

      // Open via click
      const button = wrapper.find('button[aria-label="Notifications"]')
      await button.trigger('click')
      await wrapper.vm.$nextTick()
      expect(mockFetchRecent).toHaveBeenCalledTimes(1)

      // Try to open again via ArrowDown while already open — should not fetch again
      const wrapperEl = wrapper.find('.notification-bell-wrapper')
      await wrapperEl.trigger('keydown', { key: 'ArrowDown' })
      await wrapper.vm.$nextTick()

      expect(mockFetchRecent).toHaveBeenCalledTimes(1)

      wrapper.unmount()
    })
  })

  // ---------- i18n strings ----------

  describe('i18n strings', () => {
    it('renders translated "Notifications" header when dropdown is open', async () => {
      const { wrapper } = mountBell()

      const button = wrapper.find('button[aria-label="Notifications"]')
      await button.trigger('click')

      // The i18n key notifications.title resolves to "Notifications" in the en locale
      expect(wrapper.text()).toContain('Notifications')

      wrapper.unmount()
    })

    it('renders translated "No notifications yet." when dropdown is open and empty', async () => {
      const { wrapper } = mountBell()

      const button = wrapper.find('button[aria-label="Notifications"]')
      await button.trigger('click')

      // The i18n key notifications.emptyMessage resolves to "No notifications yet."
      expect(wrapper.text()).toContain('No notifications yet.')

      wrapper.unmount()
    })

    it('renders translated "View All" link when dropdown is open', async () => {
      const { wrapper } = mountBell()

      const button = wrapper.find('button[aria-label="Notifications"]')
      await button.trigger('click')

      // The i18n key notifications.viewAll resolves to "View All"
      expect(wrapper.text()).toContain('View All')

      wrapper.unmount()
    })
  })

  // ---------- entity_type-aware navigation ----------

  describe('navigateToEntity routing', () => {
    it('navigates to /friends for friendship entity_type', async () => {
      mockStoreState.items = [
        {
          id: 'fr1',
          action_type: 'FRIEND_REQUEST',
          entity_type: 'friendship',
          entity_id: 'some-friendship-uuid',
          message: 'You have a new friend request',
          is_read: false,
          created_at: '2026-01-01T00:00:00Z',
          trigger_user: { id: 'u1', display_name: 'Alice', avatar_url: null },
        },
      ]
      mockMarkRead.mockResolvedValue(undefined)

      const router = createTestRouter()
      const pinia = createPinia()
      setActivePinia(pinia)
      const pushSpy = vi.spyOn(router, 'push')

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

      // Open dropdown
      const button = wrapper.find('button[aria-label="Notifications"]')
      await button.trigger('click')
      await wrapper.vm.$nextTick()

      // Click the friend request notification
      const notifBtn = wrapper
        .findAll('button')
        .find((b) => b.text().includes('new friend request'))
      expect(notifBtn).toBeTruthy()
      await notifBtn!.trigger('click')
      await wrapper.vm.$nextTick()

      expect(pushSpy).toHaveBeenCalledWith('/friends')

      wrapper.unmount()
    })

    it('navigates to /forum/:id for post entity_type', async () => {
      mockStoreState.items = [
        {
          id: 'p1',
          action_type: 'LIKE',
          entity_type: 'post',
          entity_id: 'post-123',
          message: 'Alice liked your post',
          is_read: false,
          created_at: '2026-01-01T00:00:00Z',
          trigger_user: { id: 'u1', display_name: 'Alice', avatar_url: null },
        },
      ]
      mockMarkRead.mockResolvedValue(undefined)

      const router = createTestRouter()
      const pinia = createPinia()
      setActivePinia(pinia)
      const pushSpy = vi.spyOn(router, 'push')

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

      const button = wrapper.find('button[aria-label="Notifications"]')
      await button.trigger('click')
      await wrapper.vm.$nextTick()

      const notifBtn = wrapper.findAll('button').find((b) => b.text().includes('Alice liked'))
      expect(notifBtn).toBeTruthy()
      await notifBtn!.trigger('click')
      await wrapper.vm.$nextTick()

      expect(pushSpy).toHaveBeenCalledWith('/forum/post-123')

      wrapper.unmount()
    })

    it('falls back to /notifications for unknown entity_type', async () => {
      mockStoreState.items = [
        {
          id: 'sys1',
          action_type: 'SYSTEM',
          entity_type: null,
          entity_id: null,
          message: 'System maintenance',
          is_read: false,
          created_at: '2026-01-01T00:00:00Z',
          trigger_user: null,
        },
      ]
      mockMarkRead.mockResolvedValue(undefined)

      const router = createTestRouter()
      const pinia = createPinia()
      setActivePinia(pinia)
      const pushSpy = vi.spyOn(router, 'push')

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

      const button = wrapper.find('button[aria-label="Notifications"]')
      await button.trigger('click')
      await wrapper.vm.$nextTick()

      const notifBtn = wrapper
        .findAll('button')
        .find((b) => b.text().includes('System maintenance'))
      expect(notifBtn).toBeTruthy()
      await notifBtn!.trigger('click')
      await wrapper.vm.$nextTick()

      expect(pushSpy).toHaveBeenCalledWith('/notifications')

      wrapper.unmount()
    })
  })
})

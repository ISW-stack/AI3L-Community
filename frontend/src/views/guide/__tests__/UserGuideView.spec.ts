import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import UserGuideView from '../UserGuideView.vue'

vi.mock('@/composables/api', () => ({
  default: { post: vi.fn(), get: vi.fn() },
}))

const mockGetProfile = vi.fn()
vi.mock('@/api/users', () => ({
  getProfile: (...args: unknown[]) => mockGetProfile(...args),
}))

vi.mock('@/api/auth', () => ({
  login: vi.fn(),
  guestLogin: vi.fn(),
  register: vi.fn(),
  logout: vi.fn(),
  heartbeat: vi.fn(),
}))

vi.mock('@/constants', () => ({
  HEARTBEAT_INTERVAL_MS: 30000,
}))

class MockIntersectionObserver {
  observe = vi.fn()
  disconnect = vi.fn()
  unobserve = vi.fn()
  constructor(_cb: unknown, _opts?: unknown) {}
}
vi.stubGlobal('IntersectionObserver', MockIntersectionObserver)

function createTestRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/guide', name: 'guide', component: UserGuideView },
      { path: '/', name: 'home', component: { template: '<div />' } },
      { path: '/login', name: 'login', component: { template: '<div />' } },
    ],
  })
}

async function mountGuide(role: string) {
  localStorage.setItem('role', role)
  localStorage.setItem('expiresAt', String(Date.now() + 3600 * 1000))
  mockGetProfile.mockResolvedValue({ id: '1', username: 'test', role })

  const pinia = createPinia()
  setActivePinia(pinia)
  const router = createTestRouter()
  await router.push('/guide')
  await router.isReady()

  const wrapper = mount(UserGuideView, {
    global: { plugins: [pinia, router] },
  })
  await flushPromises()
  return wrapper
}

describe('UserGuideView', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2025-06-01T00:00:00Z'))
  })

  afterEach(() => {
    vi.useRealTimers()
    localStorage.clear()
  })

  describe('tab visibility by role', () => {
    it('MEMBER sees Guest + Member tabs only', async () => {
      const wrapper = await mountGuide('MEMBER')
      const tabs = wrapper.findAll('[role="tab"]')
      expect(tabs).toHaveLength(2)
      expect(tabs[0].text()).toBe('Guest Guide')
      expect(tabs[1].text()).toBe('Member Guide')
    })

    it('ADMIN sees Guest + Member + Admin tabs', async () => {
      const wrapper = await mountGuide('ADMIN')
      const tabs = wrapper.findAll('[role="tab"]')
      expect(tabs).toHaveLength(3)
      expect(tabs[2].text()).toBe('Admin Guide')
    })

    it('SUPER_ADMIN sees all 4 tabs', async () => {
      const wrapper = await mountGuide('SUPER_ADMIN')
      const tabs = wrapper.findAll('[role="tab"]')
      expect(tabs).toHaveLength(4)
      expect(tabs[3].text()).toBe('Super Admin Guide')
    })
  })

  describe('static imports (no defineAsyncComponent)', () => {
    it('renders guide content synchronously without Suspense', async () => {
      const wrapper = await mountGuide('SUPER_ADMIN')
      expect(wrapper.find('.guide-content').exists()).toBe(true)
    })
  })
})

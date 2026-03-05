import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory, type Router } from 'vue-router'
import { defineComponent } from 'vue'
import { useAuthStore } from '@/stores/auth'

// Mock API modules used by auth store
vi.mock('@/composables/api', () => ({
  default: {
    post: vi.fn(),
    get: vi.fn(),
  },
}))

vi.mock('@/constants', () => ({
  HEARTBEAT_INTERVAL_MS: 30000,
}))

const Stub = defineComponent({ template: '<div>stub</div>' })

function createTestRouter(): Router {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', name: 'home', component: Stub },
      {
        path: '/about',
        name: 'about',
        component: Stub,
        meta: { requiresAuth: true, requiresMember: true },
      },
      { path: '/login', name: 'login', component: Stub, meta: { guest: true } },
      {
        path: '/profile',
        name: 'profile',
        component: Stub,
        meta: { requiresAuth: true },
      },
    ],
  })

  // Replicate the same guard logic from the real router
  router.beforeEach((to) => {
    const auth = useAuthStore()

    if (to.meta.guest && auth.isAuthenticated) {
      return { name: 'home' }
    }

    if (to.meta.requiresAuth && !auth.isAuthenticated) {
      return { name: 'login', query: { redirect: to.fullPath } }
    }

    if (to.meta.requiresMember && auth.isGuest) {
      return { name: 'home' }
    }
  })

  return router
}

describe('Router guards — requiresMember', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2025-06-01T00:00:00Z'))
  })

  afterEach(() => {
    vi.useRealTimers()
    localStorage.clear()
  })

  it('redirects guest user from /about to home', async () => {
    const expiresAt = Date.now() + 3600 * 1000
    localStorage.setItem('role', 'GUEST')
    localStorage.setItem('expiresAt', String(expiresAt))

    setActivePinia(createPinia())
    const router = createTestRouter()

    await router.push('/about')
    await router.isReady()

    expect(router.currentRoute.value.name).toBe('home')
    expect(router.currentRoute.value.path).toBe('/')
  })

  it('redirects unauthenticated user from /about to login', async () => {
    setActivePinia(createPinia())
    const router = createTestRouter()

    await router.push('/about')
    await router.isReady()

    expect(router.currentRoute.value.name).toBe('login')
    expect(router.currentRoute.value.query).toEqual({ redirect: '/about' })
  })

  it('allows member user to access /about', async () => {
    const expiresAt = Date.now() + 3600 * 1000
    localStorage.setItem('role', 'MEMBER')
    localStorage.setItem('expiresAt', String(expiresAt))

    setActivePinia(createPinia())
    const router = createTestRouter()

    await router.push('/about')
    await router.isReady()

    expect(router.currentRoute.value.name).toBe('about')
    expect(router.currentRoute.value.path).toBe('/about')
  })

  it('allows admin user to access /about', async () => {
    const expiresAt = Date.now() + 3600 * 1000
    localStorage.setItem('role', 'ADMIN')
    localStorage.setItem('expiresAt', String(expiresAt))

    setActivePinia(createPinia())
    const router = createTestRouter()

    await router.push('/about')
    await router.isReady()

    expect(router.currentRoute.value.name).toBe('about')
    expect(router.currentRoute.value.path).toBe('/about')
  })

  it('allows super admin user to access /about', async () => {
    const expiresAt = Date.now() + 3600 * 1000
    localStorage.setItem('role', 'SUPER_ADMIN')
    localStorage.setItem('expiresAt', String(expiresAt))

    setActivePinia(createPinia())
    const router = createTestRouter()

    await router.push('/about')
    await router.isReady()

    expect(router.currentRoute.value.name).toBe('about')
    expect(router.currentRoute.value.path).toBe('/about')
  })

  it('allows guest user to access non-member-only authenticated routes', async () => {
    const expiresAt = Date.now() + 3600 * 1000
    localStorage.setItem('role', 'GUEST')
    localStorage.setItem('expiresAt', String(expiresAt))

    setActivePinia(createPinia())
    const router = createTestRouter()

    await router.push('/profile')
    await router.isReady()

    expect(router.currentRoute.value.name).toBe('profile')
    expect(router.currentRoute.value.path).toBe('/profile')
  })
})

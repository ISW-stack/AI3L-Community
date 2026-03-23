import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory, type Router } from 'vue-router'
import { defineComponent } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useToastStore } from '@/stores/toast'

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
      { path: '/login', name: 'login', component: Stub, meta: { guest: true } },
      {
        path: '/guide',
        name: 'guide',
        component: Stub,
        meta: { requiresAuth: true, requiresMember: true },
      },
    ],
  })

  router.beforeEach((to) => {
    const auth = useAuthStore()
    const toast = useToastStore()

    if (to.meta.guest && auth.isAuthenticated) {
      return { name: 'home' }
    }
    if (to.meta.requiresAuth && !auth.isAuthenticated) {
      return { name: 'login', query: { redirect: to.fullPath } }
    }
    if (to.meta.requiresMember && auth.isGuest) {
      toast.show('You must be a full member to access that page.', 'error')
      return { name: 'home' }
    }
  })

  return router
}

describe('Router guards — /guide requiresMember', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2025-06-01T00:00:00Z'))
  })

  afterEach(() => {
    vi.useRealTimers()
    localStorage.clear()
  })

  it('redirects unauthenticated user from /guide to login', async () => {
    setActivePinia(createPinia())
    const router = createTestRouter()

    await router.push('/guide')
    await router.isReady()

    expect(router.currentRoute.value.name).toBe('login')
    expect(router.currentRoute.value.query).toEqual({ redirect: '/guide' })
  })

  it('redirects guest user from /guide to home', async () => {
    const expiresAt = Date.now() + 3600 * 1000
    localStorage.setItem('role', 'GUEST')
    localStorage.setItem('expiresAt', String(expiresAt))

    setActivePinia(createPinia())
    const router = createTestRouter()

    await router.push('/guide')
    await router.isReady()

    expect(router.currentRoute.value.name).toBe('home')
  })

  it('shows toast when guest is blocked from /guide', async () => {
    const expiresAt = Date.now() + 3600 * 1000
    localStorage.setItem('role', 'GUEST')
    localStorage.setItem('expiresAt', String(expiresAt))

    setActivePinia(createPinia())
    const toast = useToastStore()
    const router = createTestRouter()

    await router.push('/guide')
    await router.isReady()

    expect(toast.toasts.length).toBeGreaterThan(0)
    expect(toast.toasts[0].type).toBe('error')
    expect(toast.toasts[0].message).toContain('member')
  })

  it('allows MEMBER to access /guide', async () => {
    const expiresAt = Date.now() + 3600 * 1000
    localStorage.setItem('role', 'MEMBER')
    localStorage.setItem('expiresAt', String(expiresAt))

    setActivePinia(createPinia())
    const router = createTestRouter()

    await router.push('/guide')
    await router.isReady()

    expect(router.currentRoute.value.name).toBe('guide')
  })

  it('allows ADMIN to access /guide', async () => {
    const expiresAt = Date.now() + 3600 * 1000
    localStorage.setItem('role', 'ADMIN')
    localStorage.setItem('expiresAt', String(expiresAt))

    setActivePinia(createPinia())
    const router = createTestRouter()

    await router.push('/guide')
    await router.isReady()

    expect(router.currentRoute.value.name).toBe('guide')
  })

  it('allows SUPER_ADMIN to access /guide', async () => {
    const expiresAt = Date.now() + 3600 * 1000
    localStorage.setItem('role', 'SUPER_ADMIN')
    localStorage.setItem('expiresAt', String(expiresAt))

    setActivePinia(createPinia())
    const router = createTestRouter()

    await router.push('/guide')
    await router.isReady()

    expect(router.currentRoute.value.name).toBe('guide')
  })
})

describe('/guide route meta in real router', () => {
  it('has requiresMember: true on the guide route', async () => {
    const { default: realRouter } = await import('@/router/index')
    const guideRoute = realRouter.getRoutes().find((r) => r.name === 'guide')
    expect(guideRoute).toBeDefined()
    expect(guideRoute!.meta.requiresAuth).toBe(true)
    expect(guideRoute!.meta.requiresMember).toBe(true)
  })
})

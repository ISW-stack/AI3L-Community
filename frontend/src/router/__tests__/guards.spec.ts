import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory, type Router } from 'vue-router'
import { defineComponent } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useToastStore } from '@/stores/toast'

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
      {
        path: '/admin',
        name: 'admin',
        component: Stub,
        meta: { requiresAuth: true, requiresAdmin: true },
      },
      {
        path: '/super',
        name: 'super',
        component: Stub,
        meta: { requiresAuth: true, requiresSuperAdmin: true },
      },
    ],
  })

  // Replicate the same guard logic from the real router (including toast calls)
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

    if (to.meta.requiresAdmin && !auth.isAdmin) {
      toast.show('You do not have permission to access that page.', 'error')
      return { name: 'home' }
    }

    if (to.meta.requiresSuperAdmin && !auth.isSuperAdmin) {
      toast.show('You do not have permission to access that page.', 'error')
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

describe('Router guards — toast on permission redirect (U10)', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2025-06-01T00:00:00Z'))
  })

  afterEach(() => {
    vi.useRealTimers()
    localStorage.clear()
  })

  it('shows toast when guest is redirected from member-only page', async () => {
    const expiresAt = Date.now() + 3600 * 1000
    localStorage.setItem('role', 'GUEST')
    localStorage.setItem('expiresAt', String(expiresAt))

    setActivePinia(createPinia())
    const toast = useToastStore()
    const router = createTestRouter()

    await router.push('/about')
    await router.isReady()

    expect(router.currentRoute.value.name).toBe('home')
    expect(toast.toasts.length).toBeGreaterThan(0)
    expect(toast.toasts[0].type).toBe('error')
    expect(toast.toasts[0].message).toContain('member')
  })

  it('shows toast when non-admin is redirected from admin page', async () => {
    const expiresAt = Date.now() + 3600 * 1000
    localStorage.setItem('role', 'MEMBER')
    localStorage.setItem('expiresAt', String(expiresAt))

    setActivePinia(createPinia())
    const toast = useToastStore()
    const router = createTestRouter()

    await router.push('/admin')
    await router.isReady()

    expect(router.currentRoute.value.name).toBe('home')
    expect(toast.toasts.length).toBeGreaterThan(0)
    expect(toast.toasts[0].type).toBe('error')
    expect(toast.toasts[0].message).toContain('permission')
  })

  it('shows toast when non-superadmin is redirected from super-admin page', async () => {
    const expiresAt = Date.now() + 3600 * 1000
    localStorage.setItem('role', 'ADMIN')
    localStorage.setItem('expiresAt', String(expiresAt))

    setActivePinia(createPinia())
    const toast = useToastStore()
    const router = createTestRouter()

    await router.push('/super')
    await router.isReady()

    expect(router.currentRoute.value.name).toBe('home')
    expect(toast.toasts.length).toBeGreaterThan(0)
    expect(toast.toasts[0].type).toBe('error')
    expect(toast.toasts[0].message).toContain('permission')
  })

  it('does NOT show toast when unauthenticated user is redirected to login', async () => {
    setActivePinia(createPinia())
    const toast = useToastStore()
    const router = createTestRouter()

    await router.push('/about')
    await router.isReady()

    expect(router.currentRoute.value.name).toBe('login')
    // No toast for login redirect — just redirect silently
    expect(toast.toasts.length).toBe(0)
  })
})

describe('Router scrollBehavior (U11)', () => {
  it('scrollBehavior is defined on the real router', async () => {
    // Import the real router and verify scrollBehavior exists
    const { default: realRouter } = await import('@/router/index')
    // Access the options — createRouter stores scrollBehavior internally
    // We verify by calling it directly
    const options = (realRouter as unknown as { options: { scrollBehavior?: unknown } }).options
    expect(typeof options.scrollBehavior).toBe('function')
  })
})

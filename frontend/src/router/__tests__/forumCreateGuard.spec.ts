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
        path: '/forum/create',
        name: 'forum-create',
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

describe('FE-03: forum-create route requires member', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2025-06-01T00:00:00Z'))
  })

  afterEach(() => {
    vi.useRealTimers()
    localStorage.clear()
  })

  it('redirects guest from /forum/create to home', async () => {
    const expiresAt = Date.now() + 3600 * 1000
    localStorage.setItem('role', 'GUEST')
    localStorage.setItem('expiresAt', String(expiresAt))

    setActivePinia(createPinia())
    const router = createTestRouter()

    await router.push('/forum/create')
    await router.isReady()

    expect(router.currentRoute.value.name).toBe('home')
  })

  it('allows member to access /forum/create', async () => {
    const expiresAt = Date.now() + 3600 * 1000
    localStorage.setItem('role', 'MEMBER')
    localStorage.setItem('expiresAt', String(expiresAt))

    setActivePinia(createPinia())
    const router = createTestRouter()

    await router.push('/forum/create')
    await router.isReady()

    expect(router.currentRoute.value.name).toBe('forum-create')
  })

  it('allows admin to access /forum/create', async () => {
    const expiresAt = Date.now() + 3600 * 1000
    localStorage.setItem('role', 'ADMIN')
    localStorage.setItem('expiresAt', String(expiresAt))

    setActivePinia(createPinia())
    const router = createTestRouter()

    await router.push('/forum/create')
    await router.isReady()

    expect(router.currentRoute.value.name).toBe('forum-create')
  })

  it('real router has requiresMember on forum-create route', async () => {
    const { default: realRouter } = await import('@/router/index')
    const route = realRouter.getRoutes().find((r) => r.name === 'forum-create')
    expect(route).toBeDefined()
    expect(route!.meta.requiresMember).toBe(true)
    expect(route!.meta.requiresAuth).toBe(true)
  })
})

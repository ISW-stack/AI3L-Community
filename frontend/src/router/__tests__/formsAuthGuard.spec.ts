import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

vi.mock('@/composables/api', () => ({ default: { post: vi.fn(), get: vi.fn() } }))
vi.mock('@/constants', () => ({ HEARTBEAT_INTERVAL_MS: 30000 }))

import router from '@/router/index'

describe('Route meta — /forms requiresAuth', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2025-06-01T00:00:00Z'))
  })

  afterEach(() => {
    vi.useRealTimers()
    localStorage.clear()
  })

  it('/forms route has requiresAuth: true in meta', () => {
    const formsRoute = router.getRoutes().find((r) => r.name === 'forms')
    expect(formsRoute).toBeDefined()
    expect(formsRoute!.meta.requiresAuth).toBe(true)
  })

  it('redirects unauthenticated user from /forms to login', async () => {
    setActivePinia(createPinia())

    await router.push('/forms')
    await router.isReady()

    expect(router.currentRoute.value.name).toBe('login')
    expect(router.currentRoute.value.query).toEqual({ redirect: '/forms' })
  })

  it('allows authenticated user to access /forms', async () => {
    const expiresAt = Date.now() + 3600 * 1000
    localStorage.setItem('role', 'MEMBER')
    localStorage.setItem('expiresAt', String(expiresAt))

    setActivePinia(createPinia())

    await router.push('/forms')
    await router.isReady()

    expect(router.currentRoute.value.name).toBe('forms')
    expect(router.currentRoute.value.path).toBe('/forms')
  })
})

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

vi.mock('@/composables/api', () => ({ default: { post: vi.fn(), get: vi.fn() } }))
vi.mock('@/constants', () => ({ HEARTBEAT_INTERVAL_MS: 30000 }))

import router from '@/router/index'

describe('Route meta — fullWidth', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2025-06-01T00:00:00Z'))

    const expiresAt = Date.now() + 3600 * 1000
    localStorage.setItem('role', 'SUPER_ADMIN')
    localStorage.setItem('expiresAt', String(expiresAt))

    setActivePinia(createPinia())
  })

  afterEach(() => {
    vi.useRealTimers()
    localStorage.clear()
  })

  it('/admin route has fullWidth meta', async () => {
    await router.push('/admin')
    await router.isReady()
    expect(router.currentRoute.value.meta.fullWidth).toBe(true)
  })

  it('/profile route has fullWidth meta', async () => {
    await router.push('/profile')
    await router.isReady()
    expect(router.currentRoute.value.meta.fullWidth).toBe(true)
  })

  it('/users/:id route has fullWidth meta', async () => {
    await router.push('/users/123')
    await router.isReady()
    expect(router.currentRoute.value.meta.fullWidth).toBe(true)
  })

  it('/sigs/:id route has fullWidth meta', async () => {
    await router.push('/sigs/456')
    await router.isReady()
    expect(router.currentRoute.value.meta.fullWidth).toBe(true)
  })

  it('/forum route does NOT have fullWidth meta', async () => {
    await router.push('/forum')
    await router.isReady()
    expect(router.currentRoute.value.meta.fullWidth).toBeFalsy()
  })

  it('/ (home) route does NOT have fullWidth meta', async () => {
    await router.push('/')
    await router.isReady()
    expect(router.currentRoute.value.meta.fullWidth).toBeFalsy()
  })

  it('/sigs (directory) route does NOT have fullWidth meta', async () => {
    await router.push('/sigs')
    await router.isReady()
    expect(router.currentRoute.value.meta.fullWidth).toBeFalsy()
  })
})

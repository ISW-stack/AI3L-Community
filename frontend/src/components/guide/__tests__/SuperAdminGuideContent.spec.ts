import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import SuperAdminGuideContent from '../SuperAdminGuideContent.vue'

vi.mock('@/composables/api', () => ({
  default: { post: vi.fn(), get: vi.fn() },
}))

vi.mock('@/constants', () => ({
  HEARTBEAT_INTERVAL_MS: 30000,
}))

function mountAs(role?: string) {
  if (role) {
    localStorage.setItem('role', role)
    localStorage.setItem('expiresAt', String(Date.now() + 3600 * 1000))
  }
  const pinia = createPinia()
  setActivePinia(pinia)
  return mount(SuperAdminGuideContent, { global: { plugins: [pinia] } })
}

describe('SuperAdminGuideContent', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2025-06-01T00:00:00Z'))
  })

  afterEach(() => {
    vi.useRealTimers()
    localStorage.clear()
  })

  it('renders content when user is SUPER_ADMIN', () => {
    const wrapper = mountAs('SUPER_ADMIN')
    expect(wrapper.find('.guide-content').exists()).toBe(true)
    expect(wrapper.text()).toContain('Additional Admin Panel Pages')
  })

  it('renders nothing when user is ADMIN', () => {
    const wrapper = mountAs('ADMIN')
    expect(wrapper.find('.guide-content').exists()).toBe(false)
    expect(wrapper.text()).toBe('')
  })

  it('renders nothing when user is MEMBER', () => {
    const wrapper = mountAs('MEMBER')
    expect(wrapper.find('.guide-content').exists()).toBe(false)
  })

  it('renders nothing when user is GUEST', () => {
    const wrapper = mountAs('GUEST')
    expect(wrapper.find('.guide-content').exists()).toBe(false)
  })

  it('renders nothing when user is unauthenticated', () => {
    const wrapper = mountAs()
    expect(wrapper.find('.guide-content').exists()).toBe(false)
  })

  describe('G-06: sensitive info sanitization', () => {
    let text: string

    beforeEach(() => {
      text = mountAs('SUPER_ADMIN').text()
    })

    it('does not disclose health endpoint URL', () => {
      expect(text).not.toContain('GET /health')
      expect(text).not.toContain('/health/live')
    })

    it('does not disclose infrastructure component names', () => {
      expect(text).not.toContain('Redis connection')
      expect(text).not.toContain('MinIO')
      expect(text).not.toContain('Celery worker')
      expect(text).not.toContain('pool statistics')
    })

    it('does not disclose specific audit log event types', () => {
      expect(text).not.toContain('role changes, bans/unbans, deletions')
      expect(text).not.toContain('invite codes, SIG operations')
    })

    it('does not disclose IP ban tactical details', () => {
      expect(text).not.toContain('IPv4 or IPv6')
      expect(text).not.toContain('permanent ban')
      expect(text).not.toContain('immediately unblocked')
    })

    it('does not disclose GitHub username implementation', () => {
      expect(text).not.toContain('GitHub Username')
      expect(text).not.toContain('GitHub usernames')
    })

    it('does not disclose specific system constraints for bypass', () => {
      expect(text).not.toContain('cannot ban yourself')
      expect(text).not.toContain('delete Super Admin accounts')
      expect(text).not.toContain('change your own role')
    })

    it('does not disclose org chart visibility implementation', () => {
      expect(text).not.toContain('only shown to Super Admins')
    })
  })
})

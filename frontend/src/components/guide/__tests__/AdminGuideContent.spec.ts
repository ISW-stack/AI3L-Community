import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import AdminGuideContent from '../AdminGuideContent.vue'

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
  return mount(AdminGuideContent, { global: { plugins: [pinia] } })
}

describe('AdminGuideContent', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2025-06-01T00:00:00Z'))
  })

  afterEach(() => {
    vi.useRealTimers()
    localStorage.clear()
  })

  it('renders content when user is ADMIN', () => {
    const wrapper = mountAs('ADMIN')
    expect(wrapper.find('.guide-content').exists()).toBe(true)
    expect(wrapper.text()).toContain('Admin Panel Overview')
  })

  it('renders content when user is SUPER_ADMIN', () => {
    const wrapper = mountAs('SUPER_ADMIN')
    expect(wrapper.find('.guide-content').exists()).toBe(true)
  })

  it('renders nothing when user is MEMBER', () => {
    const wrapper = mountAs('MEMBER')
    expect(wrapper.find('.guide-content').exists()).toBe(false)
    expect(wrapper.text()).toBe('')
  })

  it('renders nothing when user is GUEST', () => {
    const wrapper = mountAs('GUEST')
    expect(wrapper.find('.guide-content').exists()).toBe(false)
  })

  it('renders nothing when user is unauthenticated', () => {
    const wrapper = mountAs()
    expect(wrapper.find('.guide-content').exists()).toBe(false)
  })

  it('does not disclose specific privilege escalation paths', () => {
    const wrapper = mountAs('ADMIN')
    const text = wrapper.text()
    expect(text).not.toContain('Only Super Admins can create Admin accounts')
    expect(text).not.toContain('SIG Admin-level permissions')
  })
})

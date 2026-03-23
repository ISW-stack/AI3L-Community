import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import GuestGuideContent from '../GuestGuideContent.vue'
import MemberGuideContent from '../MemberGuideContent.vue'

vi.mock('@/composables/api', () => ({
  default: { post: vi.fn(), get: vi.fn() },
}))

vi.mock('@/constants', () => ({
  HEARTBEAT_INTERVAL_MS: 30000,
}))

function mountComponent(Component: typeof GuestGuideContent | typeof MemberGuideContent) {
  const pinia = createPinia()
  setActivePinia(pinia)
  return mount(Component, { global: { plugins: [pinia] } })
}

describe('GuestGuideContent — G-06 sanitization', () => {
  let text: string

  beforeEach(() => {
    localStorage.clear()
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2025-06-01T00:00:00Z'))
    text = mountComponent(GuestGuideContent).text()
  })

  afterEach(() => {
    vi.useRealTimers()
    localStorage.clear()
  })

  it('does not disclose explicit password policy rules', () => {
    expect(text).not.toContain('8+ characters')
    expect(text).not.toContain('uppercase, lowercase, digit')
    expect(text).not.toContain('special character')
  })

  it('still mentions password strength requirement generically', () => {
    expect(text).toContain('strength requirements')
  })

  it('does not disclose session storage implementation', () => {
    expect(text).not.toContain('stored server-side')
  })
})

describe('MemberGuideContent — G-06 sanitization', () => {
  let text: string

  beforeEach(() => {
    localStorage.clear()
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2025-06-01T00:00:00Z'))
    text = mountComponent(MemberGuideContent).text()
  })

  afterEach(() => {
    vi.useRealTimers()
    localStorage.clear()
  })

  it('does not disclose VirusTotal scan HTTP status code', () => {
    expect(text).not.toContain('202 status')
    expect(text).not.toContain('return 202')
  })

  it('does not disclose auto-logout timing', () => {
    expect(text).not.toContain('1.5s')
    expect(text).not.toContain('1.5 seconds')
  })

  it('does not disclose SIG role comparison logic details', () => {
    expect(text).not.toContain('below own level')
  })

  it('does not disclose exact admin SIG privilege level', () => {
    expect(text).not.toContain('SIG Admin-level access')
  })

  it('still provides useful DM retention info for users', () => {
    expect(text).toContain('30 days')
    expect(text).toContain('3 days')
  })

  it('still provides useful file upload limits for users', () => {
    expect(text).toContain('50 MB')
    expect(text).toContain('1 GB')
  })
})

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import ForumLeftSidebar from '../ForumLeftSidebar.vue'
import { useAuthStore } from '@/stores/auth'

const mockListMySigs = vi.fn()

vi.mock('@/api/sigs', () => ({
  listMySigs: (...args: unknown[]) => mockListMySigs(...args),
}))

vi.mock('@/components/base/BaseCard.vue', () => ({
  default: { template: '<div class="base-card"><slot /></div>' },
}))

vi.mock('lucide-vue-next', () => ({
  Home: { template: '<svg data-testid="home-icon" />' },
  Users: { template: '<svg data-testid="users-icon" />' },
  PenSquare: { template: '<svg data-testid="pen-icon" />' },
  Bell: { template: '<svg data-testid="bell-icon" />' },
}))

vi.mock('@/composables/api', () => ({
  default: { get: vi.fn(), post: vi.fn() },
}))

vi.mock('@/constants', () => ({
  HEARTBEAT_INTERVAL_MS: 30000,
}))

function createTestRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: { template: '<div />' } },
      { path: '/forum', component: { template: '<div />' } },
      { path: '/forum/create', component: { template: '<div />' } },
      { path: '/sigs', component: { template: '<div />' } },
      { path: '/sigs/:id', component: { template: '<div />' } },
      { path: '/notifications', component: { template: '<div />' } },
    ],
  })
}

function mountSidebar(authOverrides: { role?: string; userId?: string } = {}) {
  const pinia = createPinia()
  setActivePinia(pinia)

  if (authOverrides.role) {
    localStorage.setItem('role', authOverrides.role)
    localStorage.setItem('expiresAt', String(Date.now() + 3600_000))
  }

  const pinia2 = createPinia()
  setActivePinia(pinia2)
  const auth = useAuthStore()
  if (authOverrides.userId) {
    auth.user = {
      id: authOverrides.userId,
      username: 'testuser',
      display_name: 'Test User',
      role: authOverrides.role ?? 'MEMBER',
      bio: null,
      affiliation: null,
      orcid: null,
      avatar_url: null,
      preferred_language: 'en',
      is_banned: false,
      ban_reason: null,
      created_at: new Date().toISOString(),
    }
  }

  const router = createTestRouter()
  return mount(ForumLeftSidebar, {
    global: { plugins: [pinia2, router] },
  })
}

describe('ForumLeftSidebar', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
    mockListMySigs.mockResolvedValue([])
  })

  it('renders quick links section', () => {
    const wrapper = mountSidebar({ role: 'MEMBER', userId: 'u1' })
    expect(wrapper.text()).toContain('Quick Links')
  })

  it('renders Home Feed link', () => {
    const wrapper = mountSidebar({ role: 'MEMBER', userId: 'u1' })
    const link = wrapper.find('a[href="/forum"]')
    expect(link.exists()).toBe(true)
  })

  it('renders All SIGs link', () => {
    const wrapper = mountSidebar({ role: 'MEMBER', userId: 'u1' })
    const link = wrapper.find('a[href="/sigs"]')
    expect(link.exists()).toBe(true)
  })

  it('renders Create Post link for authenticated non-guest users', () => {
    const wrapper = mountSidebar({ role: 'MEMBER', userId: 'u1' })
    const link = wrapper.find('a[href="/forum/create"]')
    expect(link.exists()).toBe(true)
  })

  it('renders Notifications link for authenticated non-guest users', () => {
    const wrapper = mountSidebar({ role: 'MEMBER', userId: 'u1' })
    const link = wrapper.find('a[href="/notifications"]')
    expect(link.exists()).toBe(true)
  })

  it('does not render Create Post link for guests', () => {
    const wrapper = mountSidebar({ role: 'GUEST', userId: 'guest-1' })
    const link = wrapper.find('a[href="/forum/create"]')
    expect(link.exists()).toBe(false)
  })

  it('fetches and displays user SIGs when authenticated', async () => {
    mockListMySigs.mockResolvedValue([
      { id: 'sig-1', name: 'NLP Research', description: null, member_count: 5 },
      { id: 'sig-2', name: 'AI Ethics', description: null, member_count: 3 },
    ])
    const wrapper = mountSidebar({ role: 'MEMBER', userId: 'u1' })
    await flushPromises()

    expect(wrapper.text()).toContain('My SIGs')
    expect(wrapper.text()).toContain('NLP Research')
    expect(wrapper.text()).toContain('AI Ethics')

    const sigLink = wrapper.find('a[href="/sigs/sig-1"]')
    expect(sigLink.exists()).toBe(true)
  })

  it('does not show My SIGs section when user has no SIGs', async () => {
    mockListMySigs.mockResolvedValue([])
    const wrapper = mountSidebar({ role: 'MEMBER', userId: 'u1' })
    await flushPromises()

    expect(wrapper.text()).not.toContain('My SIGs')
  })

  it('handles API error gracefully', async () => {
    mockListMySigs.mockRejectedValue(new Error('Network error'))
    const wrapper = mountSidebar({ role: 'MEMBER', userId: 'u1' })
    await flushPromises()

    // Should not crash, just not show SIGs
    expect(wrapper.text()).not.toContain('My SIGs')
    expect(wrapper.text()).toContain('Quick Links')
  })

  it('does not fetch SIGs for guest users', async () => {
    const wrapper = mountSidebar({ role: 'GUEST', userId: 'guest-1' })
    await flushPromises()

    expect(mockListMySigs).not.toHaveBeenCalled()
    expect(wrapper.text()).not.toContain('My SIGs')
  })
})

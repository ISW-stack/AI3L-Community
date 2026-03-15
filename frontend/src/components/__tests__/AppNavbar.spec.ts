import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import AppNavbar from '../AppNavbar.vue'
import { useAuthStore } from '@/stores/auth'

// Mock composables/api to prevent actual axios initialization
vi.mock('@/composables/api', () => ({
  default: {
    post: vi.fn(),
    get: vi.fn(),
  },
}))

vi.mock('@/constants', () => ({
  HEARTBEAT_INTERVAL_MS: 30000,
}))

// Minimal router for testing
function createTestRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: { template: '<div />' } },
      { path: '/login', name: 'login', component: { template: '<div />' } },
      { path: '/register', name: 'register', component: { template: '<div />' } },
      { path: '/forum', component: { template: '<div />' } },
      { path: '/sigs', component: { template: '<div />' } },
      { path: '/admin', component: { template: '<div />' } },
      { path: '/admin/users', component: { template: '<div />' } },
      { path: '/admin/applications', component: { template: '<div />' } },
      { path: '/admin/reports', component: { template: '<div />' } },
      { path: '/admin/categories', component: { template: '<div />' } },
      { path: '/admin/invite-codes', component: { template: '<div />' } },
      { path: '/admin/audit-logs', component: { template: '<div />' } },
      { path: '/profile', component: { template: '<div />' } },
      { path: '/about', component: { template: '<div />' } },
    ],
  })
}

function mountNavbar() {
  const router = createTestRouter()
  const pinia = createPinia()
  setActivePinia(pinia)

  const wrapper = mount(AppNavbar, {
    global: {
      plugins: [pinia, router],
      stubs: {
        NotificationBell: true,
        BaseBadge: { template: '<span class="badge-stub"><slot /></span>' },
        // Stub lucide icons
        Menu: { template: '<span class="icon-menu" />' },
        X: { template: '<span class="icon-x" />' },
        ChevronDown: { template: '<span class="icon-chevron" />' },
        GraduationCap: { template: '<span class="icon-graduation-cap" />' },
      },
    },
  })

  return { wrapper, auth: useAuthStore() }
}

describe('AppNavbar', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  // ---------- Unauthenticated state ----------

  describe('when not authenticated', () => {
    it('should show Log In and Sign Up links', () => {
      const { wrapper } = mountNavbar()

      expect(wrapper.text()).toContain('Log In')
      expect(wrapper.text()).toContain('Sign Up')
    })

    it('should show Forum, SIGs and About links', () => {
      const { wrapper } = mountNavbar()

      expect(wrapper.text()).toContain('Forum')
      expect(wrapper.text()).toContain('SIGs')
      expect(wrapper.text()).toContain('About')
    })

    it('should not show admin links', () => {
      const { wrapper } = mountNavbar()

      expect(wrapper.text()).not.toContain('Dashboard')
      expect(wrapper.text()).not.toContain('Audit Logs')
    })

    it('should not show Log Out button', () => {
      const { wrapper } = mountNavbar()

      expect(wrapper.text()).not.toContain('Log Out')
    })
  })

  // ---------- Authenticated MEMBER ----------

  describe('when authenticated as MEMBER', () => {
    it('should show Forum and SIGs links', async () => {
      const { wrapper, auth } = mountNavbar()
      auth.setSession('MEMBER', 3600)
      await nextTick()

      expect(wrapper.text()).toContain('Forum')
      expect(wrapper.text()).toContain('SIGs')
    })

    it('should not show Log In / Sign Up links', async () => {
      const { wrapper, auth } = mountNavbar()
      auth.setSession('MEMBER', 3600)
      await nextTick()

      expect(wrapper.text()).not.toContain('Log In')
      expect(wrapper.text()).not.toContain('Sign Up')
    })

    it('should not show admin links', async () => {
      const { wrapper, auth } = mountNavbar()
      auth.setSession('MEMBER', 3600)
      await nextTick()

      expect(wrapper.text()).not.toContain('Dashboard')
      expect(wrapper.text()).not.toContain('Audit Logs')
    })

    it('should show the user dropdown with role displayed', async () => {
      const { wrapper, auth } = mountNavbar()
      auth.setSession('MEMBER', 3600)
      await nextTick()

      // The dropdown button shows the role as the display or badge text
      expect(wrapper.text()).toContain('Member')
    })

    it('shows role badge before username in the dropdown button', async () => {
      const { wrapper, auth } = mountNavbar()
      auth.setSession('MEMBER', 3600)
      auth.user = {
        id: 'u1',
        username: 'alice',
        display_name: 'AliceDisplay',
        role: 'MEMBER',
        bio: null,
        affiliation: null,
        orcid: null,
        avatar_url: null,
        preferred_language: 'en',
        is_banned: false,
        ban_reason: null,
        created_at: new Date().toISOString(),
      } as any
      await nextTick()

      const userBtn = wrapper.find('.user-dropdown-wrapper button')
      const btnText = userBtn.text()
      const roleIdx = btnText.indexOf('Member')
      const nameIdx = btnText.indexOf('AliceDisplay')
      // Role badge label should appear before the username
      expect(roleIdx).toBeGreaterThanOrEqual(0)
      expect(nameIdx).toBeGreaterThanOrEqual(0)
      expect(roleIdx).toBeLessThan(nameIdx)
    })

    it('shows fallback dash when display_name is not set', async () => {
      const { wrapper, auth } = mountNavbar()
      auth.setSession('MEMBER', 3600)
      // user is null → display_name fallback is "—"
      await nextTick()

      const userBtn = wrapper.find('.user-dropdown-wrapper button')
      expect(userBtn.text()).toContain('—')
    })
  })

  // ---------- Authenticated ADMIN ----------

  describe('when authenticated as ADMIN', () => {
    it('should show admin links (Dashboard, Users, Applications, Reports, Invite Codes)', async () => {
      const { wrapper, auth } = mountNavbar()
      auth.setSession('ADMIN', 3600)
      await nextTick()

      // Admin links are inside a dropdown — click the "Admin" button to open it
      const adminBtn = wrapper.find('.admin-dropdown-wrapper button')
      expect(adminBtn.exists()).toBe(true)
      await adminBtn.trigger('click')
      await nextTick()

      expect(wrapper.text()).toContain('Dashboard')
      expect(wrapper.text()).toContain('Users')
      expect(wrapper.text()).toContain('Applications')
      expect(wrapper.text()).toContain('Reports')
      expect(wrapper.text()).toContain('Invite Codes')
    })

    it('should NOT show Audit Logs (only SUPER_ADMIN)', async () => {
      const { wrapper, auth } = mountNavbar()
      auth.setSession('ADMIN', 3600)
      await nextTick()

      expect(wrapper.text()).not.toContain('Audit Logs')
    })

    it('should not show Log In / Sign Up', async () => {
      const { wrapper, auth } = mountNavbar()
      auth.setSession('ADMIN', 3600)
      await nextTick()

      expect(wrapper.text()).not.toContain('Log In')
      expect(wrapper.text()).not.toContain('Sign Up')
    })
  })

  // ---------- Authenticated SUPER_ADMIN ----------

  describe('when authenticated as SUPER_ADMIN', () => {
    it('should show admin links including Audit Logs', async () => {
      const { wrapper, auth } = mountNavbar()
      auth.setSession('SUPER_ADMIN', 3600)
      await nextTick()

      // Admin links are inside a dropdown — click the "Admin" button to open it
      const adminBtn = wrapper.find('.admin-dropdown-wrapper button')
      expect(adminBtn.exists()).toBe(true)
      await adminBtn.trigger('click')
      await nextTick()

      expect(wrapper.text()).toContain('Dashboard')
      expect(wrapper.text()).toContain('Users')
      expect(wrapper.text()).toContain('Applications')
      expect(wrapper.text()).toContain('Reports')
      expect(wrapper.text()).toContain('Invite Codes')
      expect(wrapper.text()).toContain('Audit Logs')
    })
  })

  // ---------- GUEST role ----------

  describe('when authenticated as GUEST', () => {
    it('should not show Profile link in dropdown', async () => {
      const { wrapper, auth } = mountNavbar()
      auth.setSession('GUEST', 3600)
      await nextTick()

      // Profile link should not appear for guests (desktop or mobile)
      const html = wrapper.html()
      // Look for hrefs to /profile — there should be none for GUEST
      expect(html).not.toContain('href="/profile"')
    })

    it('should show Log Out button when mobile menu is opened', async () => {
      const { wrapper, auth } = mountNavbar()
      auth.setSession('GUEST', 3600)
      await nextTick()

      // Open the mobile menu to reveal the Log Out button
      const hamburgerButton = wrapper.find('button[aria-label="Toggle menu"]')
      await hamburgerButton.trigger('click')
      await nextTick()

      expect(wrapper.text()).toContain('Log Out')
    })

    it('should not show admin links', async () => {
      const { wrapper, auth } = mountNavbar()
      auth.setSession('GUEST', 3600)
      await nextTick()

      expect(wrapper.text()).not.toContain('Dashboard')
      expect(wrapper.text()).not.toContain('Audit Logs')
    })
  })

  // ---------- Escape key handler ----------

  describe('escape key closes dropdowns', () => {
    it('closes user dropdown on Escape key', async () => {
      const { wrapper, auth } = mountNavbar()
      auth.setSession('MEMBER', 3600)
      await nextTick()

      // Open user dropdown
      const userBtn = wrapper.find('.user-dropdown-wrapper button')
      await userBtn.trigger('click')
      await nextTick()

      // Dropdown should be open
      expect(wrapper.find('.user-dropdown-wrapper .absolute').exists()).toBe(true)

      // Press Escape via document event
      document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
      await nextTick()

      // Dropdown should be closed
      expect(wrapper.find('.user-dropdown-wrapper .absolute').exists()).toBe(false)
    })

    it('closes admin dropdown on Escape key', async () => {
      const { wrapper, auth } = mountNavbar()
      auth.setSession('ADMIN', 3600)
      await nextTick()

      // Open admin dropdown
      const adminBtn = wrapper.find('.admin-dropdown-wrapper button')
      await adminBtn.trigger('click')
      await nextTick()

      // Dropdown should be open
      expect(wrapper.find('.admin-dropdown-wrapper .absolute').exists()).toBe(true)

      // Press Escape via document event
      document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
      await nextTick()

      // Dropdown should be closed
      expect(wrapper.find('.admin-dropdown-wrapper .absolute').exists()).toBe(false)
    })

    it('closes mobile menu on Escape key', async () => {
      const { wrapper } = mountNavbar()

      // Open mobile menu
      const hamburgerButton = wrapper.find('button[aria-label="Toggle menu"]')
      await hamburgerButton.trigger('click')
      await nextTick()

      // Mobile menu should be open
      expect(wrapper.text()).toContain('Forum')

      // Press Escape via document event
      document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
      await nextTick()

      // mobileMenuOpen should be false
      const vm = wrapper.vm as unknown as { mobileMenuOpen: boolean }
      expect(vm.mobileMenuOpen).toBe(false)
    })

    it('does not close dropdowns on non-Escape key', async () => {
      const { wrapper, auth } = mountNavbar()
      auth.setSession('MEMBER', 3600)
      await nextTick()

      // Open user dropdown
      const userBtn = wrapper.find('.user-dropdown-wrapper button')
      await userBtn.trigger('click')
      await nextTick()

      // Dropdown should be open
      expect(wrapper.find('.user-dropdown-wrapper .absolute').exists()).toBe(true)

      // Press a different key
      document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter' }))
      await nextTick()

      // Dropdown should still be open
      expect(wrapper.find('.user-dropdown-wrapper .absolute').exists()).toBe(true)
    })

    it('removes keydown listener on unmount', async () => {
      const removeEventListenerSpy = vi.spyOn(document, 'removeEventListener')
      const { wrapper } = mountNavbar()

      wrapper.unmount()

      // Should have removed the keydown listener
      const keydownRemoveCalls = removeEventListenerSpy.mock.calls.filter(
        (call) => call[0] === 'keydown',
      )
      expect(keydownRemoveCalls.length).toBeGreaterThan(0)
      removeEventListenerSpy.mockRestore()
    })
  })

  // ---------- AI3L Community brand ----------

  describe('branding', () => {
    it('should display AI3L text', () => {
      const { wrapper } = mountNavbar()
      expect(wrapper.text()).toContain('AI3L')
    })

    it('should render logo icon and AI3L text', () => {
      const { wrapper } = mountNavbar()
      // The logo area should contain an SVG icon (GraduationCap from lucide)
      const logoLink = wrapper.find('a[href="/"]')
      expect(logoLink.exists()).toBe(true)
      expect(logoLink.find('svg').exists()).toBe(true)
      // The logo text should be AI3L
      expect(logoLink.find('.text-brand-700').text()).toBe('AI3L')
    })
  })
})

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import AdminLayout from '../AdminLayout.vue'
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

function createTestRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: { template: '<div />' } },
      { path: '/admin', name: 'admin-dashboard', component: { template: '<div />' } },
      { path: '/admin/users', name: 'admin-users', component: { template: '<div />' } },
      {
        path: '/admin/applications',
        name: 'admin-applications',
        component: { template: '<div />' },
      },
      { path: '/admin/reports', name: 'admin-reports', component: { template: '<div />' } },
      { path: '/admin/categories', name: 'admin-categories', component: { template: '<div />' } },
      {
        path: '/admin/invite-codes',
        name: 'admin-invite-codes',
        component: { template: '<div />' },
      },
      { path: '/admin/audit-logs', name: 'admin-audit-logs', component: { template: '<div />' } },
    ],
  })
}

async function mountLayout(role: string) {
  const router = createTestRouter()
  const pinia = createPinia()
  setActivePinia(pinia)

  const auth = useAuthStore()
  auth.setSession(role, 3600)

  await router.push('/admin')
  await router.isReady()

  const wrapper = mount(AdminLayout, {
    global: {
      plugins: [pinia, router],
      stubs: {
        // Stub lucide icons
        LayoutDashboard: { template: '<span class="icon-layout-dashboard" />' },
        Users: { template: '<span class="icon-users" />' },
        FileCheck: { template: '<span class="icon-file-check" />' },
        Flag: { template: '<span class="icon-flag" />' },
        FolderOpen: { template: '<span class="icon-folder-open" />' },
        KeyRound: { template: '<span class="icon-key-round" />' },
        Shield: { template: '<span class="icon-shield" />' },
        Menu: { template: '<span class="icon-menu" />' },
        X: { template: '<span class="icon-x" />' },
      },
    },
  })

  return { wrapper, auth }
}

describe('AdminLayout', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  describe('sidebar navigation links', () => {
    it('should render all standard navigation links for ADMIN', async () => {
      const { wrapper } = await mountLayout('ADMIN')

      expect(wrapper.text()).toContain('Dashboard')
      expect(wrapper.text()).toContain('Users')
      expect(wrapper.text()).toContain('Applications')
      expect(wrapper.text()).toContain('Reports')
      expect(wrapper.text()).toContain('Categories')
      expect(wrapper.text()).toContain('Invite Codes')
    })

    it('should render all navigation links including Audit Logs for SUPER_ADMIN', async () => {
      const { wrapper } = await mountLayout('SUPER_ADMIN')

      expect(wrapper.text()).toContain('Dashboard')
      expect(wrapper.text()).toContain('Users')
      expect(wrapper.text()).toContain('Applications')
      expect(wrapper.text()).toContain('Reports')
      expect(wrapper.text()).toContain('Categories')
      expect(wrapper.text()).toContain('Invite Codes')
      expect(wrapper.text()).toContain('Audit Logs')
    })

    it('should show Administration header', async () => {
      const { wrapper } = await mountLayout('ADMIN')

      expect(wrapper.text()).toContain('Administration')
    })
  })

  describe('Audit Logs visibility', () => {
    it('should hide Audit Logs link when user is ADMIN (not SUPER_ADMIN)', async () => {
      const { wrapper } = await mountLayout('ADMIN')

      // Find all sidebar links in the desktop sidebar
      const desktopSidebar = wrapper.find('aside')
      const links = desktopSidebar.findAll('a')
      const auditLogsLink = links.filter((link) => link.text().includes('Audit Logs'))

      expect(auditLogsLink.length).toBe(0)
    })

    it('should show Audit Logs link when user is SUPER_ADMIN', async () => {
      const { wrapper } = await mountLayout('SUPER_ADMIN')

      // Find all sidebar links in the desktop sidebar
      const desktopSidebar = wrapper.find('aside')
      const links = desktopSidebar.findAll('a')
      const auditLogsLink = links.filter((link) => link.text().includes('Audit Logs'))

      expect(auditLogsLink.length).toBeGreaterThan(0)
    })
  })

  describe('mobile toggle', () => {
    it('should have a mobile toggle button', async () => {
      const { wrapper } = await mountLayout('ADMIN')

      const toggleBtn = wrapper.find('button[aria-label="Toggle admin sidebar"]')
      expect(toggleBtn.exists()).toBe(true)
    })

    it('should show mobile sidebar when toggle is clicked', async () => {
      const { wrapper } = await mountLayout('ADMIN')

      // Initially, mobile sidebar should not be visible (only desktop aside is rendered)
      const mobileSidebars = wrapper.findAll('aside')
      expect(mobileSidebars.length).toBe(1) // Only desktop sidebar

      const toggleBtn = wrapper.find('button[aria-label="Toggle admin sidebar"]')
      await toggleBtn.trigger('click')
      await nextTick()

      // After click, mobile sidebar should appear
      const allSidebars = wrapper.findAll('aside')
      expect(allSidebars.length).toBe(2) // Desktop + mobile
    })
  })

  describe('router-view slot', () => {
    it('should render router-view for child content', async () => {
      const { wrapper } = await mountLayout('ADMIN')

      // The component should contain a router-view output area
      expect(wrapper.find('.flex-1.min-w-0').exists()).toBe(true)
    })
  })
})

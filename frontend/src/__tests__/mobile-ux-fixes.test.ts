import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { nextTick } from 'vue'
import { createRouter, createMemoryHistory } from 'vue-router'
import { readFileSync } from 'fs'
import { resolve } from 'path'

// --------------- Mocks ---------------

vi.mock('@/composables/api', () => ({
  default: {
    post: vi.fn(),
    get: vi.fn(),
  },
}))

vi.mock('@/constants', () => ({
  HEARTBEAT_INTERVAL_MS: 30000,
}))

// --------------- Issue #8: Admin sidebar mobile width ---------------

import AdminLayout from '@/components/AdminLayout.vue'
import { useAuthStore } from '@/stores/auth'

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
        LayoutDashboard: { template: '<span class="icon-layout-dashboard" />' },
        Users: { template: '<span class="icon-users" />' },
        FileCheck: { template: '<span class="icon-file-check" />' },
        Flag: { template: '<span class="icon-flag" />' },
        FolderOpen: { template: '<span class="icon-folder-open" />' },
        KeyRound: { template: '<span class="icon-key-round" />' },
        Shield: { template: '<span class="icon-shield" />' },
        Menu: { template: '<span class="icon-menu" />' },
        X: { template: '<span class="icon-x" />' },
        Ban: { template: '<span class="icon-ban" />' },
        Users2: { template: '<span class="icon-users2" />' },
      },
    },
  })

  return { wrapper, auth }
}

describe('Issue #8: Admin sidebar mobile width', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('mobile sidebar uses w-[80vw] max-w-[300px] for better mobile experience', async () => {
    const { wrapper } = await mountLayout('ADMIN')

    const toggleBtn = wrapper.find('button[aria-label="Toggle admin sidebar"]')
    await toggleBtn.trigger('click')
    await nextTick()

    const allSidebars = wrapper.findAll('aside')
    const mobileSidebar = allSidebars[1]
    expect(mobileSidebar.classes()).toContain('w-[80vw]')
    expect(mobileSidebar.classes()).toContain('max-w-[300px]')
  })

  it('mobile sidebar links have increased padding for touch (py-3)', async () => {
    const { wrapper } = await mountLayout('ADMIN')

    const toggleBtn = wrapper.find('button[aria-label="Toggle admin sidebar"]')
    await toggleBtn.trigger('click')
    await nextTick()

    const allSidebars = wrapper.findAll('aside')
    const mobileSidebar = allSidebars[1]
    const links = mobileSidebar.findAll('a')
    expect(links.length).toBeGreaterThan(0)
    expect(links[0].classes()).toContain('py-3')
    expect(links[0].classes()).toContain('touch-manipulation')
  })

  it('mobile toggle button has touch-friendly padding and active state', async () => {
    const { wrapper } = await mountLayout('ADMIN')

    const toggleBtn = wrapper.find('button[aria-label="Toggle admin sidebar"]')
    expect(toggleBtn.classes()).toContain('p-1')
    expect(toggleBtn.classes()).toContain('touch-manipulation')
  })
})

// --------------- Issue #3: BaseButton touch targets ---------------

import BaseButton from '@/components/base/BaseButton.vue'

describe('Issue #3: BaseButton mobile touch targets', () => {
  it('md size has min-h-[44px] for mobile touch target', () => {
    const wrapper = mount(BaseButton, {
      slots: { default: 'Click' },
    })
    expect(wrapper.classes()).toContain('min-h-[44px]')
    expect(wrapper.classes()).toContain('sm:min-h-0')
  })

  it('sm size has min-h-[36px] for mobile touch target', () => {
    const wrapper = mount(BaseButton, {
      props: { size: 'sm' },
      slots: { default: 'Click' },
    })
    expect(wrapper.classes()).toContain('min-h-[36px]')
  })

  it('lg size has min-h-[44px] for mobile touch target', () => {
    const wrapper = mount(BaseButton, {
      props: { size: 'lg' },
      slots: { default: 'Click' },
    })
    expect(wrapper.classes()).toContain('min-h-[44px]')
  })

  it('full size has min-h-[44px] for mobile touch target', () => {
    const wrapper = mount(BaseButton, {
      props: { size: 'full' },
      slots: { default: 'Click' },
    })
    expect(wrapper.classes()).toContain('min-h-[44px]')
  })

  it('has touch-manipulation class for better touch response', () => {
    const wrapper = mount(BaseButton, {
      slots: { default: 'Click' },
    })
    expect(wrapper.classes()).toContain('touch-manipulation')
  })
})

// --------------- Issue #9: TipTap table mobile overflow ---------------

describe('Issue #9: TipTap table mobile overflow', () => {
  it('style.css has responsive min-width for table cells', () => {
    const cssContent = readFileSync(resolve(__dirname, '../style.css'), 'utf-8')

    // Should have reduced min-width for mobile
    expect(cssContent).toContain('min-width: 50px')
    // Should have responsive breakpoint for larger min-width
    expect(cssContent).toContain('@media (min-width: 640px)')
    expect(cssContent).toContain('min-width: 80px')
  })

  it('style.css has overflow-x: auto on table wrapper', () => {
    const cssContent = readFileSync(resolve(__dirname, '../style.css'), 'utf-8')
    expect(cssContent).toContain('.tiptap .tableWrapper')
    expect(cssContent).toContain('overflow-x: auto')
  })
})

// --------------- Issue #11: Safe area insets ---------------

describe('Issue #11: Safe area insets', () => {
  it('index.html has viewport-fit=cover meta tag', () => {
    const htmlContent = readFileSync(resolve(__dirname, '../../index.html'), 'utf-8')
    expect(htmlContent).toContain('viewport-fit=cover')
  })

  it('style.css has safe area padding for body', () => {
    const cssContent = readFileSync(resolve(__dirname, '../style.css'), 'utf-8')
    expect(cssContent).toContain('safe-area-inset-left')
    expect(cssContent).toContain('safe-area-inset-right')
  })
})

// --------------- Issue #10: FormBuilder mobile experience ---------------

describe('Issue #10: QuestionEditor mobile enhancements', () => {
  // QuestionEditor has many dependencies, so we test via CSS class assertions
  // by reading the source file
  it('QuestionEditor has responsive padding (p-4 sm:p-5)', () => {
    const src = readFileSync(
      resolve(__dirname, '../components/forms/QuestionEditor.vue'),
      'utf-8',
    )
    expect(src).toContain('p-4 sm:p-5')
  })

  it('drag handle has touch-manipulation class', () => {
    const src = readFileSync(
      resolve(__dirname, '../components/forms/QuestionEditor.vue'),
      'utf-8',
    )
    expect(src).toContain('touch-manipulation')
  })

  it('action buttons have responsive padding (px-1.5 py-1 sm:px-1 sm:py-0)', () => {
    const src = readFileSync(
      resolve(__dirname, '../components/forms/QuestionEditor.vue'),
      'utf-8',
    )
    expect(src).toContain('px-1.5 py-1 sm:px-1 sm:py-0')
  })

  it('form fields have responsive text size (text-base sm:text-sm)', () => {
    const src = readFileSync(
      resolve(__dirname, '../components/forms/QuestionEditor.vue'),
      'utf-8',
    )
    expect(src).toContain('text-base sm:text-sm')
  })

  it('insert-question button is semi-visible on mobile (opacity-40)', () => {
    const src = readFileSync(
      resolve(__dirname, '../components/forms/QuestionEditor.vue'),
      'utf-8',
    )
    expect(src).toContain('opacity-40 sm:opacity-0')
  })

  it('insert-question button has larger touch target on mobile (w-8 h-8)', () => {
    const src = readFileSync(
      resolve(__dirname, '../components/forms/QuestionEditor.vue'),
      'utf-8',
    )
    expect(src).toContain('w-8 h-8 sm:w-6 sm:h-6')
  })
})

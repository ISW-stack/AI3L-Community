import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import FloatingCreateButton from '../FloatingCreateButton.vue'

vi.mock('@/constants', () => ({
  HEARTBEAT_INTERVAL_MS: 30000,
}))

vi.mock('@/composables/api', () => ({
  default: { get: vi.fn(), post: vi.fn() },
}))

vi.mock('lucide-vue-next', () => ({
  PenLine: { name: 'PenLine', template: '<svg data-testid="pen-icon" />' },
}))

function createTestRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: { template: '<div />' } },
      { path: '/forum/create', component: { template: '<div />' } },
    ],
  })
}

function mountFab(to = '/forum/create', authState?: { role: string | null; expiresAt: number }) {
  const pinia = createPinia()
  setActivePinia(pinia)
  const router = createTestRouter()

  if (authState) {
    localStorage.setItem('role', authState.role || '')
    localStorage.setItem('expiresAt', String(authState.expiresAt))
  }

  return mount(FloatingCreateButton, {
    props: { to },
    global: {
      plugins: [pinia, router],
    },
  })
}

describe('FloatingCreateButton', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('renders when user is authenticated and not a guest', () => {
    const wrapper = mountFab('/forum/create', {
      role: 'MEMBER',
      expiresAt: Date.now() + 60000,
    })
    expect(wrapper.find('.fab').exists()).toBe(true)
    expect(wrapper.find('[data-testid="pen-icon"]').exists()).toBe(true)
  })

  it('does not render when user is not authenticated', () => {
    const wrapper = mountFab('/forum/create')
    expect(wrapper.find('.fab').exists()).toBe(false)
  })

  it('does not render when user is a guest', () => {
    const wrapper = mountFab('/forum/create', {
      role: 'GUEST',
      expiresAt: Date.now() + 60000,
    })
    expect(wrapper.find('.fab').exists()).toBe(false)
  })

  it('links to the provided "to" prop', () => {
    const wrapper = mountFab('/forum/create?sig_id=123', {
      role: 'MEMBER',
      expiresAt: Date.now() + 60000,
    })
    const link = wrapper.find('a')
    expect(link.exists()).toBe(true)
    expect(link.attributes('href')).toContain('/forum/create')
  })

  it('contains the new post label text', () => {
    const wrapper = mountFab('/forum/create', {
      role: 'ADMIN',
      expiresAt: Date.now() + 60000,
    })
    expect(wrapper.find('.fab-label').exists()).toBe(true)
  })
})

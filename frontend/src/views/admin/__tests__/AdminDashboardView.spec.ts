import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import AdminDashboardView from '../AdminDashboardView.vue'

const mockGetDashboard = vi.fn()

vi.mock('@/api/admin', () => ({
  getDashboard: (...args: unknown[]) => mockGetDashboard(...args),
}))

vi.mock('@/composables/api', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
  },
}))

const fakeStats = {
  users: 42,
  posts: 128,
  sigs: 7,
  forms: 15,
  pending_reports: 3,
  pending_applications: 5,
}

function createTestRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/admin', component: AdminDashboardView },
      { path: '/admin/users', component: { template: '<div />' } },
      { path: '/admin/applications', component: { template: '<div />' } },
      { path: '/admin/reports', component: { template: '<div />' } },
    ],
  })
}

async function mountDashboard() {
  const pinia = createPinia()
  setActivePinia(pinia)
  const router = createTestRouter()
  await router.push('/admin')
  await router.isReady()

  const wrapper = mount(AdminDashboardView, {
    global: {
      plugins: [pinia, router],
      stubs: {
        BaseCard: { template: '<div class="base-card"><slot /></div>' },
        BaseButton: {
          template: '<button @click="$emit(\'click\')"><slot /></button>',
          props: ['variant', 'size'],
        },
        SkeletonLoader: { template: '<div class="skeleton-loader" />' },
        EmptyState: {
          template: '<div class="empty-state">{{ message }}</div>',
          props: ['message'],
        },
      },
    },
  })
  await flushPromises()
  return wrapper
}

describe('AdminDashboardView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockGetDashboard.mockResolvedValue(fakeStats)
  })

  it('renders the dashboard title', async () => {
    const wrapper = await mountDashboard()
    expect(wrapper.find('h1').exists()).toBe(true)
  })

  it('fetches dashboard stats on mount', async () => {
    await mountDashboard()
    expect(mockGetDashboard).toHaveBeenCalledOnce()
  })

  it('displays stat values after loading', async () => {
    const wrapper = await mountDashboard()
    expect(wrapper.text()).toContain('42')
    expect(wrapper.text()).toContain('128')
    expect(wrapper.text()).toContain('7')
    expect(wrapper.text()).toContain('15')
    expect(wrapper.text()).toContain('3')
    expect(wrapper.text()).toContain('5')
  })

  it('shows loading skeleton while fetching', async () => {
    mockGetDashboard.mockReturnValue(new Promise(() => {}))
    const pinia = createPinia()
    setActivePinia(pinia)
    const router = createTestRouter()

    const wrapper = mount(AdminDashboardView, {
      global: {
        plugins: [pinia, router],
        stubs: {
          BaseCard: { template: '<div class="base-card"><slot /></div>' },
          BaseButton: { template: '<button><slot /></button>' },
          SkeletonLoader: { template: '<div class="skeleton-loader" />' },
          EmptyState: { template: '<div class="empty-state" />' },
        },
      },
    })
    await nextTick()
    expect(wrapper.find('.skeleton-loader').exists()).toBe(true)
  })

  it('shows empty state when stats fetch fails', async () => {
    mockGetDashboard.mockRejectedValue(new Error('Network error'))
    const wrapper = await mountDashboard()
    expect(wrapper.find('.empty-state').exists()).toBe(true)
  })

  it('renders quick action router-links to admin sub-pages', async () => {
    const wrapper = await mountDashboard()
    const links = wrapper.findAll('a')
    const hrefs = links.map((l) => l.attributes('href'))
    expect(hrefs).toContain('/admin/users')
    expect(hrefs).toContain('/admin/applications')
    expect(hrefs).toContain('/admin/reports')
  })

  it('renders six stat cards plus quick actions card', async () => {
    const wrapper = await mountDashboard()
    const cards = wrapper.findAll('.base-card')
    expect(cards.length).toBe(7)
  })

  it('does not show skeleton after loading completes', async () => {
    const wrapper = await mountDashboard()
    expect(wrapper.find('.skeleton-loader').exists()).toBe(false)
  })
})

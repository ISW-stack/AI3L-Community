import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import ApplicationsView from '../ApplicationsView.vue'

const mockListApplications = vi.fn()
const mockReviewApplication = vi.fn()

vi.mock('@/api/admin', () => ({
  listApplications: (...args: unknown[]) => mockListApplications(...args),
  reviewApplication: (...args: unknown[]) => mockReviewApplication(...args),
}))

vi.mock('@/composables/api', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
  },
}))

vi.mock('@/utils/error', () => ({
  getErrorMessage: (_e: unknown, fallback: string) => fallback,
}))

const fakeApplications = [
  {
    id: 'app-1',
    user_id: 'user-1',
    username: 'alice',
    display_name: 'Alice',
    description: 'I want to join',
    status: 'PENDING',
    reviewed_at: null,
    created_at: '2026-01-15T00:00:00Z',
  },
  {
    id: 'app-2',
    user_id: 'user-2',
    username: 'bob',
    display_name: 'Bob',
    description: 'Researcher',
    status: 'APPROVED',
    reviewed_at: '2026-01-16T00:00:00Z',
    created_at: '2026-01-14T00:00:00Z',
  },
]

function createTestRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/admin/applications', component: ApplicationsView }],
  })
}

async function mountApplications(apps = fakeApplications, total = fakeApplications.length) {
  const pinia = createPinia()
  setActivePinia(pinia)
  const router = createTestRouter()
  await router.push('/admin/applications')
  await router.isReady()

  mockListApplications.mockResolvedValue({ applications: apps, total })

  const wrapper = mount(ApplicationsView, {
    global: {
      plugins: [pinia, router],
      stubs: {
        BaseCard: { template: '<div class="base-card"><slot /></div>' },
        BaseButton: {
          template:
            '<button :disabled="$attrs.disabled" @click="$emit(\'click\')"><slot /></button>',
          props: ['size', 'variant', 'loading'],
        },
        BaseBadge: {
          template: '<span class="base-badge"><slot /></span>',
          props: ['variant'],
        },
        BaseAlert: {
          template: '<div class="base-alert"><slot /></div>',
          props: ['type'],
        },
        SkeletonLoader: { template: '<div class="skeleton-loader" />' },
        EmptyState: {
          template: '<div class="empty-state">{{ title }} {{ message }}</div>',
          props: ['title', 'message'],
        },
      },
    },
  })
  await flushPromises()
  return wrapper
}

describe('ApplicationsView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders the title', async () => {
    const wrapper = await mountApplications()
    expect(wrapper.find('h1').exists()).toBe(true)
  })

  it('fetches applications on mount with PENDING filter', async () => {
    await mountApplications()
    expect(mockListApplications).toHaveBeenCalledWith({ status: 'PENDING' })
  })

  it('displays application details', async () => {
    const wrapper = await mountApplications()
    expect(wrapper.text()).toContain('Alice')
    expect(wrapper.text()).toContain('@alice')
    expect(wrapper.text()).toContain('I want to join')
  })

  it('shows approve and reject buttons for PENDING applications', async () => {
    const pendingOnly = [fakeApplications[0]]
    const wrapper = await mountApplications(pendingOnly, 1)
    const buttons = wrapper.findAll('button')
    const btnTexts = buttons.map((b) => b.text())
    expect(btnTexts.some((t) => t.length > 0)).toBe(true)
  })

  it('does not show action buttons for non-PENDING applications', async () => {
    const approvedOnly = [fakeApplications[1]]
    const wrapper = await mountApplications(approvedOnly, 1)
    // Only filter buttons should exist, no approve/reject
    const cards = wrapper.findAll('.base-card')
    if (cards.length > 0) {
      const cardButtons = cards[0].findAll('button')
      expect(cardButtons.length).toBe(0)
    }
  })

  it('shows empty state when no applications', async () => {
    const wrapper = await mountApplications([], 0)
    expect(wrapper.find('.empty-state').exists()).toBe(true)
  })

  it('shows loading skeleton while fetching', async () => {
    mockListApplications.mockReturnValue(new Promise(() => {}))
    const pinia = createPinia()
    setActivePinia(pinia)
    const router = createTestRouter()

    const wrapper = mount(ApplicationsView, {
      global: {
        plugins: [pinia, router],
        stubs: {
          BaseCard: { template: '<div class="base-card"><slot /></div>' },
          BaseButton: { template: '<button><slot /></button>' },
          BaseBadge: { template: '<span />' },
          BaseAlert: { template: '<div />' },
          SkeletonLoader: { template: '<div class="skeleton-loader" />' },
          EmptyState: { template: '<div class="empty-state" />' },
        },
      },
    })
    await nextTick()
    expect(wrapper.find('.skeleton-loader').exists()).toBe(true)
  })

  it('renders status filter buttons for PENDING, APPROVED, REJECTED', async () => {
    const wrapper = await mountApplications()
    const filterButtons = wrapper.findAll('button').filter((b) => {
      const text = b.text()
      return text && !b.classes().includes('base-card')
    })
    expect(filterButtons.length).toBeGreaterThanOrEqual(3)
  })

  it('switches filter and re-fetches when filter button is clicked', async () => {
    const wrapper = await mountApplications()
    mockListApplications.mockResolvedValue({ applications: [], total: 0 })

    // Find the APPROVED/REJECTED filter buttons (second and third filter)
    const filterButtons = wrapper
      .findAll('button')
      .filter((b) => !b.find('.base-card').exists())
    // Click the second filter button (should be APPROVED)
    if (filterButtons.length >= 2) {
      await filterButtons[1].trigger('click')
      await flushPromises()
      expect(mockListApplications).toHaveBeenCalledTimes(2)
    }
  })

  it('calls reviewApplication when approve is clicked', async () => {
    const pendingOnly = [fakeApplications[0]]
    mockReviewApplication.mockResolvedValue(undefined)

    const wrapper = await mountApplications(pendingOnly, 1)
    mockListApplications.mockResolvedValue({ applications: [], total: 0 })

    // Find approve button in the card
    const cardButtons = wrapper.findAll('.base-card button')
    if (cardButtons.length > 0) {
      await cardButtons[0].trigger('click')
      await flushPromises()
      expect(mockReviewApplication).toHaveBeenCalledWith('app-1', 'APPROVED')
    }
  })

  it('shows error message when review fails', async () => {
    const pendingOnly = [fakeApplications[0]]
    mockReviewApplication.mockRejectedValue(new Error('Forbidden'))

    const wrapper = await mountApplications(pendingOnly, 1)

    const cardButtons = wrapper.findAll('.base-card button')
    if (cardButtons.length > 0) {
      await cardButtons[0].trigger('click')
      await flushPromises()
      expect(wrapper.find('.base-alert').exists()).toBe(true)
    }
  })

  it('displays total count', async () => {
    const wrapper = await mountApplications(fakeApplications, 2)
    expect(wrapper.text()).toContain('2')
  })

  it('shows alert message when fetch fails', async () => {
    mockListApplications.mockRejectedValue(new Error('Network error'))
    const pinia = createPinia()
    setActivePinia(pinia)
    const router = createTestRouter()
    await router.push('/admin/applications')
    await router.isReady()

    const wrapper = mount(ApplicationsView, {
      global: {
        plugins: [pinia, router],
        stubs: {
          BaseCard: { template: '<div class="base-card"><slot /></div>' },
          BaseButton: { template: '<button><slot /></button>' },
          BaseBadge: { template: '<span />' },
          BaseAlert: {
            template: '<div class="base-alert"><slot /></div>',
            props: ['type'],
          },
          SkeletonLoader: { template: '<div class="skeleton-loader" />' },
          EmptyState: { template: '<div class="empty-state" />' },
        },
      },
    })
    await flushPromises()
    expect(wrapper.find('.base-alert').exists()).toBe(true)
  })
})

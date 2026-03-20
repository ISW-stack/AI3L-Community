import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import MembersView from '../about/MembersView.vue'

// ── Mock API module ────────────────────────────────────────────────────
const mockGetMembers = vi.fn()

vi.mock('@/api/about', () => ({
  getMembers: (...a: unknown[]) => mockGetMembers(...a),
  getOrgChart: vi.fn(),
  updateOverride: vi.fn(),
  updateSigDescription: vi.fn(),
  updateMemberBio: vi.fn(),
}))

// ── Fixture data ───────────────────────────────────────────────────────
const fakeMembers = [
  {
    id: 'u1',
    username: 'alice',
    display_name: 'Alice',
    avatar_url: null,
    role: 'MEMBER',
    affiliation: 'NTNU',
    bio: 'AI researcher',
  },
  {
    id: 'u2',
    username: 'bob',
    display_name: 'Bob',
    avatar_url: null,
    role: 'ADMIN',
    affiliation: null,
    bio: null,
  },
]

function createTestRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/about/members', component: MembersView },
      { path: '/users/:id', component: { template: '<div />' } },
    ],
  })
}

function mountView() {
  const pinia = createPinia()
  setActivePinia(pinia)
  const router = createTestRouter()
  return mount(MembersView, {
    global: {
      plugins: [pinia, router],
      stubs: {
        SkeletonLoader: { template: '<div class="skeleton-loader" />' },
        BaseBadge: { template: '<span class="badge"><slot /></span>', props: ['variant', 'size'] },
      },
    },
  })
}

describe('MembersView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockGetMembers.mockResolvedValue({ members: fakeMembers, total: 2 })
  })

  it('shows skeleton while loading', () => {
    mockGetMembers.mockReturnValue(new Promise(() => {}))
    const wrapper = mountView()
    expect(wrapper.find('.skeleton-loader').exists()).toBe(true)
  })

  it('renders member cards after load', async () => {
    const wrapper = mountView()
    await flushPromises()
    expect(wrapper.text()).toContain('Alice')
    expect(wrapper.text()).toContain('Bob')
  })

  it('shows member affiliation', async () => {
    const wrapper = mountView()
    await flushPromises()
    expect(wrapper.text()).toContain('NTNU')
  })

  it('shows member bio', async () => {
    const wrapper = mountView()
    await flushPromises()
    expect(wrapper.text()).toContain('AI researcher')
  })

  it('shows empty state when no members', async () => {
    mockGetMembers.mockResolvedValue({ members: [], total: 0 })
    const wrapper = mountView()
    await flushPromises()
    expect(wrapper.text()).toContain('No results found')
  })

  it('renders page heading', async () => {
    const wrapper = mountView()
    await flushPromises()
    expect(wrapper.text()).toContain('Community Members')
  })

  it('shows search input', async () => {
    const wrapper = mountView()
    await flushPromises()
    expect(wrapper.find('input[type="text"]').exists()).toBe(true)
  })

  it('calls getMembers on mount with default params', async () => {
    mountView()
    await flushPromises()
    expect(mockGetMembers).toHaveBeenCalledWith({
      page: 1,
      page_size: 24,
      search: undefined,
    })
  })

  it('does not show pagination when only 1 page', async () => {
    const wrapper = mountView()
    await flushPromises()
    // total=2, pageSize=24 → 1 page → no prev/next buttons
    const buttons = wrapper.findAll('button')
    const prevBtn = buttons.filter((b) => b.text() === 'Prev')
    expect(prevBtn.length).toBe(0)
  })

  it('shows pagination when total > page_size', async () => {
    mockGetMembers.mockResolvedValue({ members: fakeMembers, total: 50 })
    const wrapper = mountView()
    await flushPromises()
    // total=50, pageSize=24 → 3 pages → pagination shown
    const buttons = wrapper.findAll('button')
    const prevBtn = buttons.filter((b) => b.text() === 'Prev')
    expect(prevBtn.length).toBe(1)
  })

  it('shows error message on API failure', async () => {
    mockGetMembers.mockRejectedValue(new Error('Network error'))
    const wrapper = mountView()
    await flushPromises()
    expect(wrapper.text()).toContain('An unexpected error occurred')
  })

  it('member cards are clickable (cursor-pointer)', async () => {
    const wrapper = mountView()
    await flushPromises()
    // Cards have cursor-pointer class
    const cards = wrapper.findAll('.cursor-pointer')
    expect(cards.length).toBe(2)
  })
})

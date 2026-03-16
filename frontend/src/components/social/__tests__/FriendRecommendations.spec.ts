import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import FriendRecommendations from '../FriendRecommendations.vue'
import { useAuthStore } from '@/stores/auth'

const mockGetRecommendations = vi.fn()
const mockDismissRecommendation = vi.fn()
const mockSendFriendRequest = vi.fn()

vi.mock('@/api/recommendations', () => ({
  getRecommendations: (...args: unknown[]) => mockGetRecommendations(...args),
  dismissRecommendation: (...args: unknown[]) => mockDismissRecommendation(...args),
}))

vi.mock('@/api/social', () => ({
  sendFriendRequest: (...args: unknown[]) => mockSendFriendRequest(...args),
  getRelationshipStatus: vi.fn(),
  listFriends: vi.fn(),
  listFriendRequests: vi.fn(),
  listFollowing: vi.fn(),
  listFollowers: vi.fn(),
  listBlocks: vi.fn(),
  followUser: vi.fn(),
  unfollowUser: vi.fn(),
  blockUser: vi.fn(),
  unblockUser: vi.fn(),
  unfriend: vi.fn(),
  acceptFriendRequest: vi.fn(),
  rejectFriendRequest: vi.fn(),
}))

vi.mock('@/composables/api', () => ({
  default: { get: vi.fn(), post: vi.fn(), put: vi.fn(), delete: vi.fn() },
}))

vi.mock('@/constants', () => ({
  HEARTBEAT_INTERVAL_MS: 30000,
}))

const fakeRecommendations = [
  {
    id: 'rec1',
    user_id: 'u1',
    display_name: 'Alice',
    username: 'alice',
    avatar_url: null,
    affiliation: 'MIT',
    score: 0.95,
    reasons: [{ type: 'common_sig' as const, count: 3 }],
    created_at: '2026-01-01T00:00:00Z',
  },
  {
    id: 'rec2',
    user_id: 'u2',
    display_name: 'Bob',
    username: 'bob',
    avatar_url: 'http://example.com/bob.png',
    affiliation: 'Stanford',
    score: 0.85,
    reasons: [
      { type: 'mutual_friends' as const, count: 2 },
      { type: 'same_affiliation' as const, affiliation: 'Stanford' },
    ],
    created_at: '2026-01-02T00:00:00Z',
  },
  {
    id: 'rec3',
    user_id: 'u3',
    display_name: 'Charlie',
    username: 'charlie',
    avatar_url: null,
    affiliation: null,
    score: 0.75,
    reasons: [{ type: 'similar_keywords' as const }],
    created_at: '2026-01-03T00:00:00Z',
  },
]

function createTestRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: { template: '<div />' } },
      { path: '/users/:id', component: { template: '<div />' } },
    ],
  })
}

function createStubs() {
  return {
    BaseAvatar: {
      template: '<div class="base-avatar" />',
      props: ['src', 'name', 'size'],
    },
    BaseButton: {
      template: '<button @click="$emit(\'click\')"><slot /></button>',
      props: ['loading', 'variant', 'size', 'disabled'],
    },
    BaseCard: {
      template: '<div class="base-card"><slot /></div>',
      props: ['padding', 'hoverable'],
    },
    ChevronDown: { template: '<span class="icon-chevron-down" />' },
    ChevronUp: { template: '<span class="icon-chevron-up" />' },
    UserPlus: { template: '<span class="icon-user-plus" />' },
    X: { template: '<span class="icon-x" />' },
    Users: { template: '<span class="icon-users" />' },
  }
}

async function mountRecommendations(authenticated = true, isGuest = false) {
  const pinia = createPinia()
  setActivePinia(pinia)
  const router = createTestRouter()

  // Set up auth store
  const auth = useAuthStore()
  if (authenticated) {
    auth.setSession(isGuest ? 'GUEST' : 'MEMBER', 3600)
  }

  await router.push('/')
  await router.isReady()

  const wrapper = mount(FriendRecommendations, {
    global: { plugins: [pinia, router], stubs: createStubs() },
  })
  await flushPromises()
  return { wrapper, auth }
}

describe('FriendRecommendations', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockGetRecommendations.mockResolvedValue({
      recommendations: fakeRecommendations.map((r) => ({ ...r })),
    })
    mockDismissRecommendation.mockResolvedValue({})
    mockSendFriendRequest.mockResolvedValue({})
  })

  it('renders the widget title', async () => {
    const { wrapper } = await mountRecommendations()
    expect(wrapper.text()).toContain('People You May Know')
  })

  it('fetches recommendations on mount for authenticated non-guest users', async () => {
    await mountRecommendations()
    expect(mockGetRecommendations).toHaveBeenCalled()
  })

  it('does not fetch recommendations for guest users', async () => {
    await mountRecommendations(true, true)
    expect(mockGetRecommendations).not.toHaveBeenCalled()
  })

  it('does not render for unauthenticated users', async () => {
    const { wrapper } = await mountRecommendations(false)
    expect(wrapper.find('[data-testid="friend-recommendations"]').exists()).toBe(false)
  })

  it('renders recommendation names', async () => {
    const { wrapper } = await mountRecommendations()
    expect(wrapper.text()).toContain('Alice')
    expect(wrapper.text()).toContain('Bob')
    expect(wrapper.text()).toContain('Charlie')
  })

  it('renders affiliation when present', async () => {
    const { wrapper } = await mountRecommendations()
    expect(wrapper.text()).toContain('MIT')
    expect(wrapper.text()).toContain('Stanford')
  })

  it('renders formatted reason for common_sig', async () => {
    const { wrapper } = await mountRecommendations()
    expect(wrapper.text()).toContain('3 shared SIGs')
  })

  it('renders formatted reason for mutual_friends', async () => {
    const { wrapper } = await mountRecommendations()
    expect(wrapper.text()).toContain('2 mutual friends')
  })

  it('renders formatted reason for similar_keywords', async () => {
    const { wrapper } = await mountRecommendations()
    expect(wrapper.text()).toContain('Similar interests')
  })

  it('sends friend request when add button clicked', async () => {
    const { wrapper } = await mountRecommendations()
    const addButtons = wrapper.findAll('button[title="Add Friend"]')
    expect(addButtons.length).toBe(3)
    await addButtons[0].trigger('click')
    await flushPromises()
    expect(mockSendFriendRequest).toHaveBeenCalledWith('u1')
  })

  it('removes recommendation from list after successful friend request', async () => {
    const { wrapper } = await mountRecommendations()
    expect(wrapper.text()).toContain('Alice')

    const addButtons = wrapper.findAll('button[title="Add Friend"]')
    await addButtons[0].trigger('click')
    await flushPromises()

    expect(wrapper.text()).not.toContain('Alice')
  })

  it('dismisses recommendation optimistically', async () => {
    const { wrapper } = await mountRecommendations()
    expect(wrapper.text()).toContain('Bob')

    const dismissButtons = wrapper.findAll('button[title="Dismiss"]')
    await dismissButtons[1].trigger('click')
    await flushPromises()

    expect(mockDismissRecommendation).toHaveBeenCalledWith('u2')
    expect(wrapper.text()).not.toContain('Bob')
  })

  it('rolls back dismissed recommendation on API error', async () => {
    mockDismissRecommendation.mockRejectedValue(new Error('Network error'))
    const { wrapper } = await mountRecommendations()

    const dismissButtons = wrapper.findAll('button[title="Dismiss"]')
    await dismissButtons[0].trigger('click')
    await flushPromises()

    // Should be rolled back
    expect(wrapper.text()).toContain('Alice')
  })

  it('shows empty state when no recommendations', async () => {
    mockGetRecommendations.mockResolvedValue({
      recommendations: [],
    })
    const { wrapper } = await mountRecommendations()
    expect(wrapper.text()).toContain('No recommendations right now')
  })

  it('can collapse and expand the widget', async () => {
    const { wrapper } = await mountRecommendations()
    expect(wrapper.text()).toContain('Alice')

    // Click the header to collapse
    const headerButton = wrapper
      .findAll('button')
      .find((b) => b.text().includes('People You May Know'))
    await headerButton!.trigger('click')
    await flushPromises()

    // Items should not be visible when collapsed
    const items = wrapper.findAll('[data-testid="recommendation-item"]')
    expect(items.length).toBe(0)
  })

  it('shows loading state while fetching', async () => {
    mockGetRecommendations.mockReturnValue(new Promise(() => {}))
    const { wrapper } = await mountRecommendations()
    expect(wrapper.findAll('.animate-pulse').length).toBeGreaterThan(0)
  })

  it('limits to 10 recommendations', async () => {
    const manyRecs = Array.from({ length: 15 }, (_, i) => ({
      id: `rec${i}`,
      user_id: `u${i}`,
      display_name: `User${i}`,
      username: `user${i}`,
      avatar_url: null,
      affiliation: null,
      score: 1 - i * 0.05,
      reasons: [{ type: 'activity_recency' as const }],
      created_at: '2026-01-01T00:00:00Z',
    }))
    mockGetRecommendations.mockResolvedValue({
      recommendations: manyRecs,
    })
    const { wrapper } = await mountRecommendations()
    const items = wrapper.findAll('[data-testid="recommendation-item"]')
    expect(items.length).toBe(10)
  })
})

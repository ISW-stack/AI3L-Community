import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import FriendsView from '../FriendsView.vue'

const mockListFriends = vi.fn()
const mockListFriendRequests = vi.fn()
const mockUnfriend = vi.fn()
const mockAcceptFriendRequest = vi.fn()
const mockRejectFriendRequest = vi.fn()

vi.mock('@/api/social', () => ({
  listFriends: (...args: unknown[]) => mockListFriends(...args),
  listFriendRequests: (...args: unknown[]) => mockListFriendRequests(...args),
  unfriend: (...args: unknown[]) => mockUnfriend(...args),
  acceptFriendRequest: (...args: unknown[]) => mockAcceptFriendRequest(...args),
  rejectFriendRequest: (...args: unknown[]) => mockRejectFriendRequest(...args),
  sendFriendRequest: vi.fn(),
  followUser: vi.fn(),
  unfollowUser: vi.fn(),
  blockUser: vi.fn(),
  unblockUser: vi.fn(),
  getRelationshipStatus: vi.fn(),
}))

vi.mock('@/composables/api', () => ({
  default: { get: vi.fn(), post: vi.fn(), put: vi.fn(), delete: vi.fn() },
}))

vi.mock('@/constants', () => ({
  HEARTBEAT_INTERVAL_MS: 30000,
}))

vi.mock('@/utils/datetime', () => ({
  relativeTime: (d: string) => `relative(${d})`,
}))

const fakeFriends = [
  {
    id: 'f1',
    user_id: 'u1',
    display_name: 'Alice',
    username: 'alice',
    avatar_url: null,
    affiliation: 'MIT',
    created_at: '2026-01-01T00:00:00Z',
  },
  {
    id: 'f2',
    user_id: 'u2',
    display_name: 'Bob',
    username: 'bob',
    avatar_url: 'http://example.com/bob.png',
    affiliation: null,
    created_at: '2026-02-01T00:00:00Z',
  },
]

const fakeRequests = [
  {
    id: 'r1',
    requester_id: 'u3',
    requester_name: 'Charlie',
    requester_username: 'charlie',
    requester_avatar_url: null,
    addressee_id: 'me',
    addressee_name: 'Me',
    addressee_username: 'me',
    addressee_avatar_url: null,
    status: 'pending',
    created_at: '2026-03-01T00:00:00Z',
  },
]

function createTestRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/friends', component: FriendsView },
      { path: '/users/:id', component: { template: '<div />' } },
    ],
  })
}

function createStubs() {
  return {
    SkeletonLoader: { template: '<div class="skeleton-loader" />', props: ['lines', 'variant'] },
    EmptyState: {
      template: '<div class="empty-state">{{ title }}</div>',
      props: ['title', 'message'],
    },
    BasePagination: {
      template: '<div class="base-pagination" />',
      props: ['currentPage', 'totalPages'],
    },
    BaseButton: {
      template: '<button @click="$emit(\'click\')"><slot /></button>',
      props: ['loading', 'variant', 'size', 'disabled'],
    },
    BaseAvatar: {
      template: '<div class="base-avatar" />',
      props: ['src', 'name', 'size'],
    },
    BaseModal: {
      template:
        '<div v-if="modelValue" class="base-modal"><slot /><slot name="footer" /></div>',
      props: ['modelValue', 'title', 'size'],
    },
    FriendRequestCard: {
      template:
        '<div class="friend-request-card" @click="$emit(\'accept\', request.id)">{{ request.requester_name || request.addressee_name }}</div>',
      props: ['request', 'type'],
      emits: ['accept', 'reject'],
    },
    UserMinus: { template: '<span class="icon-user-minus" />' },
  }
}

async function mountFriendsView() {
  const pinia = createPinia()
  setActivePinia(pinia)
  const router = createTestRouter()

  await router.push('/friends')
  await router.isReady()

  const wrapper = mount(FriendsView, {
    global: { plugins: [pinia, router], stubs: createStubs() },
  })
  await flushPromises()
  return { wrapper, router }
}

describe('FriendsView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockListFriends.mockResolvedValue({
      data: { friends: fakeFriends.map((f) => ({ ...f })), total: 2 },
    })
    mockListFriendRequests.mockResolvedValue({
      data: { requests: fakeRequests.map((r) => ({ ...r })), total: 1 },
    })
    mockUnfriend.mockResolvedValue({})
    mockAcceptFriendRequest.mockResolvedValue({})
    mockRejectFriendRequest.mockResolvedValue({})
  })

  it('renders the page title', async () => {
    const { wrapper } = await mountFriendsView()
    expect(wrapper.text()).toContain('Friends')
  })

  it('fetches friends and requests on mount', async () => {
    await mountFriendsView()
    expect(mockListFriends).toHaveBeenCalled()
    expect(mockListFriendRequests).toHaveBeenCalled()
  })

  it('renders friend names', async () => {
    const { wrapper } = await mountFriendsView()
    expect(wrapper.text()).toContain('Alice')
    expect(wrapper.text()).toContain('Bob')
  })

  it('renders friend usernames', async () => {
    const { wrapper } = await mountFriendsView()
    expect(wrapper.text()).toContain('@alice')
    expect(wrapper.text()).toContain('@bob')
  })

  it('renders friend affiliation when present', async () => {
    const { wrapper } = await mountFriendsView()
    expect(wrapper.text()).toContain('MIT')
  })

  it('shows unfriend button for each friend', async () => {
    const { wrapper } = await mountFriendsView()
    const unfriendButtons = wrapper
      .findAll('button')
      .filter((b) => b.text().includes('Unfriend'))
    expect(unfriendButtons.length).toBe(2)
  })

  it('shows tabs for Friends and Requests', async () => {
    const { wrapper } = await mountFriendsView()
    const tabs = wrapper.findAll('button[role="tab"]')
    expect(tabs.length).toBe(2)
    expect(tabs[0].text()).toContain('Friends')
    expect(tabs[1].text()).toContain('Requests')
  })

  it('shows pending request badge count', async () => {
    const { wrapper } = await mountFriendsView()
    const requestsTab = wrapper
      .findAll('button[role="tab"]')
      .find((b) => b.text().includes('Requests'))
    expect(requestsTab).toBeTruthy()
    expect(requestsTab!.text()).toContain('1')
  })

  it('switches to requests tab and shows requests', async () => {
    const { wrapper } = await mountFriendsView()
    const requestsTab = wrapper
      .findAll('button[role="tab"]')
      .find((b) => b.text().includes('Requests'))
    await requestsTab!.trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('Charlie')
  })

  it('shows loading skeleton while fetching', async () => {
    mockListFriends.mockReturnValue(new Promise(() => {}))
    const pinia = createPinia()
    setActivePinia(pinia)
    const router = createTestRouter()

    await router.push('/friends')
    await router.isReady()

    const wrapper = mount(FriendsView, {
      global: { plugins: [pinia, router], stubs: createStubs() },
    })
    await flushPromises()

    expect(wrapper.find('.skeleton-loader').exists()).toBe(true)
  })

  it('shows empty state when no friends', async () => {
    mockListFriends.mockResolvedValue({
      data: { friends: [], total: 0 },
    })
    const { wrapper } = await mountFriendsView()
    expect(wrapper.find('.empty-state').exists()).toBe(true)
    expect(wrapper.text()).toContain('No friends yet')
  })

  it('shows relative time for friend creation date', async () => {
    const { wrapper } = await mountFriendsView()
    expect(wrapper.text()).toContain('relative(2026-01-01T00:00:00Z)')
  })

  it('unfriends a user after confirmation', async () => {
    const { wrapper } = await mountFriendsView()
    // Click unfriend button for first friend
    const unfriendButtons = wrapper
      .findAll('button')
      .filter((b) => b.text().includes('Unfriend'))
    await unfriendButtons[0].trigger('click')
    await flushPromises()

    // Confirm unfriend in modal
    const modal = wrapper.find('.base-modal')
    expect(modal.exists()).toBe(true)

    // Click the unfriend confirm button in the modal
    const modalButtons = modal.findAll('button')
    const confirmBtn = modalButtons.find((b) => b.text().includes('Unfriend'))
    await confirmBtn!.trigger('click')
    await flushPromises()

    expect(mockUnfriend).toHaveBeenCalledWith('u1')
  })

  it('accepts a friend request', async () => {
    const { wrapper } = await mountFriendsView()

    // Switch to requests tab
    const requestsTab = wrapper
      .findAll('button[role="tab"]')
      .find((b) => b.text().includes('Requests'))
    await requestsTab!.trigger('click')
    await flushPromises()

    // The FriendRequestCard emits accept with the request id
    const requestCard = wrapper.find('.friend-request-card')
    expect(requestCard.exists()).toBe(true)
    await requestCard.trigger('click')
    await flushPromises()

    expect(mockAcceptFriendRequest).toHaveBeenCalledWith('r1')
  })
})

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import FriendsView from '../FriendsView.vue'
import { useAuthStore } from '@/stores/auth'

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
      template: '<div v-if="modelValue" class="base-modal"><slot /><slot name="footer" /></div>',
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

// Current user ID used in test data (addressee_id in fakeRequests = 'me')
const CURRENT_USER_ID = 'me'

async function mountFriendsView() {
  const pinia = createPinia()
  setActivePinia(pinia)

  // Set up auth store so incomingRequests computed can compare addressee_id
  const auth = useAuthStore()
  auth.user = {
    id: CURRENT_USER_ID,
    username: 'me',
    display_name: 'Me',
    avatar_url: null,
    role: 'MEMBER',
    bio: null,
    affiliation: null,
    orcid: null,
    preferred_language: 'en',
  } as never

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
      friends: fakeFriends.map((f) => ({ ...f })),
      total: 2,
    })
    mockListFriendRequests.mockResolvedValue({
      requests: fakeRequests.map((r) => ({ ...r })),
      total: 1,
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
    const unfriendButtons = wrapper.findAll('button').filter((b) => b.text().includes('Unfriend'))
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
      friends: [],
      total: 0,
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
    const unfriendButtons = wrapper.findAll('button').filter((b) => b.text().includes('Unfriend'))
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

  it('always refreshes friends list after accepting, regardless of active tab', async () => {
    const { wrapper } = await mountFriendsView()
    // Start on requests tab so the old conditional would NOT call fetchFriends
    const requestsTab = wrapper
      .findAll('button[role="tab"]')
      .find((b) => b.text().includes('Requests'))
    await requestsTab!.trigger('click')
    await flushPromises()
    mockListFriends.mockClear()

    const requestCard = wrapper.find('.friend-request-card')
    await requestCard.trigger('click')
    await flushPromises()

    // fetchFriends must always be called, not only when on the friends tab
    expect(mockListFriends).toHaveBeenCalled()
  })

  it('prevents double-click accept via actionLoading guard', async () => {
    let resolveAccept!: () => void
    mockAcceptFriendRequest.mockReturnValue(
      new Promise<void>((resolve) => {
        resolveAccept = resolve
      }),
    )

    const { wrapper } = await mountFriendsView()
    const requestsTab = wrapper
      .findAll('button[role="tab"]')
      .find((b) => b.text().includes('Requests'))
    await requestsTab!.trigger('click')
    await flushPromises()

    const requestCard = wrapper.find('.friend-request-card')
    // Trigger two rapid clicks
    await requestCard.trigger('click')
    await requestCard.trigger('click')
    resolveAccept()
    await flushPromises()

    // API should only be called once despite two clicks
    expect(mockAcceptFriendRequest).toHaveBeenCalledTimes(1)
  })

  it('separates outgoing from incoming requests using ID comparison, not reference equality', async () => {
    // Create requests where some are incoming (addressee = me) and some outgoing (requester = me)
    const incomingReq = {
      id: 'r-in',
      requester_id: 'u5',
      requester_name: 'Eve',
      requester_username: 'eve',
      requester_avatar_url: null,
      addressee_id: CURRENT_USER_ID,
      addressee_name: 'Me',
      addressee_username: 'me',
      addressee_avatar_url: null,
      status: 'pending',
      created_at: '2026-03-01T00:00:00Z',
    }
    const outgoingReq = {
      id: 'r-out',
      requester_id: CURRENT_USER_ID,
      requester_name: 'Me',
      requester_username: 'me',
      requester_avatar_url: null,
      addressee_id: 'u6',
      addressee_name: 'Frank',
      addressee_username: 'frank',
      addressee_avatar_url: null,
      status: 'pending',
      created_at: '2026-03-02T00:00:00Z',
    }
    mockListFriendRequests.mockResolvedValue({
      requests: [incomingReq, outgoingReq],
      total: 2,
    })

    const { wrapper } = await mountFriendsView()
    const requestsTab = wrapper
      .findAll('button[role="tab"]')
      .find((b) => b.text().includes('Requests'))
    await requestsTab!.trigger('click')
    await flushPromises()

    // Both sections should be visible
    expect(wrapper.text()).toContain('Incoming Requests')
    expect(wrapper.text()).toContain('Sent Requests')

    // Find FriendRequestCards by type prop
    const cards = wrapper.findAll('.friend-request-card')
    expect(cards.length).toBe(2)

    // Eve is incoming (addressee_id = me), Frank's request is outgoing (requester_id = me)
    expect(wrapper.text()).toContain('Eve')
    expect(wrapper.text()).toContain('Me') // outgoing card shows requester_name
  })

  it('shows outgoing requests section only for non-incoming requests', async () => {
    const outgoingRequest = {
      id: 'r2',
      requester_id: CURRENT_USER_ID, // we are the requester → outgoing
      requester_name: 'Me',
      requester_username: 'me',
      requester_avatar_url: null,
      addressee_id: 'u4',
      addressee_name: 'Dave',
      addressee_username: 'dave',
      addressee_avatar_url: null,
      status: 'pending',
      created_at: '2026-03-02T00:00:00Z',
    }
    mockListFriendRequests.mockResolvedValue({
      requests: [...fakeRequests, outgoingRequest],
      total: 2,
    })

    const { wrapper } = await mountFriendsView()
    const requestsTab = wrapper
      .findAll('button[role="tab"]')
      .find((b) => b.text().includes('Requests'))
    await requestsTab!.trigger('click')
    await flushPromises()

    // r2 is outgoing (requester = me, addressee = Dave) → shows in outgoing section
    // FriendRequestCard stub shows requester_name || addressee_name
    // For outgoing: requester_name = 'Me', so stub shows 'Me'
    // Verify the outgoing section header is shown (means the section is rendered)
    expect(wrapper.text()).toContain('Sent Requests')
    // Charlie is incoming (addressee_id = 'me') → appears in incoming section
    expect(wrapper.text()).toContain('Charlie')
  })
})

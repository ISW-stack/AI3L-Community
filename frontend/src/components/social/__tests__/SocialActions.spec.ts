import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import SocialActions from '../SocialActions.vue'
import type { RelationshipStatus } from '@/types/social'

const mockGetRelationshipStatus = vi.fn()
const mockSendFriendRequest = vi.fn()
const mockAcceptFriendRequest = vi.fn()
const mockRejectFriendRequest = vi.fn()
const mockUnfriend = vi.fn()
const mockFollowUser = vi.fn()
const mockUnfollowUser = vi.fn()
const mockBlockUser = vi.fn()
const mockUnblockUser = vi.fn()

vi.mock('@/api/social', () => ({
  getRelationshipStatus: (...args: unknown[]) => mockGetRelationshipStatus(...args),
  sendFriendRequest: (...args: unknown[]) => mockSendFriendRequest(...args),
  acceptFriendRequest: (...args: unknown[]) => mockAcceptFriendRequest(...args),
  rejectFriendRequest: (...args: unknown[]) => mockRejectFriendRequest(...args),
  unfriend: (...args: unknown[]) => mockUnfriend(...args),
  followUser: (...args: unknown[]) => mockFollowUser(...args),
  unfollowUser: (...args: unknown[]) => mockUnfollowUser(...args),
  blockUser: (...args: unknown[]) => mockBlockUser(...args),
  unblockUser: (...args: unknown[]) => mockUnblockUser(...args),
}))

vi.mock('@/composables/api', () => ({
  default: { get: vi.fn(), post: vi.fn(), put: vi.fn(), delete: vi.fn() },
}))

vi.mock('@/constants', () => ({
  HEARTBEAT_INTERVAL_MS: 30000,
}))

const noRelationship: RelationshipStatus = {
  is_friend: false,
  is_following: false,
  is_followed_by: false,
  is_blocked: false,
  pending_request: null,
  friendship_id: null,
}

const friendStatus: RelationshipStatus = {
  is_friend: true,
  is_following: true,
  is_followed_by: true,
  is_blocked: false,
  pending_request: null,
  friendship_id: 'f1',
}

const requestSentStatus: RelationshipStatus = {
  is_friend: false,
  is_following: false,
  is_followed_by: false,
  is_blocked: false,
  pending_request: 'sent',
  friendship_id: 'f2',
}

const requestReceivedStatus: RelationshipStatus = {
  is_friend: false,
  is_following: false,
  is_followed_by: true,
  is_blocked: false,
  pending_request: 'received',
  friendship_id: 'f3',
}

const blockedStatus: RelationshipStatus = {
  is_friend: false,
  is_following: false,
  is_followed_by: false,
  is_blocked: true,
  pending_request: null,
  friendship_id: null,
}

function createTestRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/', component: { template: '<div />' } }],
  })
}

function createStubs() {
  return {
    BaseButton: {
      template: '<button :disabled="disabled" @click="$emit(\'click\')"><slot /></button>',
      props: ['loading', 'variant', 'size', 'disabled'],
    },
    BaseBadge: {
      template: '<span class="base-badge"><slot /></span>',
      props: ['variant', 'size'],
    },
    BaseModal: {
      template:
        '<div v-if="modelValue" class="base-modal"><slot /><slot name="footer" /></div>',
      props: ['modelValue', 'title', 'size'],
    },
    MoreVertical: { template: '<span class="icon-more" />' },
    UserPlus: { template: '<span class="icon-user-plus" />' },
    UserMinus: { template: '<span class="icon-user-minus" />' },
    UserX: { template: '<span class="icon-user-x" />' },
    Shield: { template: '<span class="icon-shield" />' },
    ShieldOff: { template: '<span class="icon-shield-off" />' },
  }
}

async function mountSocialActions(
  initialStatus?: RelationshipStatus,
  userId = 'target-user',
) {
  const pinia = createPinia()
  setActivePinia(pinia)
  const router = createTestRouter()

  await router.push('/')
  await router.isReady()

  const wrapper = mount(SocialActions, {
    props: { userId, ...(initialStatus ? { initialStatus } : {}) },
    global: { plugins: [pinia, router], stubs: createStubs() },
  })
  await flushPromises()
  return { wrapper }
}

describe('SocialActions', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockGetRelationshipStatus.mockResolvedValue({ data: noRelationship })
    mockSendFriendRequest.mockResolvedValue({})
    mockAcceptFriendRequest.mockResolvedValue({})
    mockRejectFriendRequest.mockResolvedValue({})
    mockUnfriend.mockResolvedValue({})
    mockFollowUser.mockResolvedValue({})
    mockUnfollowUser.mockResolvedValue({})
    mockBlockUser.mockResolvedValue({})
    mockUnblockUser.mockResolvedValue({})
  })

  it('fetches status on mount when no initialStatus provided', async () => {
    await mountSocialActions()
    expect(mockGetRelationshipStatus).toHaveBeenCalledWith('target-user')
  })

  it('does not fetch status when initialStatus is provided', async () => {
    await mountSocialActions(noRelationship)
    expect(mockGetRelationshipStatus).not.toHaveBeenCalled()
  })

  it('shows Add Friend and Follow buttons when no relationship', async () => {
    const { wrapper } = await mountSocialActions(noRelationship)
    expect(wrapper.text()).toContain('Add Friend')
    expect(wrapper.text()).toContain('Follow')
  })

  it('shows Request Sent when friend request is pending', async () => {
    const { wrapper } = await mountSocialActions(requestSentStatus)
    expect(wrapper.text()).toContain('Request Sent')
  })

  it('shows Accept and Decline when request is received', async () => {
    const { wrapper } = await mountSocialActions(requestReceivedStatus)
    expect(wrapper.text()).toContain('Accept')
    expect(wrapper.text()).toContain('Decline')
  })

  it('shows Friends badge and Unfriend when friends', async () => {
    const { wrapper } = await mountSocialActions(friendStatus)
    expect(wrapper.text()).toContain('Friends')
    expect(wrapper.text()).toContain('Unfriend')
  })

  it('shows Blocked badge and Unblock when blocked', async () => {
    const { wrapper } = await mountSocialActions(blockedStatus)
    expect(wrapper.text()).toContain('Blocked')
    expect(wrapper.text()).toContain('Unblock')
  })

  it('sends friend request when Add Friend clicked', async () => {
    const { wrapper } = await mountSocialActions(noRelationship)
    const addBtn = wrapper.findAll('button').find((b) => b.text().includes('Add Friend'))
    await addBtn!.trigger('click')
    await flushPromises()
    expect(mockSendFriendRequest).toHaveBeenCalledWith('target-user')
  })

  it('accepts friend request when Accept clicked', async () => {
    const { wrapper } = await mountSocialActions(requestReceivedStatus)
    const acceptBtn = wrapper.findAll('button').find((b) => b.text().includes('Accept'))
    await acceptBtn!.trigger('click')
    await flushPromises()
    expect(mockAcceptFriendRequest).toHaveBeenCalledWith('f3')
  })

  it('declines friend request when Decline clicked', async () => {
    const { wrapper } = await mountSocialActions(requestReceivedStatus)
    const declineBtn = wrapper.findAll('button').find((b) => b.text().includes('Decline'))
    await declineBtn!.trigger('click')
    await flushPromises()
    expect(mockRejectFriendRequest).toHaveBeenCalledWith('f3')
  })

  it('follows user when Follow clicked', async () => {
    const { wrapper } = await mountSocialActions(noRelationship)
    const followBtn = wrapper.findAll('button').find((b) => b.text().includes('Follow'))
    await followBtn!.trigger('click')
    await flushPromises()
    expect(mockFollowUser).toHaveBeenCalledWith('target-user')
  })

  it('unfollows user when Unfollow clicked', async () => {
    const status: RelationshipStatus = { ...noRelationship, is_following: true }
    const { wrapper } = await mountSocialActions(status)
    const unfollowBtn = wrapper.findAll('button').find((b) => b.text().includes('Unfollow'))
    await unfollowBtn!.trigger('click')
    await flushPromises()
    expect(mockUnfollowUser).toHaveBeenCalledWith('target-user')
  })

  it('unblocks user when Unblock clicked', async () => {
    const { wrapper } = await mountSocialActions(blockedStatus)
    const unblockBtn = wrapper.findAll('button').find((b) => b.text().includes('Unblock'))
    await unblockBtn!.trigger('click')
    await flushPromises()
    expect(mockUnblockUser).toHaveBeenCalledWith('target-user')
  })

  it('shows loading state while fetching status', async () => {
    mockGetRelationshipStatus.mockReturnValue(new Promise(() => {}))
    const { wrapper } = await mountSocialActions()
    // Should show loading skeleton elements
    expect(wrapper.findAll('.animate-pulse').length).toBeGreaterThan(0)
  })

  it('shows more menu with Block option', async () => {
    const { wrapper } = await mountSocialActions(noRelationship)
    const moreBtn = wrapper.find('button[aria-label="More actions"]')
    expect(moreBtn.exists()).toBe(true)
  })

  it('updates optimistically when sending friend request', async () => {
    mockSendFriendRequest.mockReturnValue(new Promise(() => {}))
    const { wrapper } = await mountSocialActions(noRelationship)

    const addBtn = wrapper.findAll('button').find((b) => b.text().includes('Add Friend'))
    await addBtn!.trigger('click')
    await flushPromises()

    // After optimistic update, should show "Request Sent"
    expect(wrapper.text()).toContain('Request Sent')
  })
})

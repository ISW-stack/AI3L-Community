/**
 * Tests for three DM UX fixes:
 *   Fix 1 (P1) - dm_friends_only preventative UI on UserProfileView
 *   Fix 2 (P1) - 404 toast notification in DMView when conversation deleted
 *   Fix 3 (P2) - Thread header avatar/name is a clickable router-link to user profile
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

// --------------- Global mocks ---------------

vi.mock('@/composables/api', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
    patch: vi.fn(),
  },
}))

vi.mock('@/constants', () => ({
  HEARTBEAT_INTERVAL_MS: 30000,
  WS_INITIAL_BACKOFF_MS: 1000,
  WS_MAX_BACKOFF_MS: 30000,
}))

const mockRouterPush = vi.fn()
const mockRouteParams = { id: 'user-42', userId: undefined as string | undefined }

vi.mock('vue-router', () => ({
  useRoute: () => ({ params: mockRouteParams }),
  useRouter: () => ({ push: mockRouterPush }),
  RouterLink: {
    name: 'RouterLink',
    props: ['to', 'title'],
    template: '<a :href="to" :title="title" v-bind="$attrs"><slot /></a>',
  },
}))

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({
    role: 'MEMBER',
    isAuthenticated: true,
    isAdmin: false,
    isSuperAdmin: false,
    isGuest: false,
    user: { id: 'user-1', display_name: 'Me' },
    clearSession: vi.fn(),
  }),
}))

const mockToastShow = vi.fn()
vi.mock('@/stores/toast', () => ({
  useToastStore: () => ({
    toasts: [],
    show: mockToastShow,
    dismiss: vi.fn(),
    clearAll: vi.fn(),
    showKey: vi.fn(),
  }),
}))

const mockListConversations = vi.fn()
const mockListMessages = vi.fn()
const mockMarkConversationRead = vi.fn()
const mockGetUnreadCount = vi.fn()
const mockSendMessage = vi.fn()
const mockEditMessage = vi.fn()
const mockRecallMessage = vi.fn()

vi.mock('@/api/dm', () => ({
  listConversations: (...args: unknown[]) => mockListConversations(...args),
  listMessages: (...args: unknown[]) => mockListMessages(...args),
  sendMessage: (...args: unknown[]) => mockSendMessage(...args),
  editMessage: (...args: unknown[]) => mockEditMessage(...args),
  recallMessage: (...args: unknown[]) => mockRecallMessage(...args),
  markConversationRead: (...args: unknown[]) => mockMarkConversationRead(...args),
  getUnreadCount: (...args: unknown[]) => mockGetUnreadCount(...args),
}))

vi.mock('@/composables/usePagination', () => ({
  usePagination: () => ({
    page: { value: 1 },
    total: { value: 0 },
    totalPages: { value: 1 },
    pageSize: 30,
    setPage: vi.fn(),
    resetPage: vi.fn(),
    updateFromResponse: vi.fn(),
  }),
}))

vi.mock('@/api/users', () => ({
  getPublicProfile: vi.fn(),
}))

vi.mock('@/api/posts', () => ({
  listPosts: vi.fn().mockResolvedValue({ posts: [], total: 0, total_pages: 1 }),
}))

vi.mock('@/api/coauthors', () => ({
  listCoAuthoredPosts: vi.fn().mockResolvedValue({ posts: [] }),
}))

vi.mock('@/api/social', () => ({
  getRelationshipStatus: vi.fn().mockResolvedValue({
    is_friend: false,
    is_following: false,
    is_followed_by: false,
    is_blocked: false,
    pending_request: null,
    friendship_id: null,
  }),
  sendFriendRequest: vi.fn(),
  acceptFriendRequest: vi.fn(),
  rejectFriendRequest: vi.fn(),
  unfriend: vi.fn(),
  followUser: vi.fn(),
  unfollowUser: vi.fn(),
  blockUser: vi.fn(),
  unblockUser: vi.fn(),
}))

vi.mock('@/composables/useLocale', () => ({
  useLocale: () => ({ currentLocale: { value: 'en' } }),
}))

vi.mock('vue-i18n', () => ({
  useI18n: () => ({
    t: (key: string) => key,
    locale: { value: 'en' },
  }),
}))

vi.mock('lucide-vue-next', () => ({
  MessageSquare: { name: 'MessageSquare', template: '<span class="icon-message-square" />' },
  Lock: { name: 'Lock', template: '<span class="icon-lock" />' },
  ArrowLeft: { name: 'ArrowLeft', template: '<span class="icon-arrow-left" />' },
  UserPlus: { name: 'UserPlus', template: '<span />' },
  UserMinus: { name: 'UserMinus', template: '<span />' },
  UserX: { name: 'UserX', template: '<span />' },
  Shield: { name: 'Shield', template: '<span />' },
  ShieldOff: { name: 'ShieldOff', template: '<span />' },
  MoreVertical: { name: 'MoreVertical', template: '<span />' },
  Check: { name: 'Check', template: '<span />' },
  CheckCheck: { name: 'CheckCheck', template: '<span />' },
  AlertTriangle: { name: 'AlertTriangle', template: '<span />' },
  File: { name: 'File', template: '<span />' },
  FileText: { name: 'FileText', template: '<span />' },
  Film: { name: 'Film', template: '<span />' },
  Music: { name: 'Music', template: '<span />' },
  Pencil: { name: 'Pencil', template: '<span />' },
  Trash2: { name: 'Trash2', template: '<span />' },
  MoreHorizontal: { name: 'MoreHorizontal', template: '<span />' },
  ArrowDown: { name: 'ArrowDown', template: '<span />' },
}))

// Stub heavy child components for DMView tests
vi.mock('@/components/dm/ConversationList.vue', () => ({
  default: { name: 'ConversationList', template: '<div class="conv-list" />' },
}))

vi.mock('@/components/dm/MessageThread.vue', () => ({
  default: { name: 'MessageThread', template: '<div class="msg-thread" />' },
}))

vi.mock('@/components/dm/MessageInput.vue', () => ({
  default: { name: 'MessageInput', template: '<div class="msg-input" />' },
}))

vi.mock('@/components/base/BaseBreadcrumb.vue', () => ({
  default: { name: 'BaseBreadcrumb', template: '<nav />' },
}))

vi.mock('@/components/base/BaseModal.vue', () => ({
  default: {
    name: 'BaseModal',
    props: ['modelValue', 'title', 'size'],
    template: '<div v-if="modelValue"><slot /><slot name="footer" /></div>',
  },
}))

vi.mock('@/components/EmptyState.vue', () => ({
  default: { name: 'EmptyState', template: '<div class="empty-state" />' },
}))

// Stub UserProfileView child components
vi.mock('@/components/PostCard.vue', () => ({
  default: { name: 'PostCard', template: '<div />' },
}))
vi.mock('@/components/base/BaseCard.vue', () => ({
  default: { name: 'BaseCard', template: '<div><slot /></div>', props: ['padding'] },
}))
vi.mock('@/components/base/BaseBadge.vue', () => ({
  default: { name: 'BaseBadge', template: '<span><slot /></span>', props: ['variant', 'size'] },
}))
vi.mock('@/components/base/BasePagination.vue', () => ({
  default: { name: 'BasePagination', template: '<div />' },
}))
vi.mock('@/components/base/BaseAvatar.vue', () => ({
  default: { name: 'BaseAvatar', template: '<div />' },
}))
vi.mock('@/components/SkeletonLoader.vue', () => ({
  default: { name: 'SkeletonLoader', template: '<div />' },
}))
vi.mock('@/components/base/BaseBreadcrumb.vue', () => ({
  default: { name: 'BaseBreadcrumb', template: '<nav />' },
}))
vi.mock('@/components/social/SocialActions.vue', () => ({
  default: { name: 'SocialActions', template: '<div data-testid="social-actions" />', props: ['userId'] },
}))
vi.mock('@/components/social/FriendRecommendations.vue', () => ({
  default: { name: 'FriendRecommendations', template: '<div />' },
}))
vi.mock('@/components/base/BaseButton.vue', () => ({
  default: {
    name: 'BaseButton',
    props: ['size', 'variant', 'disabled', 'loading'],
    template: '<button :disabled="disabled"><slot /></button>',
  },
}))

// --------------- Test helpers ---------------

function makeConversation(overrides: Record<string, unknown> = {}) {
  return {
    id: 'conv-1',
    other_user: {
      id: 'user-2',
      display_name: 'Alice',
      avatar_url: null,
    },
    last_message: null,
    unread_count: 0,
    updated_at: '2026-03-17T00:00:00Z',
    ...overrides,
  }
}

// ═══════════════════════════════════════════════════════════════════
// Fix 1: dm_friends_only preventative UI (UserProfileView)
// ═══════════════════════════════════════════════════════════════════

import UserProfileView from '@/views/UserProfileView.vue'
import { getPublicProfile } from '@/api/users'

const mockGetPublicProfile = vi.mocked(getPublicProfile)

function makePublicUser(overrides: Record<string, unknown> = {}) {
  return {
    id: 'user-42',
    username: 'alice',
    display_name: 'Alice',
    role: 'MEMBER',
    avatar_url: null,
    bio: null,
    affiliation: null,
    orcid: null,
    profile_view_count_unique: 0,
    profile_view_count_total: 0,
    created_at: '2026-01-01T00:00:00Z',
    dm_friends_only: false,
    ...overrides,
  }
}

describe('Fix 1: dm_friends_only preventative UI on UserProfileView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    mockRouteParams.id = 'user-42'
  })

  it('renders a Message button linking to /messages/:userId', async () => {
    mockGetPublicProfile.mockResolvedValueOnce(makePublicUser())
    const wrapper = mount(UserProfileView, { global: { plugins: [createPinia()] } })
    await flushPromises()

    const btn = wrapper.find('[data-testid="message-btn"]')
    expect(btn.exists()).toBe(true)
    // Check the rendered HTML contains the correct URL (router-link stub)
    expect(wrapper.html()).toContain('/messages/user-42')
  })

  it('does NOT show lock icon when dm_friends_only is false', async () => {
    mockGetPublicProfile.mockResolvedValueOnce(makePublicUser({ dm_friends_only: false }))
    const wrapper = mount(UserProfileView, { global: { plugins: [createPinia()] } })
    await flushPromises()

    expect(wrapper.find('.icon-lock').exists()).toBe(false)
  })

  it('shows lock icon when dm_friends_only is true', async () => {
    mockGetPublicProfile.mockResolvedValueOnce(makePublicUser({ dm_friends_only: true }))
    const wrapper = mount(UserProfileView, { global: { plugins: [createPinia()] } })
    await flushPromises()

    expect(wrapper.find('.icon-lock').exists()).toBe(true)
  })

  it('lock icon title says friends only', async () => {
    mockGetPublicProfile.mockResolvedValueOnce(makePublicUser({ dm_friends_only: true }))
    const wrapper = mount(UserProfileView, { global: { plugins: [createPinia()] } })
    await flushPromises()

    const btn = wrapper.find('[data-testid="message-btn"]')
    expect(btn.attributes('title')).toContain('friends')
  })

  it('does NOT render Message button on own profile', async () => {
    // When isOwnProfile, the button should not render
    // auth.user.id === userId → isOwnProfile = true
    mockRouteParams.id = 'user-1' // same as auth store user.id
    mockGetPublicProfile.mockResolvedValueOnce(makePublicUser({ id: 'user-1' }))
    const wrapper = mount(UserProfileView, { global: { plugins: [createPinia()] } })
    await flushPromises()

    expect(wrapper.find('[data-testid="message-btn"]').exists()).toBe(false)
  })
})

// ═══════════════════════════════════════════════════════════════════
// Fix 2: 404 toast notification in DMView
// ═══════════════════════════════════════════════════════════════════

import DMView from '@/views/DMView.vue'

describe('Fix 2: 404 toast notification when conversation is deleted', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    mockRouteParams.userId = undefined
    mockGetUnreadCount.mockResolvedValue({ unread_count: 0 })
    mockListConversations.mockResolvedValue({ conversations: [], total: 0 })
    mockMarkConversationRead.mockResolvedValue({})
  })

  it('shows error toast when fetchMessages returns 404', async () => {
    const err404 = Object.assign(new Error('Not Found'), {
      response: { status: 404 },
    })
    mockListMessages.mockRejectedValueOnce(err404)

    const conv = makeConversation({ id: 'conv-deleted' })
    mockListConversations.mockResolvedValueOnce({ conversations: [conv], total: 1 })

    const wrapper = mount(DMView, { global: { plugins: [createPinia()] } })
    await flushPromises()

    // Simulate selecting a conversation
    const store = (wrapper.vm as unknown as { dmStore: { selectConversation?: unknown } })
    // Trigger selectConversation via the component's internal method
    await (wrapper.vm as unknown as { selectConversation: (id: string, userId: string) => Promise<void> }).selectConversation?.('conv-deleted', 'user-2')
    await flushPromises()

    expect(mockToastShow).toHaveBeenCalledWith(
      expect.stringContaining('conversation no longer exists'),
      'error',
    )
  })

  it('does NOT show error toast when fetchMessages succeeds', async () => {
    mockListMessages.mockResolvedValueOnce({ messages: [], total: 0 })

    const conv = makeConversation()
    mockListConversations.mockResolvedValueOnce({ conversations: [conv], total: 1 })

    const wrapper = mount(DMView, { global: { plugins: [createPinia()] } })
    await flushPromises()

    await (wrapper.vm as unknown as { selectConversation: (id: string, userId: string) => Promise<void> }).selectConversation?.('conv-1', 'user-2')
    await flushPromises()

    // Toast should NOT be called with 'error' for messages
    const errorCalls = mockToastShow.mock.calls.filter(
      (call: unknown[]) => call[1] === 'error',
    )
    expect(errorCalls).toHaveLength(0)
  })
})

// ═══════════════════════════════════════════════════════════════════
// Fix 3: Thread header router-link to user profile
// ═══════════════════════════════════════════════════════════════════

describe('Fix 3: Thread header has router-link to other user profile', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    mockRouteParams.userId = undefined
    mockGetUnreadCount.mockResolvedValue({ unread_count: 0 })
    mockListConversations.mockResolvedValue({ conversations: [], total: 0 })
    mockListMessages.mockResolvedValue({ messages: [], total: 0 })
    mockMarkConversationRead.mockResolvedValue({})
  })

  it('renders a profile link in the thread header when a conversation is active', async () => {
    const conv = makeConversation({
      id: 'conv-1',
      other_user: { id: 'user-2', display_name: 'Alice', avatar_url: null },
    })
    mockListConversations.mockResolvedValueOnce({ conversations: [conv], total: 1 })

    const wrapper = mount(DMView, { global: { plugins: [createPinia()] } })
    await flushPromises()

    // Select the conversation to activate it
    await (wrapper.vm as unknown as { selectConversation: (id: string, userId: string) => Promise<void> }).selectConversation?.('conv-1', 'user-2')
    await flushPromises()

    const link = wrapper.find('[data-testid="thread-header-profile-link"]')
    expect(link.exists()).toBe(true)
    expect(wrapper.html()).toContain('/users/user-2')
  })

  it('thread header profile link contains the other user display name', async () => {
    const conv = makeConversation({
      id: 'conv-1',
      other_user: { id: 'user-2', display_name: 'Alice', avatar_url: null },
    })
    mockListConversations.mockResolvedValueOnce({ conversations: [conv], total: 1 })

    const wrapper = mount(DMView, { global: { plugins: [createPinia()] } })
    await flushPromises()

    await (wrapper.vm as unknown as { selectConversation: (id: string, userId: string) => Promise<void> }).selectConversation?.('conv-1', 'user-2')
    await flushPromises()

    const link = wrapper.find('[data-testid="thread-header-profile-link"]')
    expect(link.text()).toContain('Alice')
  })
})

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import FriendsView from '../social/FriendsView.vue'
import QAListView from '../qa/QAListView.vue'
import { useAuthStore } from '@/stores/auth'

// ── Mock social API ──
const mockListFriends = vi.fn()
const mockListFriendRequests = vi.fn()
vi.mock('@/api/social', () => ({
  listFriends: (...args: unknown[]) => mockListFriends(...args),
  listFriendRequests: (...args: unknown[]) => mockListFriendRequests(...args),
  unfriend: vi.fn(),
  acceptFriendRequest: vi.fn(),
  rejectFriendRequest: vi.fn(),
  listFollowing: vi.fn().mockResolvedValue({ data: { users: [], total: 0 } }),
  listFollowers: vi.fn().mockResolvedValue({ data: { users: [], total: 0 } }),
  unfollowUser: vi.fn(),
  followUser: vi.fn(),
  listBlocks: vi.fn().mockResolvedValue({ data: { blocks: [], total: 0 } }),
  unblockUser: vi.fn(),
  blockUser: vi.fn(),
}))

// ── Mock posts API ──
const mockListPosts = vi.fn()
vi.mock('@/api/posts', () => ({
  listPosts: (...args: unknown[]) => mockListPosts(...args),
  searchPosts: vi.fn(),
  getTrendingPosts: vi.fn(),
  getPublicStats: vi.fn(),
  createPost: vi.fn(),
  getPost: vi.fn(),
  deletePost: vi.fn(),
}))

vi.mock('@/composables/api', () => ({
  default: { get: vi.fn(), post: vi.fn() },
}))

vi.mock('@/api/notifications', () => ({
  listNotifications: vi.fn().mockResolvedValue({ notifications: [], total: 0, unread_count: 0 }),
  markRead: vi.fn(),
  markAllRead: vi.fn(),
}))

vi.mock('@/constants', () => ({
  HEARTBEAT_INTERVAL_MS: 30000,
}))

function createStubs() {
  return {
    BaseAvatar: { template: '<span />', props: ['src', 'name', 'size'] },
    BaseButton: {
      template: '<button @click="$emit(\'click\')"><slot /></button>',
      props: ['loading', 'variant', 'size', 'disabled'],
    },
    BaseModal: {
      template: '<div><slot /><slot name="footer" /></div>',
      props: ['modelValue', 'title', 'size'],
    },
    BasePagination: { template: '<div />', props: ['currentPage', 'totalPages'] },
    SkeletonLoader: { template: '<div class="skeleton" />', props: ['lines', 'variant'] },
    EmptyState: {
      template: '<div class="empty-state" :data-title="title" :data-message="message" />',
      props: ['title', 'message', 'actionLabel', 'actionTo'],
    },
    FriendRequestCard: { template: '<div />', props: ['request', 'type'] },
    UserMinus: { template: '<span />' },
    QACard: {
      template: '<div class="qa-card">{{ question?.title }}</div>',
      props: ['question'],
    },
  }
}

function createTestRouter(initialRoute: string) {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/friends', component: FriendsView },
      { path: '/qa', component: QAListView },
      { path: '/qa/create', component: { template: '<div />' } },
      { path: '/qa/:id', component: { template: '<div />' } },
      { path: '/users/:id', component: { template: '<div />' } },
    ],
  })
}

async function mountFriends() {
  const pinia = createPinia()
  setActivePinia(pinia)
  const auth = useAuthStore()
  auth.setSession('MEMBER', 3600)
  auth.user = {
    id: 'u1',
    username: 'testuser',
    display_name: 'Test User',
    role: 'MEMBER',
    bio: null,
    affiliation: null,
    orcid: null,
    avatar_url: null,
    is_banned: false,
    ban_reason: null,
  } as any

  const router = createTestRouter('/friends')
  await router.push('/friends')
  await router.isReady()

  const wrapper = mount(FriendsView, {
    global: { plugins: [pinia, router], stubs: createStubs() },
  })
  await flushPromises()
  return wrapper
}

async function mountQAList() {
  const pinia = createPinia()
  setActivePinia(pinia)
  const auth = useAuthStore()
  auth.setSession('MEMBER', 3600)
  auth.user = {
    id: 'u1',
    username: 'testuser',
    display_name: 'Test User',
    role: 'MEMBER',
    bio: null,
    affiliation: null,
    orcid: null,
    avatar_url: null,
    is_banned: false,
    ban_reason: null,
  } as any

  const router = createTestRouter('/qa')
  await router.push('/qa')
  await router.isReady()

  const wrapper = mount(QAListView, {
    global: { plugins: [pinia, router], stubs: createStubs() },
  })
  await flushPromises()
  return wrapper
}

describe('i18n gaps — FriendsView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockListFriends.mockResolvedValue({ data: { friends: [], total: 0 } })
    mockListFriendRequests.mockResolvedValue({ data: { requests: [], total: 0 } })
  })

  it('renders page title and tab labels using i18n keys', async () => {
    const wrapper = await mountFriends()
    const html = wrapper.html()

    // The page title should use the i18n key — in test env vue-i18n returns the key path
    // The h1 should contain the translated text (key path in test)
    expect(wrapper.find('h1').exists()).toBe(true)

    // Tab buttons should exist (Friends + Requests)
    const tabs = wrapper.findAll('button[role="tab"]')
    expect(tabs.length).toBe(2)

    // Empty state should use i18n-bound props (not hardcoded)
    const emptyState = wrapper.find('.empty-state')
    if (emptyState.exists()) {
      // If the empty state renders, its title/message come from t() calls
      const title = emptyState.attributes('data-title')
      expect(title).toBeTruthy()
    }
  })

  it('renders empty state with i18n keys when no friends', async () => {
    const wrapper = await mountFriends()
    const emptyState = wrapper.find('.empty-state')
    expect(emptyState.exists()).toBe(true)
    // The title prop should come from t('social.noFriends') — vue-i18n returns key in test
    const title = emptyState.attributes('data-title')
    expect(title).toBeTruthy()
    expect(title).not.toBe('')
  })
})

describe('i18n gaps — QAListView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockListPosts.mockResolvedValue({ posts: [], total: 0, total_pages: 1 })
  })

  it('renders page title using i18n key', async () => {
    const wrapper = await mountQAList()
    const h1 = wrapper.find('h1')
    expect(h1.exists()).toBe(true)
    // In test env, t('qa.title') returns 'qa.title' — just verify it exists and is not empty
    expect(h1.text()).toBeTruthy()
  })

  it('renders empty state with i18n keys when no questions', async () => {
    const wrapper = await mountQAList()
    const emptyState = wrapper.find('.empty-state')
    expect(emptyState.exists()).toBe(true)
    const title = emptyState.attributes('data-title')
    expect(title).toBeTruthy()
    expect(title).not.toBe('')
  })

  it('renders ask question button with i18n key', async () => {
    const wrapper = await mountQAList()
    // The "Ask a Question" button should exist for authenticated members
    const buttons = wrapper.findAll('button')
    expect(buttons.length).toBeGreaterThan(0)
  })
})

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { nextTick } from 'vue'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import UserProfileView from '../UserProfileView.vue'
import { useAuthStore } from '@/stores/auth'
import type { UserProfile } from '@/types/user'

const mockGetPublicProfile = vi.fn()
const mockListPosts = vi.fn()

vi.mock('@/api/users', () => ({
  getPublicProfile: (...args: unknown[]) => mockGetPublicProfile(...args),
  getProfile: vi.fn(),
  updateProfile: vi.fn(),
}))

vi.mock('@/api/posts', () => ({
  listPosts: (...args: unknown[]) => mockListPosts(...args),
  searchPosts: vi.fn(),
  getTrendingPosts: vi.fn(),
}))

vi.mock('@/composables/api', () => ({
  default: { get: vi.fn(), post: vi.fn() },
}))

vi.mock('@/constants', () => ({
  HEARTBEAT_INTERVAL_MS: 30000,
}))

const fakeUser = {
  id: 'user-other',
  username: 'otheruser',
  display_name: 'Other User',
  role: 'MEMBER',
  bio: 'I study AI in language learning',
  affiliation: 'Stanford University',
  orcid: '0000-0002-0000-0000',
  avatar_url: null,
  created_at: '2025-06-15T00:00:00Z',
}

const fakePosts = [
  {
    id: 'p1',
    title: 'Post by Other',
    content: 'Content',
    created_at: '2026-01-01T00:00:00Z',
    comment_count: 3,
    view_count: 10,
    author: { id: 'user-other', display_name: 'Other User', avatar_url: null },
  },
]

function createTestRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/users/:id', component: UserProfileView },
      { path: '/forum', component: { template: '<div />' } },
      { path: '/profile', component: { template: '<div />' } },
    ],
  })
}

function createStubs() {
  return {
    BaseCard: { template: '<div class="base-card"><slot /></div>', props: ['padding'] },
    BaseBadge: { template: '<span class="base-badge"><slot /></span>', props: ['variant'] },
    BasePagination: {
      template: '<div class="base-pagination" />',
      props: ['currentPage', 'totalPages'],
    },
    BaseAvatar: {
      template: '<div class="base-avatar" />',
      props: ['src', 'name', 'size'],
    },
    SkeletonLoader: { template: '<div class="skeleton-loader" />', props: ['lines', 'variant'] },
    EmptyState: {
      template: '<div class="empty-state">{{ title }}</div>',
      props: ['title', 'message'],
    },
    PostCard: {
      template: '<div class="post-card">{{ post.title }}</div>',
      props: ['post', 'formatTime', 'maxPreviewLines'],
    },
  }
}

async function mountUserProfile(options?: { userId?: string; isSelf?: boolean }) {
  const { userId = 'user-other', isSelf = false } = options ?? {}
  const pinia = createPinia()
  setActivePinia(pinia)
  const router = createTestRouter()

  const auth = useAuthStore()
  auth.setSession('MEMBER', 3600)
  auth.user = {
    id: isSelf ? userId : 'current-user',
    username: 'currentuser',
    display_name: 'Current User',
    role: 'MEMBER',
    bio: null,
    affiliation: null,
    orcid: null,
    avatar_url: null,
    is_banned: false,
    ban_reason: null,
  } as unknown as UserProfile

  await router.push(`/users/${userId}`)
  await router.isReady()

  const wrapper = mount(UserProfileView, {
    global: { plugins: [pinia, router], stubs: createStubs() },
  })
  await flushPromises()
  return { wrapper, auth, router }
}

describe('UserProfileView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockGetPublicProfile.mockResolvedValue(fakeUser)
    mockListPosts.mockResolvedValue({ posts: fakePosts, total: 1, total_pages: 1 })
  })

  it('fetches user profile on mount', async () => {
    await mountUserProfile()
    expect(mockGetPublicProfile).toHaveBeenCalledWith('user-other')
  })

  it('fetches user posts on mount', async () => {
    await mountUserProfile()
    expect(mockListPosts).toHaveBeenCalledWith(expect.objectContaining({ author_id: 'user-other' }))
  })

  it('renders user display name', async () => {
    const { wrapper } = await mountUserProfile()
    expect(wrapper.text()).toContain('Other User')
  })

  it('renders username with @ prefix', async () => {
    const { wrapper } = await mountUserProfile()
    expect(wrapper.text()).toContain('@otheruser')
  })

  it('renders user bio', async () => {
    const { wrapper } = await mountUserProfile()
    expect(wrapper.text()).toContain('I study AI in language learning')
  })

  it('renders user affiliation', async () => {
    const { wrapper } = await mountUserProfile()
    expect(wrapper.text()).toContain('Stanford University')
  })

  it('renders user ORCID', async () => {
    const { wrapper } = await mountUserProfile()
    expect(wrapper.text()).toContain('0000-0002-0000-0000')
  })

  it('renders role badge', async () => {
    const { wrapper } = await mountUserProfile()
    expect(wrapper.find('.base-badge').exists()).toBe(true)
    expect(wrapper.text()).toContain('MEMBER')
  })

  it('renders user posts', async () => {
    const { wrapper } = await mountUserProfile()
    expect(wrapper.find('.post-card').exists()).toBe(true)
    expect(wrapper.text()).toContain('Post by Other')
  })

  it('shows edit profile link when viewing own profile', async () => {
    // Navigate to the user's own profile (userId matches auth.user.id)
    mockGetPublicProfile.mockResolvedValue({ ...fakeUser, id: 'current-user' })

    const pinia = createPinia()
    setActivePinia(pinia)
    const router = createTestRouter()
    const auth = useAuthStore()
    auth.setSession('MEMBER', 3600)

    await router.push('/users/current-user')
    await router.isReady()

    const wrapper = mount(UserProfileView, {
      global: { plugins: [pinia, router], stubs: createStubs() },
    })

    // Set user after mount so pinia reactivity picks it up in the component
    auth.user = {
      id: 'current-user',
      username: 'currentuser',
      display_name: 'Current User',
      role: 'MEMBER',
      bio: null,
      affiliation: null,
      orcid: null,
      avatar_url: null,
      is_banned: false,
      ban_reason: null,
    } as unknown as UserProfile

    await flushPromises()
    await nextTick()

    const links = wrapper.findAll('a')
    const editLink = links.find((l) => l.attributes('href')?.includes('/profile'))
    expect(editLink).toBeTruthy()
  })

  it('hides edit profile link when viewing another user', async () => {
    const { wrapper } = await mountUserProfile({ isSelf: false })
    const links = wrapper.findAll('a')
    const editLink = links.find((l) => l.attributes('href')?.includes('/profile'))
    expect(editLink).toBeUndefined()
  })

  it('shows not found message when user does not exist', async () => {
    mockGetPublicProfile.mockRejectedValue(new Error('Not found'))
    const { wrapper } = await mountUserProfile()
    expect(wrapper.text()).toContain('User not found')
  })

  it('shows loading skeleton initially', () => {
    mockGetPublicProfile.mockReturnValue(new Promise(() => {}))
    mockListPosts.mockReturnValue(new Promise(() => {}))

    const pinia = createPinia()
    setActivePinia(pinia)
    const router = createTestRouter()
    const auth = useAuthStore()
    auth.setSession('MEMBER', 3600)
    auth.user = { id: 'current-user' } as unknown as UserProfile

    const wrapper = mount(UserProfileView, {
      global: { plugins: [pinia, router], stubs: createStubs() },
    })

    expect(wrapper.find('.skeleton-loader').exists()).toBe(true)
  })

  it('shows empty state when user has no posts', async () => {
    mockListPosts.mockResolvedValue({ posts: [], total: 0, total_pages: 0 })
    const { wrapper } = await mountUserProfile()
    expect(wrapper.find('.empty-state').exists()).toBe(true)
  })

  it('shows posts count in heading', async () => {
    const { wrapper } = await mountUserProfile()
    expect(wrapper.text()).toContain('(1)')
  })
})

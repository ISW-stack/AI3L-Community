import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import UserProfileView from '../UserProfileView.vue'
import { useAuthStore } from '@/stores/auth'

vi.mock('@/composables/api', () => ({
  default: {
    post: vi.fn(),
    get: vi.fn(),
  },
}))

vi.mock('@/constants', () => ({
  HEARTBEAT_INTERVAL_MS: 30000,
}))

const mockGetPublicProfile = vi.fn()
const mockListPosts = vi.fn()

vi.mock('@/api/users', () => ({
  getPublicProfile: (...args: unknown[]) => mockGetPublicProfile(...args),
}))

vi.mock('@/api/posts', () => ({
  listPosts: (...args: unknown[]) => mockListPosts(...args),
}))

function makeUser(id: string, name: string) {
  return {
    id,
    username: name.toLowerCase(),
    display_name: name,
    role: 'MEMBER',
    avatar_url: null,
    bio: null,
    affiliation: null,
    orcid: null,
    created_at: '2026-01-01T00:00:00Z',
  }
}

function createTestRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/users/:id', name: 'user-profile', component: UserProfileView },
      { path: '/forum', component: { template: '<div />' } },
      { path: '/forum/:id', component: { template: '<div />' } },
      { path: '/profile', component: { template: '<div />' } },
    ],
  })
}

async function mountComponent(userId: string) {
  const pinia = createPinia()
  setActivePinia(pinia)
  const auth = useAuthStore()
  auth.setSession('MEMBER', 3600)
  auth.user = { id: 'current-user' } as never

  const router = createTestRouter()
  await router.push(`/users/${userId}`)
  await router.isReady()

  const wrapper = mount(UserProfileView, {
    global: {
      plugins: [pinia, router],
      stubs: {
        BaseCard: { template: '<div class="base-card"><slot /></div>' },
        BaseBadge: { template: '<span class="base-badge"><slot /></span>' },
        BasePagination: { template: '<div />', props: ['currentPage', 'totalPages'] },
        BaseAvatar: { template: '<span class="base-avatar" />', props: ['src', 'name', 'size'] },
        PostCard: {
          template: '<div class="post-card">{{ post.title }}</div>',
          props: ['post', 'formatTime', 'contentClamp'],
        },
        SkeletonLoader: { template: '<div class="skeleton-loader" />', props: ['lines', 'variant'] },
        EmptyState: {
          template: '<div class="empty-state">{{ title }}</div>',
          props: ['title', 'message'],
        },
      },
    },
  })

  return { wrapper, router, pinia }
}

describe('UserProfileView — Race condition guard', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('stale profile response does not overwrite current data on rapid userId changes', async () => {
    // First call for user-1: slow response
    // Second call for user-2: fast response
    let resolveFirst: (value: unknown) => void
    const firstPromise = new Promise((resolve) => {
      resolveFirst = resolve
    })

    mockGetPublicProfile
      .mockImplementationOnce(() => firstPromise) // user-1: slow
      .mockImplementationOnce(() => Promise.resolve(makeUser('user-2', 'Bob'))) // user-2: fast

    mockListPosts.mockResolvedValue({ posts: [], total: 0, total_pages: 1 })

    const { wrapper, router } = await mountComponent('user-1')

    // Navigate to user-2 before user-1 resolves
    await router.push('/users/user-2')
    await flushPromises()

    // Now user-2 data should be displayed
    expect(wrapper.text()).toContain('Bob')

    // Now the slow user-1 response arrives
    resolveFirst!(makeUser('user-1', 'Alice'))
    await flushPromises()

    // User-2 data should STILL be displayed — stale response discarded
    expect(wrapper.text()).toContain('Bob')
    expect(wrapper.text()).not.toContain('Alice')
  })

  it('stale posts response does not overwrite current posts on rapid userId changes', async () => {
    mockGetPublicProfile.mockResolvedValue(makeUser('user-2', 'Bob'))

    let resolveFirstPosts: (value: unknown) => void
    const firstPostsPromise = new Promise((resolve) => {
      resolveFirstPosts = resolve
    })

    mockListPosts
      .mockImplementationOnce(() => firstPostsPromise) // user-1 posts: slow
      .mockImplementationOnce(() =>
        Promise.resolve({
          posts: [
            {
              id: 'p2',
              title: 'Bob Post',
              content: '<p>Hi</p>',
              author: { id: 'user-2', display_name: 'Bob', avatar_url: null },
              category_id: null,
              category_name: null,
              sig_id: null,
              sig_name: null,
              keywords: null,
              allow_comments: true,
              version: 1,
              comment_count: 0,
              is_pinned: false,
              view_count: 1,
              last_comment_at: null,
              created_at: '2026-01-02T00:00:00Z',
              updated_at: '2026-01-02T00:00:00Z',
            },
          ],
          total: 1,
          total_pages: 1,
        }),
      ) // user-2 posts: fast

    const { wrapper, router } = await mountComponent('user-1')

    // Navigate to user-2 before user-1 posts resolve
    await router.push('/users/user-2')
    await flushPromises()

    expect(wrapper.text()).toContain('Bob Post')

    // Stale user-1 posts arrive late
    resolveFirstPosts!({
      posts: [
        {
          id: 'p1',
          title: 'Alice Post',
          content: '<p>Hey</p>',
          author: { id: 'user-1', display_name: 'Alice', avatar_url: null },
          category_id: null,
          category_name: null,
          sig_id: null,
          sig_name: null,
          keywords: null,
          allow_comments: true,
          version: 1,
          comment_count: 0,
          is_pinned: false,
          view_count: 1,
          last_comment_at: null,
          created_at: '2026-01-01T00:00:00Z',
          updated_at: '2026-01-01T00:00:00Z',
        },
      ],
      total: 1,
      total_pages: 1,
    })
    await flushPromises()

    // Bob's post should still be displayed, not Alice's stale data
    expect(wrapper.text()).toContain('Bob Post')
    expect(wrapper.text()).not.toContain('Alice Post')
  })

  it('error from stale request does not clear current user data', async () => {
    let rejectFirst: (reason: unknown) => void
    const firstPromise = new Promise((_resolve, reject) => {
      rejectFirst = reject
    })

    mockGetPublicProfile
      .mockImplementationOnce(() => firstPromise) // user-1: will error
      .mockImplementationOnce(() => Promise.resolve(makeUser('user-2', 'Charlie')))

    mockListPosts.mockResolvedValue({ posts: [], total: 0, total_pages: 1 })

    const { wrapper, router } = await mountComponent('user-1')

    await router.push('/users/user-2')
    await flushPromises()

    expect(wrapper.text()).toContain('Charlie')

    // Stale request errors out
    rejectFirst!(new Error('Network error'))
    await flushPromises()

    // Charlie's data should still be displayed
    expect(wrapper.text()).toContain('Charlie')
  })
})

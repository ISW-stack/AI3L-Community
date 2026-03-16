import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import QADetailView from '../QADetailView.vue'
import { useAuthStore } from '@/stores/auth'

const mockGetPost = vi.fn()
const mockDeletePost = vi.fn()
const mockListComments = vi.fn()
const mockCreateComment = vi.fn()
const mockMarkBestAnswer = vi.fn()
const mockUnmarkBestAnswer = vi.fn()
const mockVoteOnAnswer = vi.fn()

vi.mock('@/api/posts', () => ({
  getPost: (...args: unknown[]) => mockGetPost(...args),
  deletePost: (...args: unknown[]) => mockDeletePost(...args),
  listPosts: vi.fn(),
  searchPosts: vi.fn(),
}))

vi.mock('@/api/comments', () => ({
  listComments: (...args: unknown[]) => mockListComments(...args),
  createComment: (...args: unknown[]) => mockCreateComment(...args),
}))

vi.mock('@/api/qa', () => ({
  markBestAnswer: (...args: unknown[]) => mockMarkBestAnswer(...args),
  unmarkBestAnswer: (...args: unknown[]) => mockUnmarkBestAnswer(...args),
  voteOnAnswer: (...args: unknown[]) => mockVoteOnAnswer(...args),
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

const fakePost = {
  id: 'q1',
  title: 'How to use AI in education?',
  content: '<p>I want to know how AI can help.</p>',
  author: { id: 'u1', display_name: 'Alice', username: 'alice', avatar_url: null },
  category_name: 'General',
  keywords: ['AI', 'education'],
  allow_comments: true,
  version: 1,
  comment_count: 2,
  view_count: 10,
  answer_count: 2,
  best_answer_id: null,
  type: 'question',
  is_pinned: false,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
}

const fakeComments = {
  comments: [
    {
      id: 'c1',
      content: '<p>AI can help with tutoring.</p>',
      author: { id: 'u2', display_name: 'Bob', username: 'bob', avatar_url: null },
      parent_id: null,
      created_at: '2026-01-02T00:00:00Z',
      updated_at: '2026-01-02T00:00:00Z',
      mentions: [],
    },
  ],
  total: 1,
}

function createTestRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/qa/:id', component: QADetailView },
      { path: '/qa', component: { template: '<div />' } },
      { path: '/', component: { template: '<div />' } },
      { path: '/users/:id', component: { template: '<div />' } },
    ],
  })
}

function createStubs() {
  return {
    BaseCard: {
      template: '<div class="base-card"><slot /><slot name="footer" /></div>',
      props: ['hoverable', 'padding'],
    },
    BaseButton: {
      template: '<button :disabled="$attrs.disabled" @click="$emit(\'click\')"><slot /></button>',
      props: ['loading', 'variant', 'size'],
    },
    BaseAlert: { template: '<div class="base-alert"><slot /></div>', props: ['type'] },
    BaseBadge: {
      template: '<span class="base-badge"><slot /></span>',
      props: ['variant'],
    },
    BaseModal: {
      template: '<div class="base-modal" v-if="modelValue"><slot /><slot name="footer" /></div>',
      props: ['modelValue', 'title', 'size'],
    },
    BaseAvatar: { template: '<span class="base-avatar" />', props: ['src', 'name', 'size'] },
    BasePagination: {
      template: '<div class="base-pagination" />',
      props: ['currentPage', 'totalPages'],
    },
    BaseBreadcrumb: {
      template:
        '<nav class="base-breadcrumb"><span v-for="item in items" :key="item.label">{{ item.label }}</span></nav>',
      props: ['items'],
    },
    SkeletonLoader: { template: '<div class="skeleton-loader" />', props: ['lines', 'variant'] },
    EmptyState: {
      template: '<div class="empty-state">{{ message }}</div>',
      props: ['title', 'message'],
    },
    VoteButtons: {
      template: '<div class="vote-buttons" />',
      props: ['commentId', 'score', 'userVote', 'disabled'],
    },
    BestAnswerBadge: {
      template: '<div class="best-answer-badge" />',
      props: ['isOwner', 'isBest'],
    },
    TiptapEditor: { template: '<div class="tiptap-editor" />' },
    ArrowLeft: { template: '<span class="arrow-left" />', props: ['size'] },
  }
}

async function mountQADetail(options?: { role?: string; postData?: unknown }) {
  const { role = 'MEMBER', postData = fakePost } = options ?? {}
  const pinia = createPinia()
  setActivePinia(pinia)
  const router = createTestRouter()

  const auth = useAuthStore()
  auth.setSession(role, 3600)
  auth.user = {
    id: 'user1',
    username: 'testuser',
    display_name: 'Test User',
    role,
    bio: null,
    affiliation: null,
    orcid: null,
    avatar_url: null,
    is_banned: false,
    ban_reason: null,
  } as any

  await router.push('/qa/q1')
  await router.isReady()

  const wrapper = mount(QADetailView, {
    global: { plugins: [pinia, router], stubs: createStubs() },
  })
  await flushPromises()
  return { wrapper, auth, router }
}

describe('QADetailView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockGetPost.mockResolvedValue(fakePost)
    mockListComments.mockResolvedValue(fakeComments)
  })

  it('shows back link to Q&A list during loading', async () => {
    mockGetPost.mockReturnValue(new Promise(() => {}))
    const pinia = createPinia()
    setActivePinia(pinia)
    const router = createTestRouter()
    const auth = useAuthStore()
    auth.setSession('MEMBER', 3600)
    auth.user = { id: 'user1' } as any

    await router.push('/qa/q1')
    await router.isReady()

    const wrapper = mount(QADetailView, {
      global: { plugins: [pinia, router], stubs: createStubs() },
    })
    // Don't flush - keep it in loading state

    // router-link renders as <a> with href
    const links = wrapper.findAll('a')
    const backLink = links.find((l) => l.attributes('href')?.includes('/qa'))
    expect(backLink).toBeTruthy()
  })

  it('shows back link when post is not found', async () => {
    mockGetPost.mockRejectedValue(new Error('Not found'))
    const { wrapper } = await mountQADetail()
    const backLink = wrapper.find('a[href="/qa"]')
    expect(backLink.exists()).toBe(true)
  })

  it('shows breadcrumb when post is loaded', async () => {
    const { wrapper } = await mountQADetail()
    const breadcrumb = wrapper.find('.base-breadcrumb')
    expect(breadcrumb.exists()).toBe(true)
    expect(breadcrumb.text()).toContain('Q&A')
    expect(breadcrumb.text()).toContain('How to use AI in education?')
  })

  it('renders question title and content', async () => {
    const { wrapper } = await mountQADetail()
    expect(wrapper.text()).toContain('How to use AI in education?')
  })

  it('renders answers section', async () => {
    const { wrapper } = await mountQADetail()
    expect(wrapper.text()).toContain('1 Answer')
  })

  it('fetches post and comments on mount', async () => {
    await mountQADetail()
    expect(mockGetPost).toHaveBeenCalledWith('q1')
    expect(mockListComments).toHaveBeenCalled()
  })
})

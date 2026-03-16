import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import QADetailView from '../qa/QADetailView.vue'
import { useAuthStore } from '@/stores/auth'

// --- Mocks ---
const mockGetPost = vi.fn()
const mockListComments = vi.fn()

vi.mock('@/api/posts', () => ({
  getPost: (...args: unknown[]) => mockGetPost(...args),
  deletePost: vi.fn(),
  listPosts: vi.fn(),
  searchPosts: vi.fn(),
}))

vi.mock('@/api/comments', () => ({
  listComments: (...args: unknown[]) => mockListComments(...args),
  createComment: vi.fn(),
}))

vi.mock('@/api/qa', () => ({
  markBestAnswer: vi.fn(),
  unmarkBestAnswer: vi.fn(),
  voteOnAnswer: vi.fn(),
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
  title: 'Test question',
  content: '<p>Body</p>',
  author: { id: 'u1', display_name: 'Alice', username: 'alice', avatar_url: null },
  category_name: 'General',
  keywords: [],
  allow_comments: true,
  version: 1,
  comment_count: 0,
  view_count: 5,
  answer_count: 0,
  best_answer_id: null,
  type: 'question',
  is_pinned: false,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
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
    BaseBadge: { template: '<span class="base-badge"><slot /></span>', props: ['variant'] },
    BaseModal: {
      template: '<div class="base-modal" v-if="modelValue"><slot /><slot name="footer" /></div>',
      props: ['modelValue', 'title', 'size'],
    },
    BaseAvatar: { template: '<span class="base-avatar" />', props: ['src', 'name', 'size'] },
    BasePagination: { template: '<div class="base-pagination" />', props: ['currentPage', 'totalPages'] },
    BaseBreadcrumb: {
      template: '<nav class="base-breadcrumb"><span v-for="item in items" :key="item.label">{{ item.label }}</span></nav>',
      props: ['items'],
    },
    SkeletonLoader: { template: '<div class="skeleton-loader" />', props: ['lines', 'variant'] },
    EmptyState: { template: '<div class="empty-state">{{ message }}</div>', props: ['title', 'message'] },
    VoteButtons: { template: '<div class="vote-buttons" />', props: ['commentId', 'score', 'userVote', 'disabled'] },
    BestAnswerBadge: { template: '<div class="best-answer-badge" />', props: ['isOwner', 'isBest'] },
    TiptapEditor: {
      template: '<div class="tiptap-editor" data-testid="tiptap-editor" />',
      props: ['modelValue'],
    },
    ArrowLeft: { template: '<span class="arrow-left" />', props: ['size'] },
  }
}

describe('QADetailView — TipTap editor for new answers', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockGetPost.mockResolvedValue(fakePost)
    mockListComments.mockResolvedValue({ comments: [], total: 0 })
  })

  it('renders TiptapEditor instead of textarea for answer input', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const router = createTestRouter()

    const auth = useAuthStore()
    auth.setSession('MEMBER', 3600)
    auth.user = {
      id: 'u1',
      username: 'alice',
      display_name: 'Alice',
      role: 'MEMBER',
      bio: null,
      affiliation: null,
      orcid: null,
      avatar_url: null,
      is_banned: false,
      ban_reason: null,
    } as never

    await router.push('/qa/q1')
    await router.isReady()

    const wrapper = mount(QADetailView, {
      global: {
        plugins: [pinia, router],
        stubs: createStubs(),
      },
    })

    await flushPromises()

    // Should have TiptapEditor (rendered as stub with .tiptap-editor class), not a textarea
    expect(wrapper.find('.tiptap-editor').exists()).toBe(true)
    expect(wrapper.find('textarea').exists()).toBe(false)
  })
})

describe('AlbumPhotosView — no redundant onMounted fetch', () => {
  it('does not use onMounted; uses watch with immediate: true instead', async () => {
    // Static analysis: read the raw source to verify onMounted was removed
    const source = await import('../albums/AlbumPhotosView.vue?raw')
    const code = (source as { default: string }).default

    // Should not have onMounted call in the source
    expect(code).not.toMatch(/onMounted\s*\(/)
    // Should have watch with immediate: true as the replacement
    expect(code).toMatch(/immediate:\s*true/)
  })
})

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { ref, computed } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import PostDetailView from '../PostDetailView.vue'
import { useAuthStore } from '@/stores/auth'

// Mock the usePostDetail composable since it has extensive tests elsewhere
const mockUsePostDetail = vi.fn()

vi.mock('@/composables/usePostDetail', () => ({
  usePostDetail: (...args: unknown[]) => mockUsePostDetail(...args),
}))

vi.mock('@/composables/api', () => ({
  default: { get: vi.fn(), post: vi.fn() },
}))

vi.mock('@/constants', () => ({
  HEARTBEAT_INTERVAL_MS: 30000,
}))

vi.mock('dompurify', () => ({
  default: {
    sanitize: (html: string) => html,
  },
}))

vi.mock('@/utils/html', () => ({
  renderMentions: (html: string) => html,
  extractMentions: () => [],
}))

const fakePost = {
  id: 'post-1',
  title: 'Test Post Title',
  content: '<p>This is the post content</p>',
  created_at: '2026-01-01T00:00:00Z',
  comment_count: 2,
  view_count: 50,
  version: 1,
  is_pinned: false,
  allow_comments: true,
  keywords: ['ai', 'learning'],
  category_name: 'AI Research',
  last_comment_at: '2026-01-02T00:00:00Z',
  author: { id: 'u1', display_name: 'Alice', avatar_url: null },
}

const fakeCommentTree = [
  {
    root: {
      id: 'c1',
      content: 'Great post!',
      created_at: '2026-01-01T01:00:00Z',
      author: { id: 'u2', display_name: 'Bob', avatar_url: null },
      reactions: [],
      mentions: [],
    },
    replies: [
      {
        id: 'c2',
        content: 'Thanks!',
        created_at: '2026-01-01T02:00:00Z',
        author: { id: 'u1', display_name: 'Alice', avatar_url: null },
        reactions: [],
        mentions: [],
      },
    ],
  },
]

function buildMockPostDetail(overrides?: Record<string, any>) {
  return {
    post: ref(overrides && 'post' in overrides ? overrides.post : fakePost),
    loading: ref(overrides?.loading ?? false),
    editing: ref(false),
    editTitle: ref(''),
    editContent: ref(''),
    editSaving: ref(false),
    editMessage: ref(''),
    commentTree: ref(overrides?.commentTree ?? fakeCommentTree),
    commentPage: ref(1),
    commentTotalPages: ref(1),
    commentsTotal: ref(2),
    newComment: ref(''),
    commentSaving: ref(false),
    commentMessage: ref(''),
    inlineReplyTo: ref(null),
    inlineReplyContent: ref(''),
    editingComment: ref(null),
    editCommentContent: ref(''),
    editCommentSaving: ref(false),
    history: ref([]),
    showHistory: ref(false),
    showDeletePostConfirm: ref(false),
    showDeleteCommentConfirm: ref(false),
    showReportModal: ref(false),
    reportReason: ref(''),
    reportSaving: ref(false),
    reportMessage: ref(''),
    canReport: computed(() => overrides?.canReport ?? true),
    pinSaving: ref(false),
    canModify: computed(() => overrides?.canModify ?? false),
    contentSegments: computed(() => [{ type: 'html', content: fakePost.content }]),
    postContentRef: ref(null),
    goToCommentPage: vi.fn(),
    fetchHistory: vi.fn(),
    startEdit: vi.fn(),
    saveEdit: vi.fn(),
    deletePostHandler: vi.fn(),
    submitComment: vi.fn(),
    submitInlineReply: vi.fn(),
    confirmDeleteComment: vi.fn(),
    deleteCommentHandler: vi.fn(),
    canDeleteComment: vi.fn(() => false),
    submitReport: vi.fn(),
    handleTogglePin: vi.fn(),
    formatRelativeTime: (d: string) => `relative(${d})`,
    toggleReactionHandler: vi.fn(),
    getReactionCount: vi.fn(() => 0),
    hasReacted: vi.fn(() => false),
    canEditComment: vi.fn(() => false),
    startEditComment: vi.fn(),
    cancelEditComment: vi.fn(),
    saveEditComment: vi.fn(),
    handleReply: vi.fn(),
  }
}

function createTestRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/forum/:id', component: PostDetailView },
      { path: '/forum', component: { template: '<div />' } },
      { path: '/forum/create', component: { template: '<div />' } },
      { path: '/users/:id', component: { template: '<div />' } },
    ],
  })
}

function createStubs() {
  return {
    BaseCard: { template: '<div class="base-card"><slot /></div>', props: ['padding'] },
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
    BaseInput: {
      template: '<input class="base-input" />',
      props: ['modelValue', 'placeholder'],
    },
    BasePagination: {
      template: '<div class="base-pagination" />',
      props: ['currentPage', 'totalPages'],
    },
    BaseAvatar: {
      template: '<div class="base-avatar" />',
      props: ['src', 'name', 'size'],
    },
    SkeletonLoader: { template: '<div class="skeleton-loader" />', props: ['lines', 'variant'] },
    TiptapEditor: { template: '<div class="tiptap-editor" />', props: ['modelValue'] },
    SigShareCard: { template: '<div class="sig-share-card" />', props: ['sigId'] },
    FormShareCard: { template: '<div class="form-share-card" />', props: ['formId'] },
    FloatingCreateButton: { template: '<div class="fab" />', props: ['to'] },
  }
}

async function mountPostDetail(overrides?: Record<string, any>) {
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
  } as any

  const mockData = buildMockPostDetail(overrides)
  mockUsePostDetail.mockReturnValue(mockData)

  await router.push('/forum/post-1')
  await router.isReady()

  const wrapper = mount(PostDetailView, {
    global: { plugins: [pinia, router], stubs: createStubs() },
  })
  await flushPromises()
  return { wrapper, router, auth, mockData }
}

describe('PostDetailView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders post title', async () => {
    const { wrapper } = await mountPostDetail()
    expect(wrapper.text()).toContain('Test Post Title')
  })

  it('renders post content', async () => {
    const { wrapper } = await mountPostDetail()
    expect(wrapper.html()).toContain('This is the post content')
  })

  it('renders author name', async () => {
    const { wrapper } = await mountPostDetail()
    expect(wrapper.text()).toContain('Alice')
  })

  it('renders category badge', async () => {
    const { wrapper } = await mountPostDetail()
    expect(wrapper.text()).toContain('AI Research')
  })

  it('renders keywords', async () => {
    const { wrapper } = await mountPostDetail()
    expect(wrapper.text()).toContain('ai')
    expect(wrapper.text()).toContain('learning')
  })

  it('renders comment count and view count', async () => {
    const { wrapper } = await mountPostDetail()
    expect(wrapper.text()).toContain('2 comment')
    expect(wrapper.text()).toContain('50')
  })

  it('renders comment tree', async () => {
    const { wrapper } = await mountPostDetail()
    expect(wrapper.text()).toContain('Great post!')
    expect(wrapper.text()).toContain('Bob')
    expect(wrapper.text()).toContain('Thanks!')
  })

  it('shows loading skeleton when loading', async () => {
    const { wrapper } = await mountPostDetail({ loading: true, post: null })
    expect(wrapper.find('.skeleton-loader').exists()).toBe(true)
  })

  it('shows not found when post is null and not loading', async () => {
    const mockData = buildMockPostDetail({ post: null })
    mockData.loading.value = false
    mockUsePostDetail.mockReturnValue(mockData)

    const pinia = createPinia()
    setActivePinia(pinia)
    const router = createTestRouter()
    const auth = useAuthStore()
    auth.setSession('MEMBER', 3600)
    auth.user = { id: 'u1' } as any

    await router.push('/forum/post-1')
    await router.isReady()

    const wrapper = mount(PostDetailView, {
      global: { plugins: [pinia, router], stubs: createStubs() },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('Post not found')
  })

  it('shows edit and delete buttons when canModify is true', async () => {
    const { wrapper } = await mountPostDetail({ canModify: true })
    expect(wrapper.text()).toContain('Edit')
    expect(wrapper.text()).toContain('Delete')
  })

  it('hides edit and delete buttons when canModify is false', async () => {
    const { wrapper } = await mountPostDetail({ canModify: false })
    const buttons = wrapper.findAll('button')
    const editBtn = buttons.find((b) => b.text() === wrapper.vm.$t('Edit'))
    expect(editBtn).toBeUndefined()
  })

  it('shows report button when canReport is true', async () => {
    const { wrapper } = await mountPostDetail({ canReport: true })
    expect(wrapper.text()).toContain('Report')
  })

  it('shows comment input for authenticated non-guest user', async () => {
    const { wrapper } = await mountPostDetail()
    const textarea = wrapper.find('textarea')
    expect(textarea.exists()).toBe(true)
  })

  it('hides comment input when comments are disabled', async () => {
    const postNoComments = { ...fakePost, allow_comments: false }
    const { wrapper } = await mountPostDetail({ post: postNoComments })
    expect(wrapper.text()).toContain('Comments are disabled')
  })

  it('shows back to forum link', async () => {
    const { wrapper } = await mountPostDetail()
    const backLink = wrapper.findAll('a').find((l) => l.attributes('href')?.includes('/forum'))
    expect(backLink).toBeTruthy()
  })

  it('renders reaction buttons on comments', async () => {
    const { wrapper } = await mountPostDetail()
    // Reaction buttons render emoji: thumbs up, smile, cry
    const html = wrapper.html()
    const hasReactionEmoji =
      html.includes('\uD83D\uDC4D') || // thumbs up
      html.includes('\uD83D\uDE0A') || // smile
      html.includes('\uD83D\uDE22') || // cry
      html.includes('128077') ||
      html.includes('128522') ||
      html.includes('128546')
    expect(hasReactionEmoji).toBe(true)
  })

  it('renders floating create button', async () => {
    const { wrapper } = await mountPostDetail()
    expect(wrapper.find('.fab').exists()).toBe(true)
  })
})

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
  REACTIONS: ['LIKE', 'SMILE', 'CRY'] as const,
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

vi.mock('lucide-vue-next', async (importOriginal) => {
  const stub = { template: '<svg />' }
  return {
    ...((await importOriginal()) as Record<string, unknown>),
    Quote: stub,
    ChevronDown: stub,
    ChevronUp: stub,
    Pin: { name: 'Pin', template: '<svg data-testid="lucide-pin" />', props: ['size'] },
    Users: stub,
    UserPlus: stub,
    X: stub,
  }
})

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
      reaction_counts: null,
      user_reactions: null,
      mentions: [],
    },
    replies: [
      {
        id: 'c2',
        content: 'Thanks!',
        created_at: '2026-01-01T02:00:00Z',
        author: { id: 'u1', display_name: 'Alice', avatar_url: null },
        reaction_counts: null,
        user_reactions: null,
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
    isAuthor: computed(() => overrides?.isAuthor ?? false),
    canModify: computed(() => overrides?.canModify ?? false),
    coAuthors: ref(overrides?.coAuthors ?? []),
    citedBy: ref(overrides?.citedBy ?? []),
    citing: ref(overrides?.citing ?? []),
    citedByTotal: ref(overrides?.citedByTotal ?? 0),
    citingTotal: ref(overrides?.citingTotal ?? 0),
    contentSegments: computed(() => [{ type: 'html', content: fakePost.content }]),
    postContentRef: ref(null),
    goToCommentPage: vi.fn(),
    fetchHistory: vi.fn(),
    fetchCoAuthors: vi.fn(),
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
    cancelEdit: vi.fn(),
    cancelEditComment: vi.fn(),
    saveEditComment: vi.fn(),
    handleReply: vi.fn(),
    togglePostReactionHandler: vi.fn(),
    getPostReactionCount: vi.fn(() => 0),
    hasPostReacted: vi.fn(() => false),
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
    CoAuthorManager: { template: '<div class="co-author-manager" />', props: ['postId'] },
    CopyShareLinkButton: {
      template: '<button class="copy-share-link" :data-url="url">Copy Link</button>',
      props: ['url', 'label'],
    },
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

  it('renders reaction picker add button for authenticated user', async () => {
    const { wrapper } = await mountPostDetail()
    // ReactionPicker should render an "Add reaction" button for authenticated non-guest users
    const addBtns = wrapper.findAll('button[aria-label="Add reaction"]')
    // At least one (for post reactions); comments also have their own pickers
    expect(addBtns.length).toBeGreaterThanOrEqual(1)
  })

  it('shows forum breadcrumb when no fromSigId query param', async () => {
    const { wrapper } = await mountPostDetail()
    // Default breadcrumb shows "Forum" path
    const links = wrapper.findAll('a').map((a) => a.attributes('href'))
    expect(links).toContain('/forum')
    expect(links).not.toContain('/sigs')
  })

  it('shows SIG breadcrumb when fromSigId and fromSigName query params are present', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const router = createTestRouter()
    const auth = useAuthStore()
    auth.setSession('MEMBER', 3600)
    auth.user = { id: 'u1' } as any

    const mockData = buildMockPostDetail()
    mockUsePostDetail.mockReturnValue(mockData)

    await router.push('/forum/post-1?fromSigId=sig-42&fromSigName=NLP+Research')
    await router.isReady()

    const wrapper = mount(PostDetailView, {
      global: { plugins: [pinia, router], stubs: createStubs() },
    })
    await flushPromises()

    // Breadcrumb should link to /sigs and /sigs/sig-42
    const links = wrapper.findAll('a').map((a) => a.attributes('href'))
    expect(links).toContain('/sigs')
    expect(links.some((h) => h?.includes('/sigs/sig-42'))).toBe(true)
    // Should NOT link to /forum in the breadcrumb
    const breadcrumbForumLink = links.filter((h) => h === '/forum')
    expect(breadcrumbForumLink.length).toBe(0)
    // SIG name should appear as breadcrumb label
    expect(wrapper.text()).toContain('NLP Research')
  })

  it('renders floating create button', async () => {
    const { wrapper } = await mountPostDetail()
    expect(wrapper.find('.fab').exists()).toBe(true)
  })

  it('renders lucide Pin icon for pinned posts', async () => {
    const pinnedPost = { ...fakePost, is_pinned: true }
    const { wrapper } = await mountPostDetail({ post: pinnedPost })
    expect(wrapper.find('[data-testid="pin-icon"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="lucide-pin"]').exists()).toBe(true)
  })

  it('does not render pin icon for non-pinned posts', async () => {
    const { wrapper } = await mountPostDetail()
    expect(wrapper.find('[data-testid="pin-icon"]').exists()).toBe(false)
  })

  it('shows share button for authenticated user', async () => {
    const { wrapper } = await mountPostDetail()
    const shareBtn = wrapper.find('.copy-share-link')
    expect(shareBtn.exists()).toBe(true)
    expect(shareBtn.attributes('data-url')).toContain('/forum/post-1')
  })

  it('hides share button for unauthenticated user', async () => {
    localStorage.clear()
    const pinia = createPinia()
    setActivePinia(pinia)
    const router = createTestRouter()
    // Do NOT call setSession or set user — user is unauthenticated

    const mockData = buildMockPostDetail()
    mockUsePostDetail.mockReturnValue(mockData)

    await router.push('/forum/post-1')
    await router.isReady()

    const wrapper = mount(PostDetailView, {
      global: { plugins: [pinia, router], stubs: createStubs() },
    })
    await flushPromises()

    const shareBtn = wrapper.find('.copy-share-link')
    expect(shareBtn.exists()).toBe(false)
  })

  it('calls cancelEdit when cancel button is clicked in edit mode', async () => {
    const { wrapper, mockData } = await mountPostDetail({ canModify: true })
    // Enter editing mode
    mockData.editing.value = true
    await wrapper.vm.$nextTick()

    // Find and click the cancel button (secondary variant)
    const buttons = wrapper.findAll('button')
    const cancelBtn = buttons.find((b) => b.text().includes('Cancel'))
    expect(cancelBtn).toBeTruthy()
    await cancelBtn!.trigger('click')

    expect(mockData.cancelEdit).toHaveBeenCalled()
  })
})

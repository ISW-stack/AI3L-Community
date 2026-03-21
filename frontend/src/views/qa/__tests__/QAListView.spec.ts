import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import QAListView from '../QAListView.vue'
import { useAuthStore } from '@/stores/auth'
import type { Post } from '@/types'

const mockListPosts = vi.fn()
const mockSearchPosts = vi.fn()
const mockGetTrendingPosts = vi.fn()
const mockListCategories = vi.fn()

vi.mock('@/api/posts', () => ({
  listPosts: (...args: unknown[]) => mockListPosts(...args),
  searchPosts: (...args: unknown[]) => mockSearchPosts(...args),
  getTrendingPosts: (...args: unknown[]) => mockGetTrendingPosts(...args),
}))

vi.mock('@/api/categories', () => ({
  listCategories: (...args: unknown[]) => mockListCategories(...args),
}))

vi.mock('@/composables/api', () => ({
  default: { get: vi.fn(), post: vi.fn() },
}))

vi.mock('@/constants', () => ({
  HEARTBEAT_INTERVAL_MS: 30000,
}))

// ---------------------------------------------------------------------------
// Stub IntersectionObserver (not available in jsdom)
// ---------------------------------------------------------------------------
const mockIOObserve = vi.fn()
const mockIODisconnect = vi.fn()

class MockIntersectionObserver {
  observe = mockIOObserve
  disconnect = mockIODisconnect
  unobserve = vi.fn()
  constructor() {}
}

vi.stubGlobal('IntersectionObserver', MockIntersectionObserver)

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

function makeQuestion(overrides: Partial<Post> = {}): Post {
  return {
    id: 'q-1',
    title: 'Test Question',
    content: '<p>body</p>',
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    comment_count: 0,
    view_count: 0,
    is_pinned: false,
    keywords: [],
    category_id: null,
    category_name: null,
    sig_id: null,
    sig_name: null,
    allow_comments: true,
    version: 1,
    last_comment_at: null,
    reactions: null,
    type: 'question',
    citation_count: 0,
    answer_count: 0,
    best_answer_id: null,
    author: {
      id: 'user-1',
      username: 'alice',
      display_name: 'Alice',
      avatar_url: null,
    },
    ...overrides,
  } as Post
}

const fakeCategories = [
  { id: 'cat1', name: 'AI Research', post_count: 10 },
  { id: 'cat2', name: 'Language Learning', post_count: 5 },
]

const fakeTrending = [
  makeQuestion({ id: 'tq1', title: 'Trending Question', answer_count: 12 }),
]

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function createTestRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: { template: '<div />' } },
      { path: '/qa', component: QAListView },
      { path: '/qa/ask', component: { template: '<div />' } },
      { path: '/qa/:id', component: { template: '<div />' } },
    ],
  })
}

function createStubs() {
  return {
    BaseCard: { template: '<div class="base-card"><slot /></div>', props: ['hoverable'] },
    BaseBreadcrumb: { template: '<nav class="breadcrumb" />', props: ['items'] },
    SkeletonLoader: { template: '<div class="skeleton-loader" />', props: ['lines', 'variant'] },
    EmptyState: {
      template: '<div class="empty-state">{{ title }} {{ message }}</div>',
      props: ['title', 'message', 'actionLabel', 'actionTo'],
    },
    QACard: {
      template: '<div class="qa-card">{{ question.title }}</div>',
      props: ['question'],
    },
    FloatingCreateButton: { template: '<div class="fab" />', props: ['to'] },
    SearchPanel: {
      template:
        '<div class="search-panel"><input type="text" :value="keyword" @input="$emit(\'update:keyword\', $event.target.value); $emit(\'search-input\')" @keyup.enter="$emit(\'immediate-search\')" /><button class="search-btn" @click="$emit(\'immediate-search\')">Search</button><button class="advanced-btn" @click="$emit(\'toggle-advanced\')">Advanced</button></div>',
      props: [
        'keyword',
        'dateFrom',
        'dateTo',
        'logic',
        'showAdvanced',
        'isSearchLoading',
        'isSearching',
        'dateRangeInvalid',
        'placeholder',
      ],
      emits: [
        'update:keyword',
        'update:dateFrom',
        'update:dateTo',
        'update:logic',
        'search-input',
        'immediate-search',
        'toggle-advanced',
        'clear-search',
      ],
    },
    CategoryFilter: {
      template:
        '<div class="category-filter"><button v-for="cat in categories" :key="cat.id" @click="$emit(\'select\', cat.id)">{{ cat.name }} ({{ cat.post_count }})</button></div>',
      props: ['categories', 'activeCategory', 'mode', 'allLabel'],
      emits: ['select'],
    },
    SortControls: {
      template:
        '<div class="sort-controls"><button v-for="opt in options" :key="opt.value" @click="$emit(\'select\', opt.value)">{{ opt.label }}</button></div>',
      props: ['currentSort', 'options', 'activeCategoryName'],
      emits: ['select'],
    },
    TrendingSidebar: {
      template:
        '<div class="trending-sidebar" v-if="posts.length"><span v-for="p in posts" :key="p.id">{{ p.title }}</span></div>',
      props: ['posts', 'title', 'linkPrefix'],
    },
  }
}

async function mountView(
  questions: Post[] = [],
  authOverrides: { role?: string; userId?: string } = {},
) {
  const pinia = createPinia()
  setActivePinia(pinia)

  if (authOverrides.role) {
    localStorage.setItem('role', authOverrides.role)
    localStorage.setItem('expiresAt', String(Date.now() + 3600_000))
  }
  const auth = useAuthStore()
  if (authOverrides.userId) {
    auth.user = {
      id: authOverrides.userId,
      username: 'testuser',
      display_name: 'Test User',
      role: authOverrides.role ?? 'MEMBER',
      bio: null,
      affiliation: null,
      orcid: null,
      avatar_url: null,
      preferred_language: 'en',
      is_banned: false,
      ban_reason: null,
      created_at: new Date().toISOString(),
    }
  }

  mockListPosts.mockResolvedValue({
    posts: questions,
    next_cursor: null,
    has_more: false,
  })

  const router = createTestRouter()
  await router.push('/qa')
  await router.isReady()

  const wrapper = mount(QAListView, {
    global: { plugins: [pinia, router], stubs: createStubs() },
  })
  await flushPromises()
  return { wrapper, router }
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('QAListView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.useFakeTimers()
    localStorage.clear()
    mockListPosts.mockResolvedValue({ posts: [], next_cursor: null, has_more: false })
    mockListCategories.mockResolvedValue(fakeCategories)
    mockGetTrendingPosts.mockResolvedValue(fakeTrending)
    mockSearchPosts.mockResolvedValue({ posts: [], next_cursor: null, has_more: false })
    mockIOObserve.mockClear()
    mockIODisconnect.mockClear()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('renders the Q&A heading', async () => {
    const { wrapper } = await mountView()
    expect(wrapper.text()).toContain('Q&A')
  })

  it('fetches categories and trending on mount', async () => {
    await mountView()
    expect(mockListCategories).toHaveBeenCalled()
    expect(mockGetTrendingPosts).toHaveBeenCalled()
  })

  it('calls listPosts with type: question', async () => {
    await mountView()
    expect(mockListPosts).toHaveBeenCalledWith(expect.objectContaining({ type: 'question' }))
  })

  it('shows empty state when no questions', async () => {
    const { wrapper } = await mountView([])
    expect(wrapper.find('.empty-state').exists()).toBe(true)
    expect(wrapper.text()).toContain('No questions yet')
  })

  it('renders question cards when questions exist', async () => {
    const questions = [
      makeQuestion({ id: 'q-1', title: 'First Question' }),
      makeQuestion({ id: 'q-2', title: 'Second Question' }),
    ]
    const { wrapper } = await mountView(questions)
    const cards = wrapper.findAll('.qa-card')
    expect(cards.length).toBe(2)
    expect(cards[0].text()).toContain('First Question')
    expect(cards[1].text()).toContain('Second Question')
  })

  it('shows "Ask a Question" button for authenticated members', async () => {
    const { wrapper } = await mountView([], { role: 'MEMBER', userId: 'user-1' })
    expect(wrapper.find('.fab').exists()).toBe(true)
  })

  it('does not show FloatingCreateButton for guests', async () => {
    const { wrapper } = await mountView([])
    // No auth overrides → not authenticated → no FAB
    expect(wrapper.find('.fab').exists()).toBe(false)
  })

  it('renders search panel', async () => {
    const { wrapper } = await mountView()
    expect(wrapper.find('.search-panel').exists()).toBe(true)
  })

  it('renders sort controls with Q&A options', async () => {
    const { wrapper } = await mountView()
    expect(wrapper.text()).toContain('Newest')
    expect(wrapper.text()).toContain('Oldest')
    expect(wrapper.text()).toContain('Most Answers')
    expect(wrapper.text()).toContain('Unanswered')
  })

  it('renders category sidebar buttons', async () => {
    const { wrapper } = await mountView()
    expect(wrapper.text()).toContain('AI Research')
    expect(wrapper.text()).toContain('Language Learning')
  })

  it('renders trending questions sidebar', async () => {
    const { wrapper } = await mountView()
    expect(wrapper.text()).toContain('Trending Question')
  })

  it('EmptyState action-to points to /qa/ask (not /qa/create)', async () => {
    const { wrapper } = await mountView([])
    const html = wrapper.html()
    expect(html).not.toContain('/qa/create')
  })

  it('triggers search on enter key', async () => {
    const { wrapper } = await mountView()
    vi.clearAllMocks()
    mockSearchPosts.mockResolvedValue({ posts: [], next_cursor: null, has_more: false })

    const searchInput = wrapper.find('input[type="text"]')
    await searchInput.setValue('language models')
    await searchInput.trigger('keyup.enter')
    await flushPromises()

    expect(mockSearchPosts).toHaveBeenCalledWith(
      expect.objectContaining({ keyword: 'language models', type: 'question' }),
    )
  })

  it('shows loading skeleton while fetch is pending', async () => {
    mockListPosts.mockReturnValue(new Promise(() => {}))

    const pinia = createPinia()
    setActivePinia(pinia)
    const router = createTestRouter()
    await router.push('/qa')
    await router.isReady()

    const wrapper = mount(QAListView, {
      global: { plugins: [pinia, router], stubs: createStubs() },
    })
    await flushPromises()

    expect(wrapper.find('.skeleton-loader').exists()).toBe(true)
  })

  it('IntersectionObserver is observed on the sentinel element', async () => {
    await mountView()
    expect(mockIOObserve).toHaveBeenCalledTimes(1)
  })

  it('selects category filter and refetches', async () => {
    const { wrapper } = await mountView()
    vi.clearAllMocks()
    mockListPosts.mockResolvedValue({ posts: [], next_cursor: null, has_more: false })

    const catButtons = wrapper.findAll('button').filter((b) => b.text().includes('AI Research'))
    expect(catButtons.length).toBeGreaterThan(0)
    await catButtons[0].trigger('click')
    await flushPromises()

    expect(mockListPosts).toHaveBeenCalledWith(expect.objectContaining({ category_id: 'cat1' }))
  })

  it('shows "no more questions" text when has_more is false and questions exist', async () => {
    const questions = [makeQuestion({ id: 'q-1', title: 'A Question' })]
    const { wrapper } = await mountView(questions)
    expect(wrapper.text()).toContain('No more questions')
  })

  it('does NOT show "no more questions" when there are no questions', async () => {
    const { wrapper } = await mountView([])
    expect(wrapper.text()).not.toContain('No more questions')
  })

  it('loadMore appends questions via IntersectionObserver callback', async () => {
    // Capture the IntersectionObserver callback
    let ioCallback: IntersectionObserverCallback | null = null
    vi.stubGlobal(
      'IntersectionObserver',
      class {
        observe = vi.fn()
        disconnect = vi.fn()
        unobserve = vi.fn()
        constructor(cb: IntersectionObserverCallback) {
          ioCallback = cb
        }
      },
    )

    const initialQuestions = [
      makeQuestion({ id: 'q-1', title: 'First Question' }),
      makeQuestion({ id: 'q-2', title: 'Second Question' }),
    ]

    // Set up initial response with cursor for more pages
    mockListPosts.mockResolvedValue({
      posts: initialQuestions,
      next_cursor: 'cursor-qa',
      has_more: true,
    })

    const pinia = createPinia()
    setActivePinia(pinia)
    const router = createTestRouter()
    await router.push('/qa')
    await router.isReady()

    const wrapper = mount(QAListView, {
      global: { plugins: [pinia, router], stubs: createStubs() },
    })
    await flushPromises()
    expect(wrapper.findAll('.qa-card').length).toBe(2)

    // Override the mock for the page 2 response
    mockListPosts.mockResolvedValue({
      posts: [makeQuestion({ id: 'q-3', title: 'Third Question' })],
      next_cursor: null,
      has_more: false,
    })

    // Simulate sentinel entering viewport
    expect(ioCallback).not.toBeNull()
    ioCallback!([{ isIntersecting: true } as IntersectionObserverEntry], {} as IntersectionObserver)
    await flushPromises()

    expect(wrapper.findAll('.qa-card').length).toBe(3)
    expect(wrapper.text()).toContain('Third Question')

    // Restore the original mock
    vi.stubGlobal('IntersectionObserver', MockIntersectionObserver)
  })

  it('right sidebar is hidden below lg breakpoint', async () => {
    const { wrapper } = await mountView()
    const asides = wrapper.findAll('aside')
    expect(asides.length).toBeGreaterThan(0)
    const rightSidebar = asides[0]
    expect(rightSidebar.classes()).toContain('hidden')
    expect(rightSidebar.classes()).toContain('lg:block')
  })
})

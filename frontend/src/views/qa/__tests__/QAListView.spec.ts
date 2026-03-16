import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import QAListView from '../QAListView.vue'
import { useAuthStore } from '../../../stores/auth'
import type { Post } from '../../../types'

vi.mock('@/api/posts', () => ({
  listPosts: vi.fn(),
}))

vi.mock('@/components/SkeletonLoader.vue', () => ({
  default: { template: '<div class="skeleton" />' },
}))

vi.mock('@/components/EmptyState.vue', () => ({
  default: {
    props: ['title', 'message', 'actionLabel', 'actionTo'],
    template: '<div class="empty-state">{{ title }} {{ message }}</div>',
  },
}))

vi.mock('@/components/base/BaseButton.vue', () => ({
  default: {
    template: '<button><slot /></button>',
  },
}))

vi.mock('@/components/base/BasePagination.vue', () => ({
  default: {
    props: ['currentPage', 'totalPages'],
    template: '<div class="pagination" />',
  },
}))

vi.mock('@/components/qa/QACard.vue', () => ({
  default: {
    props: ['question'],
    template: '<div class="qa-card">{{ question.title }}</div>',
  },
}))

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

function createTestRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: { template: '<div />' } },
      { path: '/qa', component: { template: '<div />' } },
      { path: '/qa/create', component: { template: '<div />' } },
      { path: '/qa/:id', component: { template: '<div />' } },
    ],
  })
}

async function mountView(
  questions: Post[] = [],
  authOverrides: { role?: string; userId?: string } = {},
) {
  const { listPosts } = await import('@/api/posts')
  const mockedListPosts = vi.mocked(listPosts)
  mockedListPosts.mockResolvedValue({
    posts: questions,
    total: questions.length,
    has_more: false,
  })

  const router = createTestRouter()
  await router.push('/qa')
  await router.isReady()

  const pinia = createPinia()
  setActivePinia(pinia)

  useAuthStore()
  if (authOverrides.role) {
    localStorage.setItem('role', authOverrides.role)
    localStorage.setItem('expiresAt', String(Date.now() + 3600_000))
  }
  const pinia2 = createPinia()
  setActivePinia(pinia2)
  const auth2 = useAuthStore()
  if (authOverrides.userId) {
    auth2.user = {
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

  const wrapper = mount(QAListView, {
    global: { plugins: [pinia2, router] },
  })

  await flushPromises()
  return { wrapper, mockedListPosts }
}

describe('QAListView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    vi.clearAllMocks()
  })

  it('renders the Q&A heading', async () => {
    const { wrapper } = await mountView()
    expect(wrapper.text()).toContain('Q&A')
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
    expect(wrapper.text()).toContain('Ask a Question')
  })

  it('calls listPosts with type: question', async () => {
    const { mockedListPosts } = await mountView()
    expect(mockedListPosts).toHaveBeenCalledWith(expect.objectContaining({ type: 'question' }))
  })

  it('shows question count when questions exist', async () => {
    const questions = [
      makeQuestion({ id: 'q-1' }),
      makeQuestion({ id: 'q-2' }),
      makeQuestion({ id: 'q-3' }),
    ]
    const { wrapper } = await mountView(questions)
    expect(wrapper.text()).toContain('3 questions')
  })

  it('shows singular "question" for count 1', async () => {
    const questions = [makeQuestion({ id: 'q-1' })]
    const { wrapper } = await mountView(questions)
    expect(wrapper.text()).toContain('1 question')
  })
})

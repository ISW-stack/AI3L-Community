import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import QACard from '../QACard.vue'
import type { Post } from '../../../types'

vi.mock('@/components/base/BaseCard.vue', () => ({
  default: { props: ['hoverable'], template: '<div><slot /></div>' },
}))

vi.mock('@/components/base/BaseBadge.vue', () => ({
  default: {
    props: ['variant'],
    template: '<span class="base-badge"><slot /></span>',
  },
}))

vi.mock('lucide-vue-next', () => ({
  MessageCircle: { name: 'MessageCircle', template: '<svg data-testid="message-icon" />' },
}))

function createTestRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: { template: '<div />' } },
      { path: '/qa/:id', name: 'qa-detail', component: { template: '<div />' } },
    ],
  })
}

function makeQuestion(overrides: Partial<Post> = {}): Post {
  return {
    id: 'q-1',
    title: 'How does AI work?',
    content: '<p>I want to understand AI</p>',
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    comment_count: 2,
    view_count: 15,
    is_pinned: false,
    keywords: ['AI', 'learning'],
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
    answer_count: 3,
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

function mountCard(question: Post) {
  const router = createTestRouter()
  return mount(QACard, {
    props: { question },
    global: { plugins: [router] },
  })
}

describe('QACard', () => {
  it('renders the question title', () => {
    const wrapper = mountCard(makeQuestion({ title: 'How does AI work?' }))
    expect(wrapper.text()).toContain('How does AI work?')
  })

  it('renders the author display name', () => {
    const wrapper = mountCard(
      makeQuestion({
        author: { id: 'u1', username: 'bob', display_name: 'Bob Smith', avatar_url: null },
      }),
    )
    expect(wrapper.text()).toContain('Bob Smith')
  })

  it('shows answer count', () => {
    const wrapper = mountCard(makeQuestion({ answer_count: 5 }))
    expect(wrapper.text()).toContain('5')
    expect(wrapper.text()).toContain('answers')
  })

  it('shows singular "answer" for count 1', () => {
    const wrapper = mountCard(makeQuestion({ answer_count: 1 }))
    expect(wrapper.text()).toContain('1')
    expect(wrapper.text()).toContain('answer')
    // Ensure it does not say "answers" (plural)
    const text = wrapper.text()
    // The text should contain "answer" but followed by the end or non-s character
    expect(text).toMatch(/1\s*answer(?!s)/)
  })

  it('shows "Answered" badge when best_answer_id is set', () => {
    const wrapper = mountCard(makeQuestion({ best_answer_id: 'comment-1' }))
    expect(wrapper.text()).toContain('Answered')
  })

  it('shows "Unanswered" badge when best_answer_id is null', () => {
    const wrapper = mountCard(makeQuestion({ best_answer_id: null }))
    expect(wrapper.text()).toContain('Unanswered')
  })

  it('renders view count', () => {
    const wrapper = mountCard(makeQuestion({ view_count: 42 }))
    expect(wrapper.text()).toContain('42')
    expect(wrapper.text()).toContain('views')
  })

  it('renders keywords', () => {
    const wrapper = mountCard(makeQuestion({ keywords: ['AI', 'ML', 'NLP'] }))
    expect(wrapper.text()).toContain('AI')
    expect(wrapper.text()).toContain('ML')
    expect(wrapper.text()).toContain('NLP')
  })

  it('limits keywords to 5', () => {
    const keywords = ['a', 'b', 'c', 'd', 'e', 'f']
    const wrapper = mountCard(makeQuestion({ keywords }))
    expect(wrapper.text()).toContain('a')
    expect(wrapper.text()).toContain('e')
    expect(wrapper.text()).not.toContain('f')
  })

  it('links to /qa/{id}', () => {
    const wrapper = mountCard(makeQuestion({ id: 'q-42' }))
    const link = wrapper.find('a[href="/qa/q-42"]')
    expect(link.exists()).toBe(true)
  })

  it('renders category badge when category_name is set', () => {
    const wrapper = mountCard(makeQuestion({ category_name: 'AI Tools' }))
    const badges = wrapper.findAll('.base-badge')
    const categoryBadge = badges.find((b) => b.text() === 'AI Tools')
    expect(categoryBadge).toBeTruthy()
  })

  it('shows comment count with icon', () => {
    const wrapper = mountCard(makeQuestion({ comment_count: 7 }))
    expect(wrapper.text()).toContain('7')
    expect(wrapper.find('[data-testid="message-icon"]').exists()).toBe(true)
  })

  it('does not show comment icon when comment_count is 0', () => {
    const wrapper = mountCard(makeQuestion({ comment_count: 0 }))
    expect(wrapper.find('[data-testid="message-icon"]').exists()).toBe(false)
  })

  it('renders the green background on answer count when answered', () => {
    const wrapper = mountCard(makeQuestion({ best_answer_id: 'c-1', answer_count: 3 }))
    const answerDiv = wrapper.findAll('.min-w-\\[50px\\]')[1]
    expect(answerDiv.classes()).toContain('bg-green-50')
    expect(answerDiv.classes()).toContain('text-green-700')
  })
})

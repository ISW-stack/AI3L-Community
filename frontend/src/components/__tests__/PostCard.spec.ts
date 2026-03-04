import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import PostCard from '../PostCard.vue'
import type { Post } from '../../types'

vi.mock('@/components/base/BaseCard.vue', () => ({
  default: { template: '<div><slot /></div>' },
}))

vi.mock('@/components/base/BaseBadge.vue', () => ({
  default: {
    props: ['variant'],
    template: '<span class="base-badge"><slot /></span>',
  },
}))

vi.mock('@/components/base/BaseAvatar.vue', () => ({
  default: {
    props: ['src', 'name', 'size'],
    template: '<img :alt="name" />',
  },
}))

vi.mock('lucide-vue-next', () => ({
  Pin: { name: 'Pin', template: '<svg data-testid="pin-icon" />' },
  Eye: { name: 'Eye', template: '<svg data-testid="eye-icon" />' },
}))

function createTestRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: { template: '<div />' } },
      { path: '/forum/:id', name: 'post', component: { template: '<div />' } },
      { path: '/users/:id', name: 'user', component: { template: '<div />' } },
    ],
  })
}

function makePost(overrides: Partial<Post> = {}): Post {
  return {
    id: 'post-1',
    title: 'Test Post Title',
    content: '<p>Test <b>content</b></p>',
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    comment_count: 3,
    view_count: 42,
    is_pinned: false,
    keywords: [],
    category_id: null,
    category_name: null,
    sig_id: null,
    sig_name: null,
    allow_comments: true,
    version: 1,
    last_comment_at: null,
    author: {
      id: 'user-1',
      username: 'alice',
      display_name: 'Alice',
      avatar_url: null,
    },
    ...overrides,
  } as Post
}

function mountCard(post: Post, extra: Record<string, unknown> = {}) {
  const router = createTestRouter()
  const pinia = createPinia()
  setActivePinia(pinia)

  return mount(PostCard, {
    props: { post, ...extra },
    global: {
      plugins: [pinia, router],
    },
  })
}

describe('PostCard', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  describe('post title', () => {
    it('renders the post title', () => {
      const wrapper = mountCard(makePost({ title: 'Hello World' }))
      expect(wrapper.text()).toContain('Hello World')
    })
  })

  describe('author display name', () => {
    it('renders the author display name', () => {
      const wrapper = mountCard(
        makePost({
          author: { id: 'u1', username: 'bob', display_name: 'Bob Smith', avatar_url: null },
        }),
      )
      expect(wrapper.text()).toContain('Bob Smith')
    })
  })

  describe('content HTML stripping', () => {
    it('strips HTML tags and renders plain text', () => {
      const wrapper = mountCard(makePost({ content: '<p>Test <b>content</b></p>' }))
      expect(wrapper.text()).toContain('Test content')
      expect(wrapper.html()).not.toContain('<p>Test')
    })
  })

  describe('pinned indicator', () => {
    it('shows "Pinned" text when is_pinned is true', () => {
      const wrapper = mountCard(makePost({ is_pinned: true }))
      expect(wrapper.text()).toContain('Pinned')
    })

    it('does not show "Pinned" text when is_pinned is false', () => {
      const wrapper = mountCard(makePost({ is_pinned: false }))
      expect(wrapper.text()).not.toContain('Pinned')
    })

    it('renders Pin icon when post is pinned', () => {
      const wrapper = mountCard(makePost({ is_pinned: true }))
      const pinIcon = wrapper.find('[data-testid="pin-icon"]')
      expect(pinIcon.exists()).toBe(true)
    })
  })

  describe('category badge', () => {
    it('shows a category badge when category_name is set', () => {
      const wrapper = mountCard(makePost({ category_name: 'AI Tools' }))
      const badges = wrapper.findAll('.base-badge')
      const categoryBadge = badges.find((b) => b.text() === 'AI Tools')
      expect(categoryBadge).toBeTruthy()
      expect(categoryBadge!.exists()).toBe(true)
    })

    it('does not show a category badge when category_name is null', () => {
      const wrapper = mountCard(makePost({ category_name: null }))
      const badges = wrapper.findAll('.base-badge')
      const categoryBadge = badges.find((b) => b.text() === 'AI Tools')
      expect(categoryBadge).toBeUndefined()
    })
  })

  describe('keywords', () => {
    it('renders keyword badges (up to 5)', () => {
      const keywords = ['alpha', 'beta', 'gamma', 'delta', 'epsilon', 'zeta']
      const wrapper = mountCard(makePost({ keywords }))
      const text = wrapper.text()
      expect(text).toContain('alpha')
      expect(text).toContain('beta')
      expect(text).toContain('gamma')
      expect(text).toContain('delta')
      expect(text).toContain('epsilon')
      expect(text).not.toContain('zeta')
    })

    it('renders nothing for keyword section when keywords list is empty', () => {
      const wrapper = mountCard(makePost({ keywords: [] }))
      const allBadges = wrapper.findAll('.base-badge')
      expect(allBadges.length).toBe(0)
    })
  })

  describe('comment count pluralization', () => {
    it('shows "3 comments" for comment_count = 3', () => {
      const wrapper = mountCard(makePost({ comment_count: 3 }))
      expect(wrapper.text()).toContain('3 comments')
    })

    it('shows "1 comment" (singular) for comment_count = 1', () => {
      const wrapper = mountCard(makePost({ comment_count: 1 }))
      expect(wrapper.text()).toContain('1 comment')
      expect(wrapper.text()).not.toContain('1 comments')
    })

    it('shows "0 comments" for comment_count = 0', () => {
      const wrapper = mountCard(makePost({ comment_count: 0 }))
      expect(wrapper.text()).toContain('0 comments')
    })
  })

  describe('view count', () => {
    it('renders the view count number', () => {
      const wrapper = mountCard(makePost({ view_count: 99 }))
      expect(wrapper.text()).toContain('99')
    })
  })

  describe('formatTime prop', () => {
    it('calls the custom formatTime function when provided and displays its result', () => {
      const formatTime = vi.fn().mockReturnValue('custom-time-string')
      const post = makePost({ created_at: '2024-01-01T00:00:00Z' })
      const wrapper = mountCard(post, { formatTime })
      expect(formatTime).toHaveBeenCalled()
      expect(wrapper.text()).toContain('custom-time-string')
    })
  })

  describe('defaultFormatTime', () => {
    it('returns "just now" for a timestamp less than 60 seconds ago', () => {
      const recentDate = new Date(Date.now() - 10_000).toISOString()
      const wrapper = mountCard(makePost({ created_at: recentDate }))
      expect(wrapper.text()).toContain('just now')
    })

    it('returns "Xm ago" for a timestamp a few minutes ago', () => {
      const fiveMinutesAgo = new Date(Date.now() - 5 * 60_000).toISOString()
      const wrapper = mountCard(makePost({ created_at: fiveMinutesAgo }))
      expect(wrapper.text()).toContain('5m ago')
    })

    it('returns "Xh ago" for a timestamp a few hours ago', () => {
      const twoHoursAgo = new Date(Date.now() - 2 * 60 * 60_000).toISOString()
      const wrapper = mountCard(makePost({ created_at: twoHoursAgo }))
      expect(wrapper.text()).toContain('2h ago')
    })

    it('returns "Xd ago" for a timestamp a few days ago', () => {
      const threeDaysAgo = new Date(Date.now() - 3 * 24 * 60 * 60_000).toISOString()
      const wrapper = mountCard(makePost({ created_at: threeDaysAgo }))
      expect(wrapper.text()).toContain('3d ago')
    })
  })

  describe('last reply time', () => {
    it('shows "Last reply ..." when last_comment_at is set', () => {
      const recentDate = new Date(Date.now() - 30_000).toISOString()
      const wrapper = mountCard(makePost({ last_comment_at: recentDate }))
      expect(wrapper.text()).toContain('Last reply')
    })

    it('does not show "Last reply" when last_comment_at is null', () => {
      const wrapper = mountCard(makePost({ last_comment_at: null }))
      expect(wrapper.text()).not.toContain('Last reply')
    })
  })

  describe('post link', () => {
    it('renders a router-link with href pointing to /forum/{post.id}', () => {
      const wrapper = mountCard(makePost({ id: 'post-42' }))
      const link = wrapper.find('a[href="/forum/post-42"]')
      expect(link.exists()).toBe(true)
    })
  })

  describe('author link', () => {
    it('renders a router-link with href pointing to /users/{author.id}', () => {
      const wrapper = mountCard(
        makePost({
          author: { id: 'user-99', username: 'carol', display_name: 'Carol', avatar_url: null },
        }),
      )
      const links = wrapper.findAll('a[href="/users/user-99"]')
      expect(links.length).toBeGreaterThanOrEqual(1)
    })
  })
})

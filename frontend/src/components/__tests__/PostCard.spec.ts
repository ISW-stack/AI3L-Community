import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import PostCard from '../PostCard.vue'
import { useAuthStore } from '../../stores/auth'
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
  MessageCircle: { name: 'MessageCircle', template: '<svg data-testid="message-icon" />' },
}))

vi.mock('@/api/posts', () => ({
  togglePostReaction: vi.fn(),
}))

vi.mock('dompurify', () => ({
  default: {
    sanitize: (html: string) => html,
  },
}))

function createTestRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: { template: '<div />' } },
      { path: '/forum/:id', name: 'post', component: { template: '<div />' } },
      { path: '/users/:id', name: 'user', component: { template: '<div />' } },
      { path: '/sigs/:id', name: 'sig', component: { template: '<div />' } },
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
    reactions: null,
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

function mountCardWithAuth(
  post: Post,
  authOverrides: { role?: string; userId?: string; isGuest?: boolean } = {},
) {
  const router = createTestRouter()
  const pinia = createPinia()
  setActivePinia(pinia)

  useAuthStore()
  // Set role in localStorage before mounting so computed properties work
  if (authOverrides.role) {
    localStorage.setItem('role', authOverrides.role)
    localStorage.setItem('expiresAt', String(Date.now() + 3600_000))
  }
  // Re-create pinia to pick up localStorage
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

  return mount(PostCard, {
    props: { post },
    global: {
      plugins: [pinia2, router],
    },
  })
}

describe('PostCard', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
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

  describe('content rendering', () => {
    it('renders sanitized HTML content with formatting preserved', () => {
      const wrapper = mountCard(makePost({ content: '<p>Test <b>content</b></p>' }))
      const previewDiv = wrapper.find('.post-preview-content')
      expect(previewDiv.exists()).toBe(true)
      // DOMPurify mock passes HTML through, so tags should be in rendered output
      expect(previewDiv.html()).toContain('<p>')
      expect(previewDiv.html()).toContain('<b>')
    })

    it('renders content via v-html (not text interpolation)', () => {
      const wrapper = mountCard(makePost({ content: '<p>Hello <em>world</em></p>' }))
      const previewDiv = wrapper.find('.post-preview-content')
      expect(previewDiv.html()).toContain('<em>')
    })
  })

  describe('show more / show less', () => {
    it('does not show toggle button when content fits within maxHeight', () => {
      const wrapper = mountCard(makePost({ content: '<p>Short</p>' }))
      const toggleBtn = wrapper.findAll('button').find((b) => b.text().includes('Show more'))
      expect(toggleBtn).toBeUndefined()
    })

    it('renders the content preview div with max-height style', () => {
      const wrapper = mountCard(makePost({ content: '<p>Content</p>' }))
      const previewDiv = wrapper.find('.post-preview-content')
      expect(previewDiv.exists()).toBe(true)
      // Default maxPreviewLines = 15, so maxHeight = 22.5rem
      expect(previewDiv.element.style.maxHeight).toBe('22.5rem')
    })

    it('respects custom maxPreviewLines prop', () => {
      const wrapper = mountCard(makePost({ content: '<p>Content</p>' }), {
        maxPreviewLines: 3,
      })
      const previewDiv = wrapper.find('.post-preview-content')
      expect(previewDiv.element.style.maxHeight).toBe('4.5rem')
    })

    it('toggles expanded state when button is clicked', async () => {
      const wrapper = mountCard(makePost({ content: '<p>Content</p>' }))
      const vm = wrapper.vm as unknown as { isExpanded: boolean; isOverflowing: boolean }

      // Simulate overflow
      vm.isOverflowing = true
      await nextTick()

      const toggleBtn = wrapper.findAll('button').find((b) => b.text().includes('Show more'))
      expect(toggleBtn).toBeTruthy()

      await toggleBtn!.trigger('click')
      expect(vm.isExpanded).toBe(true)

      // Now should show "Show less"
      await nextTick()
      const lessBtn = wrapper.findAll('button').find((b) => b.text().includes('Show less'))
      expect(lessBtn).toBeTruthy()
    })

    it('removes max-height when expanded', async () => {
      const wrapper = mountCard(makePost({ content: '<p>Content</p>' }))
      const vm = wrapper.vm as unknown as { isExpanded: boolean; isOverflowing: boolean }

      vm.isOverflowing = true
      vm.isExpanded = true
      await nextTick()

      const previewDiv = wrapper.find('.post-preview-content')
      expect(previewDiv.element.style.maxHeight).toBe('')
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

  describe('comment count', () => {
    it('shows comment count with icon for comment_count = 3', () => {
      const wrapper = mountCard(makePost({ comment_count: 3 }))
      expect(wrapper.text()).toContain('3')
      expect(wrapper.find('[data-testid="message-icon"]').exists()).toBe(true)
    })

    it('shows comment count for comment_count = 1', () => {
      const wrapper = mountCard(makePost({ comment_count: 1 }))
      expect(wrapper.text()).toContain('1')
    })

    it('shows 0 for comment_count = 0', () => {
      const wrapper = mountCard(makePost({ comment_count: 0 }))
      expect(wrapper.text()).toContain('0')
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

  describe('SIG context', () => {
    it('shows SIG name and link when sig_name is set', () => {
      const wrapper = mountCard(makePost({ sig_id: 'sig-1', sig_name: 'NLP Research' }))
      expect(wrapper.text()).toContain('NLP Research')
      const sigLink = wrapper.find('a[href="/sigs/sig-1"]')
      expect(sigLink.exists()).toBe(true)
    })

    it('does not show SIG context when sig_name is null', () => {
      const wrapper = mountCard(makePost({ sig_id: null, sig_name: null }))
      const sigLinks = wrapper
        .findAll('a')
        .filter((a) => a.attributes('href')?.startsWith('/sigs/'))
      expect(sigLinks.length).toBe(0)
    })
  })

  describe('image display', () => {
    it('shows full-width image when content contains an image', () => {
      const wrapper = mountCard(
        makePost({
          id: 'post-img-test',
          content: '<p>Hello</p><img src="https://example.com/img.jpg" />',
        }),
      )
      // The full-width image is rendered inside a router-link to the post
      // (separate from the v-html content preview)
      const imgLink = wrapper.find('a[href="/forum/post-img-test"]')
      expect(imgLink.exists()).toBe(true)
      // Find images with bg-surface-alt class (the standalone full-width image)
      const imgs = wrapper.findAll('img').filter((i) => i.html().includes('bg-surface-alt'))
      expect(imgs.length).toBe(1)
      expect(imgs[0].html()).toContain('w-full')
      expect(imgs[0].html()).toContain('max-h-80')
      expect(imgs[0].html()).toContain('object-cover')
    })

    it('does not show image when content has no image', () => {
      const wrapper = mountCard(makePost({ content: '<p>No images here</p>' }))
      // Only the avatar img should exist
      const imgs = wrapper.findAll('img')
      const contentImgs = imgs.filter((img) => img.attributes('alt') !== 'Alice')
      expect(contentImgs.length).toBe(0)
    })

    it('wraps image in a router-link to the post', () => {
      const wrapper = mountCard(
        makePost({
          id: 'post-img',
          content: '<p>With image</p><img src="https://example.com/pic.jpg" />',
        }),
      )
      const imgLink = wrapper.find('a[href="/forum/post-img"] img.w-full')
      expect(imgLink.exists()).toBe(true)
    })
  })

  describe('reactions', () => {
    it('shows reaction buttons for authenticated non-guest users', () => {
      const wrapper = mountCardWithAuth(makePost({ reactions: { LIKE: ['user-2'] } }), {
        role: 'MEMBER',
        userId: 'user-1',
      })
      const buttons = wrapper.findAll('button[aria-label]')
      expect(buttons.length).toBe(3) // LIKE, SMILE, CRY
    })

    it('shows reaction count when reactions exist', () => {
      const wrapper = mountCardWithAuth(makePost({ reactions: { LIKE: ['user-2', 'user-3'] } }), {
        role: 'MEMBER',
        userId: 'user-1',
      })
      const likeButton = wrapper.find('button[aria-label="React with LIKE"]')
      expect(likeButton.exists()).toBe(true)
      expect(likeButton.text()).toContain('2')
    })

    it('highlights reaction button when user has reacted', () => {
      const wrapper = mountCardWithAuth(makePost({ reactions: { LIKE: ['user-1'] } }), {
        role: 'MEMBER',
        userId: 'user-1',
      })
      const likeButton = wrapper.find('button[aria-label="React with LIKE"]')
      expect(likeButton.classes()).toContain('bg-brand-100')
      expect(likeButton.attributes('aria-pressed')).toBe('true')
    })

    it('does not highlight reaction button when user has not reacted', () => {
      const wrapper = mountCardWithAuth(makePost({ reactions: { LIKE: ['user-2'] } }), {
        role: 'MEMBER',
        userId: 'user-1',
      })
      const likeButton = wrapper.find('button[aria-label="React with LIKE"]')
      expect(likeButton.classes()).not.toContain('bg-brand-100')
      expect(likeButton.attributes('aria-pressed')).toBe('false')
    })

    it('calls togglePostReaction when reaction button is clicked', async () => {
      const { togglePostReaction } = await import('@/api/posts')
      const mockedToggle = vi.mocked(togglePostReaction)
      const postData = makePost({ reactions: null })
      mockedToggle.mockResolvedValue({ ...postData, reactions: { LIKE: ['user-1'] } })

      const wrapper = mountCardWithAuth(postData, { role: 'MEMBER', userId: 'user-1' })

      const likeButton = wrapper.find('button[aria-label="React with LIKE"]')
      await likeButton.trigger('click')

      expect(mockedToggle).toHaveBeenCalledWith('post-1', 'LIKE')
    })

    it('shows read-only reactions for guests when reactions exist', () => {
      const wrapper = mountCard(makePost({ reactions: { LIKE: ['user-2'], SMILE: ['user-3'] } }))
      // No interactive buttons (no aria-label buttons)
      const buttons = wrapper.findAll('button[aria-label]')
      expect(buttons.length).toBe(0)
      // Should show reaction counts as spans
      const reactionSpans = wrapper.findAll('span.rounded-full')
      expect(reactionSpans.length).toBeGreaterThanOrEqual(1)
    })

    it('does not show read-only reactions section when no reactions exist', () => {
      const wrapper = mountCard(makePost({ reactions: null }))
      const buttons = wrapper.findAll('button[aria-label]')
      expect(buttons.length).toBe(0)
    })

    it('does not show reaction buttons for guest users', () => {
      const wrapper = mountCardWithAuth(makePost({ reactions: { LIKE: ['user-2'] } }), {
        role: 'GUEST',
        userId: 'guest-1',
      })
      // Guest should not see interactive buttons
      const buttons = wrapper.findAll('button[aria-label]')
      expect(buttons.length).toBe(0)
    })
  })
})

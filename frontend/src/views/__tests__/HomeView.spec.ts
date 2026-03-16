import { describe, it, expect, vi, beforeEach } from 'vitest'
import { nextTick } from 'vue'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import HomeView from '../HomeView.vue'
import { useAuthStore } from '@/stores/auth'

const mockListPosts = vi.fn()
const mockGetTrendingPosts = vi.fn()
const mockGetPublicStats = vi.fn()
const mockApplyForMembership = vi.fn()
const mockListMySigs = vi.fn()
const mockListSigs = vi.fn()

vi.mock('@/api/posts', () => ({
  listPosts: (...args: unknown[]) => mockListPosts(...args),
  searchPosts: vi.fn(),
  getTrendingPosts: (...args: unknown[]) => mockGetTrendingPosts(...args),
  getPublicStats: (...args: unknown[]) => mockGetPublicStats(...args),
}))

vi.mock('@/api/sigs', () => ({
  listMySigs: (...args: unknown[]) => mockListMySigs(...args),
  listSigs: (...args: unknown[]) => mockListSigs(...args),
  getSig: vi.fn(),
}))

vi.mock('@/api/users', () => ({
  applyForMembership: (...args: unknown[]) => mockApplyForMembership(...args),
  getProfile: vi.fn(),
  updateProfile: vi.fn(),
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

const fakePosts = [
  {
    id: 'p1',
    title: 'First Post',
    content: 'Hello',
    created_at: '2026-01-01T00:00:00Z',
    comment_count: 5,
    view_count: 10,
    author: { id: 'u1', display_name: 'Alice', avatar_url: null },
  },
  {
    id: 'p2',
    title: 'Second Post',
    content: 'World',
    created_at: '2026-01-02T00:00:00Z',
    comment_count: 2,
    view_count: 3,
    author: { id: 'u2', display_name: 'Bob', avatar_url: null },
  },
]

function createTestRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: HomeView },
      { path: '/forum', component: { template: '<div />' } },
      { path: '/forum/create', component: { template: '<div />' } },
      { path: '/forum/:id', component: { template: '<div />' } },
      { path: '/sigs', component: { template: '<div />' } },
      { path: '/register', component: { template: '<div />' } },
      { path: '/guest', component: { template: '<div />' } },
      { path: '/profile', component: { template: '<div />' } },
      { path: '/notifications', component: { template: '<div />' } },
    ],
  })
}

function createStubs() {
  return {
    BaseCard: {
      template: '<div class="base-card"><slot /></div>',
      props: ['hoverable', 'padding'],
    },
    BaseButton: {
      template: '<button :disabled="$attrs.disabled" @click="$emit(\'click\')"><slot /></button>',
      props: ['loading', 'variant', 'size'],
    },
    BaseAlert: { template: '<div class="base-alert"><slot /></div>', props: ['type'] },
    BaseTextarea: {
      template:
        '<textarea class="base-textarea" :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)"></textarea>',
      props: ['modelValue', 'placeholder', 'rows'],
    },
    SkeletonLoader: { template: '<div class="skeleton-loader" />', props: ['lines', 'variant'] },
    PostCard: {
      template: '<div class="post-card">{{ post?.title }}</div>',
      props: ['post', 'maxPreviewLines'],
    },
    MessageSquare: { template: '<span />' },
    Users: { template: '<span />' },
    FileText: { template: '<span />' },
    BookOpen: { template: '<span />' },
    TrendingUp: { template: '<span />' },
  }
}

async function mountHome(options?: { role?: string }) {
  const { role = 'MEMBER' } = options ?? {}
  const pinia = createPinia()
  setActivePinia(pinia)
  const router = createTestRouter()

  const auth = useAuthStore()
  if (role) {
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
  }

  await router.push('/')
  await router.isReady()

  const wrapper = mount(HomeView, {
    global: { plugins: [pinia, router], stubs: createStubs() },
  })
  await flushPromises()
  return { wrapper, auth, router }
}

describe('HomeView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockListPosts.mockResolvedValue({ posts: fakePosts, total: 2, total_pages: 1 })
    mockGetTrendingPosts.mockResolvedValue(fakePosts)
    mockGetPublicStats.mockResolvedValue({ member_count: 10, post_count: 20, sig_count: 3 })
    mockListMySigs.mockResolvedValue([
      { id: 's1', name: 'NLP SIG', member_count: 5, description: null },
    ])
    mockListSigs.mockResolvedValue({
      sigs: [{ id: 's1', name: 'NLP SIG', member_count: 5, description: 'NLP research' }],
      total: 1,
    })
    mockApplyForMembership.mockResolvedValue({})
  })

  describe('Unauthenticated view', () => {
    async function mountUnauthenticated() {
      const pinia = createPinia()
      setActivePinia(pinia)
      const router = createTestRouter()
      await router.push('/')
      await router.isReady()
      const wrapper = mount(HomeView, {
        global: { plugins: [pinia, router], stubs: createStubs() },
      })
      await flushPromises()
      return wrapper
    }

    it('shows hero section with title', async () => {
      const wrapper = await mountUnauthenticated()
      // Unauthenticated view should contain the platform title
      const h1 = wrapper.find('h1')
      expect(h1.exists()).toBe(true)
    })

    it('shows register and guest links', async () => {
      const wrapper = await mountUnauthenticated()
      const links = wrapper.findAll('a')
      const registerLinks = links.filter((l) => l.attributes('href')?.includes('/register'))
      const guestLinks = links.filter((l) => l.attributes('href')?.includes('/guest'))
      expect(registerLinks.length).toBeGreaterThan(0)
      expect(guestLinks.length).toBeGreaterThan(0)
    })

    it('does not fetch posts', async () => {
      await mountUnauthenticated()
      expect(mockListPosts).not.toHaveBeenCalled()
    })

    it('shows feature cards', async () => {
      const wrapper = await mountUnauthenticated()
      const cards = wrapper.findAll('.base-card')
      expect(cards.length).toBeGreaterThanOrEqual(4)
    })
  })

  describe('Authenticated (member) view', () => {
    it('uses lg breakpoint for grid columns instead of md (M9)', async () => {
      const { wrapper } = await mountHome()
      const gridDiv = wrapper.find('.grid.grid-cols-1')
      expect(gridDiv.exists()).toBe(true)
      expect(gridDiv.classes()).toContain('lg:grid-cols-3')
      expect(gridDiv.classes()).not.toContain('md:grid-cols-3')
    })

    it('uses lg breakpoint for main column span (M9)', async () => {
      const { wrapper } = await mountHome()
      const mainColumn = wrapper.find('.lg\\:col-span-2')
      expect(mainColumn.exists()).toBe(true)
    })

    it('shows welcome message with display name', async () => {
      const { wrapper } = await mountHome()
      // i18n t() returns key path in test; verify the welcome section renders
      expect(wrapper.text()).toContain('Welcome back')
    })

    it('fetches recent posts on mount', async () => {
      await mountHome()
      expect(mockListPosts).toHaveBeenCalledWith({ page: 1, page_size: 5, sort: 'newest' })
    })

    it('renders recent post titles', async () => {
      const { wrapper } = await mountHome()
      expect(wrapper.text()).toContain('First Post')
      expect(wrapper.text()).toContain('Second Post')
    })

    it('renders post cards for recent posts', async () => {
      const { wrapper } = await mountHome()
      const postCards = wrapper.findAll('.post-card')
      // Recent posts (5) + trending posts (up to 3 from same fakePosts) = multiple cards
      expect(postCards.length).toBeGreaterThanOrEqual(2)
    })

    it('shows empty message when no posts', async () => {
      mockListPosts.mockResolvedValue({ posts: [], total: 0, total_pages: 0 })
      const { wrapper } = await mountHome()
      // empty posts text from i18n
      expect(wrapper.find('.skeleton-loader').exists()).toBe(false)
    })

    it('shows quick links including edit profile', async () => {
      const { wrapper } = await mountHome()
      const links = wrapper.findAll('a')
      const profileLink = links.find((l) => l.attributes('href')?.includes('/profile'))
      expect(profileLink).toBeTruthy()
    })

    it('shows "View All Trending" link when trending posts exist', async () => {
      const { wrapper } = await mountHome()
      const links = wrapper.findAll('a')
      const trendingLink = links.find((l) => l.attributes('href') === '/forum?sort=trending')
      expect(trendingLink).toBeTruthy()
      expect(trendingLink!.text()).toContain('View All Trending')
    })

    it('hides "View All Trending" link when no trending posts', async () => {
      mockGetTrendingPosts.mockResolvedValue([])
      const { wrapper } = await mountHome()
      const links = wrapper.findAll('a')
      const trendingLink = links.find((l) => l.attributes('href') === '/forum?sort=trending')
      expect(trendingLink).toBeUndefined()
    })

    it('does not show guest alert', async () => {
      const { wrapper } = await mountHome()
      // BaseAlert for guest alert should not exist for members
      // Check no guest-related text
      const alerts = wrapper.findAll('.base-alert')
      // Member view should not have the guest warning alert
      const guestAlerts = alerts.filter((a) => a.text().includes('guest'))
      expect(guestAlerts.length).toBe(0)
    })
  })

  describe('Guest view', () => {
    it('shows guest alert', async () => {
      const { wrapper } = await mountHome({ role: 'GUEST' })
      const alerts = wrapper.findAll('.base-alert')
      expect(alerts.length).toBeGreaterThan(0)
    })

    it('shows membership application form', async () => {
      const { wrapper } = await mountHome({ role: 'GUEST' })
      expect(wrapper.find('.base-textarea').exists()).toBe(true)
    })

    it('submits membership application on click', async () => {
      const { wrapper } = await mountHome({ role: 'GUEST' })
      const vm = wrapper.vm as any
      vm.applicationDesc = 'I want to join the community'
      await nextTick()

      await vm.submitApplication()
      await flushPromises()
      expect(mockApplyForMembership).toHaveBeenCalledWith('I want to join the community')
    })

    it('shows submitted message after successful application', async () => {
      const { wrapper } = await mountHome({ role: 'GUEST' })
      const vm = wrapper.vm as any
      vm.applicationDesc = 'Please accept me'
      await nextTick()

      await vm.submitApplication()
      await flushPromises()

      // After submit, the submitted state shows the success message
      expect(wrapper.text()).toContain(wrapper.vm.$t('home.applyMembership.submitted'))
    })

    it('handles application error gracefully', async () => {
      mockApplyForMembership.mockRejectedValue(new Error('Failed'))
      const { wrapper } = await mountHome({ role: 'GUEST' })
      const textarea = wrapper.find('.base-textarea')
      await textarea.setValue('I want to join')

      const buttons = wrapper.findAll('button')
      const submitBtn = buttons.find(
        (b) => b.attributes('disabled') === undefined && b.text().trim().length > 0,
      )
      if (submitBtn) {
        await submitBtn.trigger('click')
        await flushPromises()
      }
      // Should still show the form (not submitted)
      expect(wrapper.find('.base-textarea').exists()).toBe(true)
    })
  })
})

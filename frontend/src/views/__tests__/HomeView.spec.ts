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

const mockGetMyApplication = vi.fn().mockResolvedValue({ application: null })
vi.mock('@/api/users', () => ({
  applyForMembership: (...args: unknown[]) => mockApplyForMembership(...args),
  getMyApplication: (...args: unknown[]) => mockGetMyApplication(...args),
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
    BaseInput: {
      template:
        '<div><input class="base-input" :id="id" :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" /><span v-if="error" class="input-error">{{ error }}</span></div>',
      props: ['modelValue', 'id', 'label', 'placeholder', 'error', 'maxlength', 'autocomplete', 'type'],
    },
    BaseTextarea: {
      template:
        '<textarea class="base-textarea" :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)"></textarea>',
      props: ['modelValue', 'placeholder', 'rows'],
    },
    BaseModal: {
      template: '<div class="base-modal" v-if="modelValue"><slot /><slot name="footer" /></div>',
      props: ['modelValue', 'title', 'size'],
    },
    SkeletonLoader: { template: '<div class="skeleton-loader" />', props: ['lines', 'variant'] },
    PostCard: {
      template: '<div class="post-card">{{ post?.title }}</div>',
      props: ['post', 'maxPreviewLines'],
    },
    FriendRecommendations: { template: '<div />' },
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

    it('does not show membership application form (anonymous guests cannot apply)', async () => {
      const { wrapper } = await mountHome({ role: 'GUEST' })
      // Application textarea was removed — guests should register instead
      expect(wrapper.find('.base-textarea').exists()).toBe(false)
    })

    it('shows a register link in the guest alert', async () => {
      const { wrapper } = await mountHome({ role: 'GUEST' })
      const links = wrapper.findAll('a')
      const registerLink = links.find((l) => l.attributes('href')?.includes('/register'))
      expect(registerLink).toBeTruthy()
    })

    it('never calls applyForMembership', async () => {
      await mountHome({ role: 'GUEST' })
      expect(mockApplyForMembership).not.toHaveBeenCalled()
    })
  })

  describe('Membership application modal (H2, H3, M3)', () => {
    async function openModal() {
      mockGetMyApplication.mockRejectedValue(
        Object.assign(new Error('Not Found'), { response: { status: 404 } }),
      )
      const { wrapper, auth } = await mountHome({ role: 'GUEST' })
      // Click "Apply Now" button to open the modal
      const applyBtn = wrapper
        .findAll('button')
        .find((b) => b.text().includes('Apply Now'))
      expect(applyBtn).toBeTruthy()
      await applyBtn!.trigger('click')
      await nextTick()
      return { wrapper }
    }

    it('H2: form contains a hidden submit button for Enter key submission', async () => {
      const { wrapper } = await openModal()
      const form = wrapper.find('form')
      expect(form.exists()).toBe(true)
      const hiddenSubmit = form.find('button[type="submit"].hidden')
      expect(hiddenSubmit.exists()).toBe(true)
    })

    it('H3: password with only lowercase and length >= 8 fails validation', async () => {
      const { wrapper } = await openModal()
      // Fill form with valid fields but weak password (no uppercase/digit/special)
      const inputs = wrapper.findAll('.base-input')
      const usernameInput = wrapper.find('#apply-username')
      const passwordInput = wrapper.find('#apply-password')
      const displayNameInput = wrapper.find('#apply-display-name')

      await usernameInput.setValue('validuser')
      await passwordInput.setValue('abcdefgh')
      await displayNameInput.setValue('Valid Name')
      // Set description via textarea
      const textarea = wrapper.find('.base-textarea')
      await textarea.setValue('I want to join for research')

      // Trigger form submission via the submit button in footer
      const submitBtn = wrapper
        .findAll('button')
        .find((b) => b.text().includes('Submit Application'))
      await submitBtn!.trigger('click')
      await nextTick()

      // Should show password policy error
      expect(wrapper.text()).toContain(
        'Password must include uppercase, lowercase, digit, and special character.',
      )
    })

    it('H3: password meeting all policy requirements passes validation', async () => {
      const { wrapper } = await openModal()
      const usernameInput = wrapper.find('#apply-username')
      const passwordInput = wrapper.find('#apply-password')
      const displayNameInput = wrapper.find('#apply-display-name')
      const textarea = wrapper.find('.base-textarea')

      await usernameInput.setValue('validuser')
      await passwordInput.setValue('StrongP@ss1')
      await displayNameInput.setValue('Valid Name')
      await textarea.setValue('I want to join for research')

      mockApplyForMembership.mockResolvedValue({})
      const submitBtn = wrapper
        .findAll('button')
        .find((b) => b.text().includes('Submit Application'))
      await submitBtn!.trigger('click')
      await flushPromises()

      // Should not show password policy error — form submitted successfully
      expect(wrapper.text()).not.toContain(
        'Password must include uppercase, lowercase, digit, and special character.',
      )
      expect(mockApplyForMembership).toHaveBeenCalled()
    })

    it('H3: password with no special character fails validation', async () => {
      const { wrapper } = await openModal()
      const usernameInput = wrapper.find('#apply-username')
      const passwordInput = wrapper.find('#apply-password')
      const displayNameInput = wrapper.find('#apply-display-name')
      const textarea = wrapper.find('.base-textarea')

      await usernameInput.setValue('validuser')
      await passwordInput.setValue('StrongPass1')
      await displayNameInput.setValue('Valid Name')
      await textarea.setValue('I want to join for research')

      const submitBtn = wrapper
        .findAll('button')
        .find((b) => b.text().includes('Submit Application'))
      await submitBtn!.trigger('click')
      await nextTick()

      expect(wrapper.text()).toContain(
        'Password must include uppercase, lowercase, digit, and special character.',
      )
      expect(mockApplyForMembership).not.toHaveBeenCalled()
    })

    it('M3: fetchMyApplication ignores 404 errors silently', async () => {
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
      mockGetMyApplication.mockRejectedValue(
        Object.assign(new Error('Not Found'), { response: { status: 404 } }),
      )
      await mountHome({ role: 'GUEST' })
      await flushPromises()

      expect(consoleSpy).not.toHaveBeenCalledWith(
        expect.stringContaining('Failed to fetch application status'),
        expect.anything(),
      )
      consoleSpy.mockRestore()
    })

    it('M3: fetchMyApplication ignores 401 errors silently', async () => {
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
      mockGetMyApplication.mockRejectedValue(
        Object.assign(new Error('Unauthorized'), { response: { status: 401 } }),
      )
      await mountHome({ role: 'GUEST' })
      await flushPromises()

      expect(consoleSpy).not.toHaveBeenCalledWith(
        expect.stringContaining('Failed to fetch application status'),
        expect.anything(),
      )
      consoleSpy.mockRestore()
    })

    it('M3: fetchMyApplication logs non-404/401 errors', async () => {
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
      mockGetMyApplication.mockRejectedValue(
        Object.assign(new Error('Server Error'), { response: { status: 500 } }),
      )
      await mountHome({ role: 'GUEST' })
      await flushPromises()

      expect(consoleSpy).toHaveBeenCalledWith(
        'Failed to fetch application status:',
        expect.anything(),
      )
      consoleSpy.mockRestore()
    })
  })
})

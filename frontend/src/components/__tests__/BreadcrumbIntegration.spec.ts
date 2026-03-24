import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import { ref } from 'vue'
import type { UserProfile } from '@/types/user'

// ── Mocks ──

vi.mock('@/composables/api', () => ({
  default: { get: vi.fn(), post: vi.fn(), put: vi.fn(), delete: vi.fn() },
}))

vi.mock('@/api/users', () => ({
  updateProfile: vi.fn(),
  uploadAvatar: vi.fn(),
  changePassword: vi.fn(),
  deleteAccount: vi.fn(),
  getProfile: vi.fn(),
  getPublicProfile: vi.fn().mockResolvedValue({
    id: 'u1',
    username: 'alice',
    display_name: 'Alice',
    role: 'MEMBER',
    bio: '',
    affiliation: '',
    orcid: '',
    avatar_url: null,
    created_at: '2025-01-01T00:00:00Z',
  }),
}))

vi.mock('@/api/posts', () => ({
  getPost: vi.fn().mockResolvedValue({
    id: 'p1',
    title: 'Test Post',
    content: '<p>Hello</p>',
    author: { id: 'u1', display_name: 'Alice', avatar_url: null },
    created_at: '2025-01-01T00:00:00Z',
    comment_count: 0,
    view_count: 1,
    version: 1,
    is_pinned: false,
    keywords: [],
    reaction_counts: {},
    user_reactions: [],
    allow_comments: true,
    category_name: null,
    last_comment_at: null,
    sig_id: null,
    sig_name: null,
  }),
  updatePost: vi.fn(),
  deletePost: vi.fn(),
  getPostHistory: vi.fn().mockResolvedValue([]),
  togglePinPost: vi.fn(),
  togglePostReaction: vi.fn(),
  listPosts: vi.fn().mockResolvedValue({ posts: [], total: 0, total_pages: 1 }),
}))

vi.mock('@/api/comments', () => ({
  listComments: vi.fn().mockResolvedValue({ comments: [], total: 0, total_pages: 1 }),
  createComment: vi.fn(),
  deleteComment: vi.fn(),
  updateComment: vi.fn(),
  toggleReaction: vi.fn(),
}))

vi.mock('@/api/reports', () => ({
  createReport: vi.fn(),
}))

vi.mock('@/api/files', () => ({
  getFileScanStatus: vi.fn(),
  getStorageUsage: vi.fn().mockResolvedValue({ used_bytes: 0, quota_bytes: 1073741824 }),
  uploadEditorFile: vi.fn(),
}))

vi.mock('@/api/admin', () => ({
  getDashboard: vi.fn().mockResolvedValue({
    users: 10,
    posts: 20,
    sigs: 3,
    forms: 5,
    pending_reports: 0,
    pending_applications: 0,
  }),
  createInviteCode: vi.fn(),
}))

vi.mock('@/api/sigs', () => ({
  getSig: vi.fn().mockResolvedValue({
    id: 's1',
    name: 'Test SIG',
    description: '',
    member_count: 1,
    created_at: '2025-01-01T00:00:00Z',
    creator_display_name: 'Alice',
  }),
  getSigPosts: vi.fn().mockResolvedValue({ posts: [], total: 0 }),
  getSigMembers: vi.fn().mockResolvedValue({ members: [], total: 0 }),
  getSigForms: vi.fn().mockResolvedValue({ forms: [], total: 0 }),
}))

vi.mock('@/api/forms', () => ({
  getForm: vi.fn().mockResolvedValue({
    id: 'f1',
    sig_id: 's1',
    title: 'Test Form',
    description: null,
    banner_url: null,
    deadline: null,
    max_respondents: null,
    is_active: true,
    is_schema_locked: false,
    allow_non_members: false,
    questions: [],
    response_count: 0,
    created_by: 'u1',
    created_by_name: 'Alice',
    user_is_sig_admin: false,
  }),
  createForm: vi.fn(),
  updateForm: vi.fn(),
  submitForm: vi.fn(),
  exportForm: vi.fn(),
  listFormResponses: vi.fn(),
}))

vi.mock('@/api/tasks', () => ({
  getTaskStatus: vi.fn(),
}))

vi.mock('@/constants', () => ({
  HEARTBEAT_INTERVAL_MS: 30000,
  REACTIONS: ['LIKE', 'SMILE', 'CRY'],
}))

// ── Imports after mocks ──

import ProfileView from '@/views/ProfileView.vue'
import UserProfileView from '@/views/UserProfileView.vue'
import PostDetailView from '@/views/forum/PostDetailView.vue'
import AdminDashboardView from '@/views/admin/AdminDashboardView.vue'
import { useAuthStore } from '@/stores/auth'

// ── Shared stubs ──

const stubs = {
  BaseCard: { template: '<div class="base-card"><slot /></div>', props: ['padding', 'hoverable'] },
  BaseButton: {
    template: '<button @click="$emit(\'click\')"><slot /></button>',
    props: ['loading', 'variant', 'size', 'type', 'disabled'],
  },
  BaseAlert: { template: '<div class="base-alert"><slot /></div>', props: ['type'] },
  BaseInput: {
    template: '<input class="base-input" />',
    props: ['modelValue', 'label', 'maxlength', 'placeholder', 'type', 'disabled'],
  },
  BaseTextarea: {
    template: '<textarea class="base-textarea"></textarea>',
    props: ['modelValue', 'label', 'rows', 'maxlength'],
  },
  BaseModal: {
    template: '<div class="base-modal" v-if="modelValue"><slot /><slot name="footer" /></div>',
    props: ['modelValue', 'title', 'size'],
  },
  BaseBadge: { template: '<span class="base-badge"><slot /></span>', props: ['variant', 'size'] },
  BasePagination: {
    template: '<div class="base-pagination" />',
    props: ['currentPage', 'totalPages'],
  },
  BaseAvatar: { template: '<div class="base-avatar" />', props: ['src', 'name', 'size'] },
  SkeletonLoader: { template: '<div class="skeleton-loader" />', props: ['lines', 'variant'] },
  EmptyState: {
    template: '<div class="empty-state">{{ message }}</div>',
    props: ['title', 'message'],
  },
  FloatingCreateButton: { template: '<div />', props: ['to'] },
  PostCard: {
    template: '<div class="post-card" />',
    props: ['post', 'formatTime', 'maxPreviewLines'],
  },
  TiptapEditor: { template: '<div class="tiptap-editor" />', props: ['modelValue'] },
  SigShareCard: { template: '<div />', props: ['sigId'] },
  FormShareCard: { template: '<div />', props: ['formId'] },
  CopyShareLinkButton: { template: '<div />', props: ['url'] },
  LanguageSwitcher: { template: '<div aria-haspopup="true" />', props: ['variant'] },
  Eye: { template: '<span />' },
  EyeOff: { template: '<span />' },
  Copy: { template: '<span />' },
  Check: { template: '<span />' },
}

function setupAuth(pinia: ReturnType<typeof createPinia>, role = 'MEMBER') {
  setActivePinia(pinia)
  const auth = useAuthStore()
  auth.setSession(role, 3600)
  auth.user = {
    id: 'u1',
    username: 'testuser',
    display_name: 'Test User',
    role,
    bio: '',
    affiliation: '',
    orcid: '',
    avatar_url: null,
    is_banned: false,
    ban_reason: null,
  } as unknown as UserProfile
  return auth
}

describe('Breadcrumb integration', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('ProfileView', () => {
    it('renders breadcrumb with Home > My Profile', async () => {
      const pinia = createPinia()
      setupAuth(pinia)
      const router = createRouter({
        history: createMemoryHistory(),
        routes: [
          { path: '/profile', component: ProfileView },
          { path: '/', component: { template: '<div />' } },
          { path: '/forum', component: { template: '<div />' } },
          { path: '/login', name: 'login', component: { template: '<div />' } },
        ],
      })
      await router.push('/profile')
      await router.isReady()

      const wrapper = mount(ProfileView, {
        global: { plugins: [pinia, router], stubs },
      })
      await flushPromises()

      const nav = wrapper.find('nav[aria-label="Breadcrumb"]')
      expect(nav.exists()).toBe(true)
      expect(nav.text()).toContain('Home')
      expect(nav.text()).toContain('My Profile')

      // Home should be a link
      const links = nav.findAll('a')
      expect(links.some((l) => l.text() === 'Home')).toBe(true)
      // My Profile should NOT be a link (last item)
      expect(links.some((l) => l.text() === 'My Profile')).toBe(false)
    })

    it('Home link points to /', async () => {
      const pinia = createPinia()
      setupAuth(pinia)
      const router = createRouter({
        history: createMemoryHistory(),
        routes: [
          { path: '/profile', component: ProfileView },
          { path: '/', component: { template: '<div />' } },
          { path: '/forum', component: { template: '<div />' } },
          { path: '/login', name: 'login', component: { template: '<div />' } },
        ],
      })
      await router.push('/profile')
      await router.isReady()

      const wrapper = mount(ProfileView, {
        global: { plugins: [pinia, router], stubs },
      })
      await flushPromises()

      const nav = wrapper.find('nav[aria-label="Breadcrumb"]')
      const homeLink = nav.findAll('a').find((l) => l.text() === 'Home')
      expect(homeLink?.attributes('href')).toBe('/')
    })
  })

  describe('UserProfileView', () => {
    it('renders breadcrumb with Home > Users > [User Name]', async () => {
      const pinia = createPinia()
      setupAuth(pinia)
      const router = createRouter({
        history: createMemoryHistory(),
        routes: [
          { path: '/users/:id', component: UserProfileView },
          { path: '/', component: { template: '<div />' } },
          { path: '/forum', component: { template: '<div />' } },
        ],
      })
      await router.push('/users/u1')
      await router.isReady()

      const wrapper = mount(UserProfileView, {
        global: { plugins: [pinia, router], stubs },
      })
      await flushPromises()

      const nav = wrapper.find('nav[aria-label="Breadcrumb"]')
      expect(nav.exists()).toBe(true)
      expect(nav.text()).toContain('Home')
      expect(nav.text()).toContain('Users')
      expect(nav.text()).toContain('Alice')
    })
  })

  describe('PostDetailView', () => {
    it('renders breadcrumb with Home > Forum > Post Title', async () => {
      const pinia = createPinia()
      setupAuth(pinia)
      const router = createRouter({
        history: createMemoryHistory(),
        routes: [
          { path: '/forum/:id', component: PostDetailView },
          { path: '/', component: { template: '<div />' } },
          { path: '/forum', component: { template: '<div />' } },
          { path: '/forum/create', component: { template: '<div />' } },
          { path: '/users/:id', component: { template: '<div />' } },
        ],
      })
      await router.push('/forum/p1')
      await router.isReady()

      const wrapper = mount(PostDetailView, {
        global: { plugins: [pinia, router], stubs },
      })
      await flushPromises()

      const nav = wrapper.find('nav[aria-label="Breadcrumb"]')
      expect(nav.exists()).toBe(true)
      expect(nav.text()).toContain('Home')
      expect(nav.text()).toContain('Forum')
      expect(nav.text()).toContain('Test Post')

      // Forum should be a link to /forum
      const forumLink = nav.findAll('a').find((l) => l.text() === 'Forum')
      expect(forumLink?.attributes('href')).toBe('/forum')
    })
  })

  describe('AdminDashboardView', () => {
    it('renders breadcrumb with Admin > Dashboard', async () => {
      const pinia = createPinia()
      setupAuth(pinia, 'ADMIN')
      const router = createRouter({
        history: createMemoryHistory(),
        routes: [
          { path: '/admin', component: AdminDashboardView },
          { path: '/admin/users', component: { template: '<div />' } },
          { path: '/admin/applications', component: { template: '<div />' } },
          { path: '/admin/reports', component: { template: '<div />' } },
        ],
      })
      await router.push('/admin')
      await router.isReady()

      const wrapper = mount(AdminDashboardView, {
        global: { plugins: [pinia, router], stubs },
      })
      await flushPromises()

      const nav = wrapper.find('nav[aria-label="Breadcrumb"]')
      expect(nav.exists()).toBe(true)
      expect(nav.text()).toContain('Admin')
      expect(nav.text()).toContain('Dashboard')

      // Admin should be a link
      const adminLink = nav.findAll('a').find((l) => l.text() === 'Admin')
      expect(adminLink?.attributes('href')).toBe('/admin')
    })
  })

  describe('SIG child views', () => {
    const sigChildStubs = {
      ...stubs,
    }

    it('SigPostsView renders breadcrumb with Home > SIGs > [SIG Name] > Posts', async () => {
      const { default: SigPostsView } = await import('@/views/sigs/SigPostsView.vue')
      const pinia = createPinia()
      setupAuth(pinia)
      const router = createRouter({
        history: createMemoryHistory(),
        routes: [
          { path: '/sigs/:id/posts', component: SigPostsView },
          { path: '/', component: { template: '<div />' } },
          { path: '/sigs', component: { template: '<div />' } },
          { path: '/sigs/:id', component: { template: '<div />' } },
          { path: '/forum/:id', component: { template: '<div />' } },
          { path: '/users/:id', component: { template: '<div />' } },
          { path: '/forum/create', component: { template: '<div />' } },
        ],
      })
      await router.push('/sigs/s1/posts')
      await router.isReady()

      const wrapper = mount(SigPostsView, {
        global: {
          plugins: [pinia, router],
          stubs: sigChildStubs,
          provide: {
            sig: ref({
              id: 's1',
              name: 'Test SIG',
              description: '',
              member_count: 1,
              created_at: '2025-01-01T00:00:00Z',
              creator_display_name: 'Alice',
            }),
            userSigRole: ref('MEMBER'),
          },
        },
      })
      await flushPromises()

      const nav = wrapper.find('nav[aria-label="Breadcrumb"]')
      expect(nav.exists()).toBe(true)
      expect(nav.text()).toContain('Home')
      expect(nav.text()).toContain('SIGs')
      expect(nav.text()).toContain('Test SIG')
      expect(nav.text()).toContain('Posts')
    })

    it('SigMembersView renders breadcrumb with Members', async () => {
      const { default: SigMembersView } = await import('@/views/sigs/SigMembersView.vue')
      const pinia = createPinia()
      setupAuth(pinia)
      const router = createRouter({
        history: createMemoryHistory(),
        routes: [
          { path: '/sigs/:id/members', component: SigMembersView },
          { path: '/', component: { template: '<div />' } },
          { path: '/sigs', component: { template: '<div />' } },
          { path: '/sigs/:id', component: { template: '<div />' } },
          { path: '/users/:id', component: { template: '<div />' } },
        ],
      })
      await router.push('/sigs/s1/members')
      await router.isReady()

      const wrapper = mount(SigMembersView, {
        global: {
          plugins: [pinia, router],
          stubs: sigChildStubs,
          provide: {
            sig: ref({
              id: 's1',
              name: 'Test SIG',
              description: '',
              member_count: 1,
              created_at: '2025-01-01T00:00:00Z',
              creator_display_name: 'Alice',
            }),
            userSigRole: ref('MEMBER'),
          },
        },
      })
      await flushPromises()

      const nav = wrapper.find('nav[aria-label="Breadcrumb"]')
      expect(nav.exists()).toBe(true)
      expect(nav.text()).toContain('Members')
    })

    it('SigFormsView renders breadcrumb with Forms', async () => {
      const { default: SigFormsView } = await import('@/views/sigs/SigFormsView.vue')
      const pinia = createPinia()
      setupAuth(pinia)
      const router = createRouter({
        history: createMemoryHistory(),
        routes: [
          { path: '/sigs/:id/forms', component: SigFormsView },
          { path: '/', component: { template: '<div />' } },
          { path: '/sigs', component: { template: '<div />' } },
          { path: '/sigs/:id', component: { template: '<div />' } },
          { path: '/sigs/:sigId/forms/new', component: { template: '<div />' } },
          { path: '/forms/:formId', component: { template: '<div />' } },
          { path: '/forms/:formId/edit', component: { template: '<div />' } },
        ],
      })
      await router.push('/sigs/s1/forms')
      await router.isReady()

      const wrapper = mount(SigFormsView, {
        global: {
          plugins: [pinia, router],
          stubs: sigChildStubs,
          provide: {
            sig: ref({
              id: 's1',
              name: 'Test SIG',
              description: '',
              member_count: 1,
              created_at: '2025-01-01T00:00:00Z',
              creator_display_name: 'Alice',
            }),
            userSigRole: ref('MEMBER'),
          },
        },
      })
      await flushPromises()

      const nav = wrapper.find('nav[aria-label="Breadcrumb"]')
      expect(nav.exists()).toBe(true)
      expect(nav.text()).toContain('Forms')
    })
  })
})

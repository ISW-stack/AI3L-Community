import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { ref } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import SigPostsView from '../SigPostsView.vue'
import SigMembersView from '../SigMembersView.vue'
import SigFormsView from '../SigFormsView.vue'
import { useAuthStore } from '@/stores/auth'

// Standard mocks
vi.mock('@/composables/api', () => ({
  default: {
    post: vi.fn(),
    get: vi.fn(),
  },
}))

vi.mock('@/constants', () => ({
  HEARTBEAT_INTERVAL_MS: 30000,
}))

const mockGetSigPosts = vi.fn()
const mockGetSigMembers = vi.fn()
const mockGetSigForms = vi.fn()
const mockRemoveMember = vi.fn()
const mockAssignSubAdmin = vi.fn()

vi.mock('@/api/sigs', () => ({
  getSigPosts: (...args: unknown[]) => mockGetSigPosts(...args),
  getSigMembers: (...args: unknown[]) => mockGetSigMembers(...args),
  getSigForms: (...args: unknown[]) => mockGetSigForms(...args),
  removeMember: (...args: unknown[]) => mockRemoveMember(...args),
  assignSubAdmin: (...args: unknown[]) => mockAssignSubAdmin(...args),
}))

vi.mock('@/api/forms', () => ({
  deleteForm: vi.fn(),
  listFormResponses: vi.fn(),
}))

vi.mock('@/stores/toast', () => ({
  useToastStore: vi.fn(() => ({
    show: vi.fn(),
  })),
}))

const fakeSig = {
  id: 'sig-1',
  name: 'Test SIG',
  description: null,
  created_by: 'u1',
  creator_display_name: null,
  member_count: 2,
  created_at: '2026-01-01T00:00:00Z',
}

const commonStubs = {
  BaseCard: { template: '<div class="base-card"><slot /></div>' },
  BaseButton: { template: '<button class="base-button"><slot /></button>' },
  BaseBadge: { template: '<span class="base-badge"><slot /></span>' },
  BaseModal: {
    template: '<div class="base-modal" v-if="modelValue"><slot /><slot name="footer" /></div>',
    props: ['modelValue', 'title', 'size'],
  },
  BasePagination: {
    template: '<div class="base-pagination" />',
    props: ['currentPage', 'totalPages'],
  },
  BaseAvatar: { template: '<span class="base-avatar" />' },
  SkeletonLoader: { template: '<div class="skeleton-loader" />', props: ['variant', 'lines'] },
  EmptyState: {
    template: '<div class="empty-state">{{ title }}</div>',
    props: ['title', 'message'],
  },
  FloatingCreateButton: {
    template: '<div class="fab" v-bind="$props" />',
    props: ['to'],
  },
}

describe('SIG Views — useSigLayout Inject Safety', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockGetSigPosts.mockResolvedValue({ posts: [], total: 0 })
    mockGetSigMembers.mockResolvedValue({ members: [], total: 0 })
    mockGetSigForms.mockResolvedValue({ forms: [], total: 0 })
  })

  describe('SigPostsView throws without required inject', () => {
    it('throws when sig and userSigRole are not provided', () => {
      const router = createRouter({
        history: createMemoryHistory(),
        routes: [
          {
            path: '/sigs/:id',
            component: { template: '<div />' },
            children: [{ path: 'posts', name: 'sig-posts', component: SigPostsView }],
          },
        ],
      })
      const pinia = createPinia()
      setActivePinia(pinia)

      expect(() => {
        mount(SigPostsView, {
          global: {
            plugins: [pinia, router],
            provide: {},
            stubs: commonStubs,
          },
        })
      }).toThrow('useSigLayout must be used within SigLayout')
    })

    it('mounts successfully when sig and userSigRole are provided', async () => {
      const router = createRouter({
        history: createMemoryHistory(),
        routes: [
          {
            path: '/sigs/:id',
            component: { template: '<div />' },
            children: [{ path: 'posts', name: 'sig-posts', component: SigPostsView }],
          },
        ],
      })
      const pinia = createPinia()
      setActivePinia(pinia)
      await router.push('/sigs/sig1/posts')
      await router.isReady()

      const wrapper = mount(SigPostsView, {
        global: {
          plugins: [pinia, router],
          provide: {
            sig: ref(fakeSig),
            userSigRole: ref(null),
          },
          stubs: commonStubs,
        },
      })
      await flushPromises()

      expect(wrapper.exists()).toBe(true)
    })

    it('isMember is false when userSigRole is null', async () => {
      const router = createRouter({
        history: createMemoryHistory(),
        routes: [
          {
            path: '/sigs/:id',
            component: { template: '<div />' },
            children: [{ path: 'posts', name: 'sig-posts', component: SigPostsView }],
          },
        ],
      })
      const pinia = createPinia()
      setActivePinia(pinia)
      await router.push('/sigs/sig1/posts')
      await router.isReady()

      const wrapper = mount(SigPostsView, {
        global: {
          plugins: [pinia, router],
          provide: {
            sig: ref(fakeSig),
            userSigRole: ref(null),
          },
          stubs: commonStubs,
        },
      })
      await flushPromises()

      // Floating create button should not appear when userSigRole is null
      expect(wrapper.find('.fab').exists()).toBe(false)
    })

    it('isMember becomes true when userSigRole is provided with a value', async () => {
      const router = createRouter({
        history: createMemoryHistory(),
        routes: [
          {
            path: '/sigs/:id',
            component: { template: '<div />' },
            children: [{ path: 'posts', name: 'sig-posts', component: SigPostsView }],
          },
        ],
      })
      const pinia = createPinia()
      setActivePinia(pinia)
      await router.push('/sigs/sig1/posts')
      await router.isReady()

      const wrapper = mount(SigPostsView, {
        global: {
          plugins: [pinia, router],
          provide: {
            sig: ref(fakeSig),
            userSigRole: ref('MEMBER'),
          },
          stubs: commonStubs,
        },
      })
      await flushPromises()

      expect(wrapper.find('.fab').exists()).toBe(true)
    })
  })

  describe('SigMembersView throws without required inject', () => {
    it('throws when sig and userSigRole are not provided', () => {
      const pinia = createPinia()
      setActivePinia(pinia)
      const auth = useAuthStore()
      auth.setSession('MEMBER', 3600)

      const router = createRouter({
        history: createMemoryHistory(),
        routes: [
          { path: '/sigs/:id/members', name: 'sig-members', component: SigMembersView },
          { path: '/users/:id', name: 'user-profile', component: { template: '<div />' } },
        ],
      })

      expect(() => {
        mount(SigMembersView, {
          global: {
            plugins: [pinia, router],
            provide: {},
            stubs: commonStubs,
          },
        })
      }).toThrow('useSigLayout must be used within SigLayout')
    })

    it('SIG admin actions are hidden when userSigRole is null', async () => {
      const pinia = createPinia()
      setActivePinia(pinia)
      const auth = useAuthStore()
      auth.setSession('MEMBER', 3600)
      auth.user = { id: 'current-user' } as never

      const members = [
        {
          id: 'mem-1',
          sig_id: 'sig-1',
          user_id: 'user-1',
          role: 'MEMBER',
          display_name: 'Test User',
          username: 'testuser',
          avatar_url: null,
          created_at: '2026-01-01T00:00:00Z',
        },
      ]
      mockGetSigMembers.mockResolvedValue({ members, total: 1 })

      const router = createRouter({
        history: createMemoryHistory(),
        routes: [
          { path: '/sigs/:id/members', name: 'sig-members', component: SigMembersView },
          { path: '/users/:id', name: 'user-profile', component: { template: '<div />' } },
        ],
      })
      await router.push('/sigs/sig1/members')
      await router.isReady()

      const wrapper = mount(SigMembersView, {
        global: {
          plugins: [pinia, router],
          provide: {
            sig: ref(fakeSig),
            userSigRole: ref(null),
          },
          stubs: commonStubs,
        },
      })
      await flushPromises()

      // Remove button should not appear for non-SIG-admin
      expect(wrapper.text()).not.toContain('Remove')
    })
  })

  describe('SigFormsView throws without required inject', () => {
    it('throws when sig and userSigRole are not provided', () => {
      const pinia = createPinia()
      setActivePinia(pinia)
      const auth = useAuthStore()
      auth.setSession('MEMBER', 3600)

      const router = createRouter({
        history: createMemoryHistory(),
        routes: [
          { path: '/sigs/:id/forms', name: 'sig-forms', component: SigFormsView },
          {
            path: '/sigs/:id/forms/new',
            name: 'sig-forms-new',
            component: { template: '<div />' },
          },
          { path: '/forms/:id', name: 'form-detail', component: { template: '<div />' } },
          { path: '/forms/:id/edit', name: 'form-edit', component: { template: '<div />' } },
        ],
      })

      expect(() => {
        mount(SigFormsView, {
          global: {
            plugins: [pinia, router],
            provide: {},
            stubs: commonStubs,
          },
        })
      }).toThrow('useSigLayout must be used within SigLayout')
    })

    it('Create Form button is hidden when userSigRole is null and not platform admin', async () => {
      const pinia = createPinia()
      setActivePinia(pinia)
      const auth = useAuthStore()
      auth.setSession('MEMBER', 3600)

      const sampleForms = [
        {
          id: 'form-1',
          sig_id: 'sig-1',
          title: 'Survey',
          description: 'A survey',
          banner_url: null,
          deadline: null,
          max_respondents: null,
          response_count: 0,
          allow_non_members: false,
          is_active: true,
          created_by: 'user-alice',
          created_by_name: 'Alice',
          created_at: '2026-01-01T00:00:00Z',
          updated_at: '2026-01-01T00:00:00Z',
          user_is_sig_admin: false,
        },
      ]
      mockGetSigForms.mockResolvedValue({ forms: sampleForms, total: 1 })

      const router = createRouter({
        history: createMemoryHistory(),
        routes: [
          { path: '/sigs/:id/forms', name: 'sig-forms', component: SigFormsView },
          {
            path: '/sigs/:id/forms/new',
            name: 'sig-forms-new',
            component: { template: '<div />' },
          },
          { path: '/forms/:id', name: 'form-detail', component: { template: '<div />' } },
          { path: '/forms/:id/edit', name: 'form-edit', component: { template: '<div />' } },
        ],
      })
      await router.push('/sigs/sig1/forms')
      await router.isReady()

      const wrapper = mount(SigFormsView, {
        global: {
          plugins: [pinia, router],
          provide: {
            sig: ref(fakeSig),
            userSigRole: ref(null),
          },
          stubs: commonStubs,
        },
      })
      await flushPromises()

      expect(wrapper.text()).not.toContain('Create Form')
    })
  })
})

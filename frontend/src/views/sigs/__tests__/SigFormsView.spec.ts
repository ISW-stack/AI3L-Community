import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { nextTick, ref } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import SigFormsView from '../SigFormsView.vue'
import { useAuthStore } from '@/stores/auth'

vi.mock('@/composables/api', () => ({
  default: {
    post: vi.fn(),
    get: vi.fn(),
  },
}))

vi.mock('@/constants', () => ({
  HEARTBEAT_INTERVAL_MS: 30000,
}))

const mockGetSigForms = vi.fn()
vi.mock('@/api/sigs', () => ({
  getSigForms: (...args: unknown[]) => mockGetSigForms(...args),
}))

const mockDeleteForm = vi.fn()
const mockListFormResponses = vi.fn()
vi.mock('@/api/forms', () => ({
  deleteForm: (...args: unknown[]) => mockDeleteForm(...args),
  listFormResponses: (...args: unknown[]) => mockListFormResponses(...args),
}))

const sampleForms = [
  {
    id: 'form-1',
    sig_id: 'sig-1',
    title: 'Feedback Survey',
    description: 'Please share your feedback',
    deadline: null,
    max_respondents: null,
    response_count: 5,
    allow_non_members: false,
    is_active: true,
    created_by_name: 'Alice',
    created_at: '2026-01-01T00:00:00Z',
    user_is_sig_admin: true,
  },
  {
    id: 'form-2',
    sig_id: 'sig-1',
    title: 'Registration Form',
    description: 'Event registration',
    deadline: '2026-06-01T00:00:00Z',
    max_respondents: 100,
    response_count: 42,
    allow_non_members: true,
    is_active: false,
    created_by_name: 'Bob',
    created_at: '2026-02-15T00:00:00Z',
    user_is_sig_admin: false,
  },
]

function createTestRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: { template: '<div />' } },
      { path: '/sigs/:id/forms', name: 'sig-forms', component: SigFormsView },
      { path: '/sigs/:id/forms/new', name: 'sig-forms-new', component: { template: '<div />' } },
      { path: '/forms/:id', name: 'form-detail', component: { template: '<div />' } },
      { path: '/forms/:id/edit', name: 'form-edit', component: { template: '<div />' } },
    ],
  })
}

interface MountOptions {
  userSigRole?: string | null
  platformRole?: string
}

async function mountComponent(opts: MountOptions = {}) {
  const { userSigRole = null, platformRole = 'MEMBER' } = opts

  const router = createTestRouter()
  const pinia = createPinia()
  setActivePinia(pinia)

  const auth = useAuthStore()
  auth.setSession(platformRole, 3600)

  await router.push('/sigs/sig-1/forms')
  await router.isReady()

  const wrapper = mount(SigFormsView, {
    global: {
      plugins: [pinia, router],
      provide: {
        userSigRole: ref(userSigRole),
      },
      stubs: {
        BaseCard: {
          template: '<div class="base-card"><slot /></div>',
        },
        BaseButton: {
          template: '<button class="base-button"><slot /></button>',
        },
        BaseBadge: {
          template: '<span class="base-badge"><slot /></span>',
          props: ['variant', 'size'],
        },
        BaseModal: {
          template:
            '<div class="base-modal" v-if="modelValue"><slot /><slot name="footer" /></div>',
          props: ['modelValue', 'title', 'size'],
        },
        BasePagination: {
          template: '<div class="base-pagination" />',
          props: ['currentPage', 'totalPages'],
        },
        SkeletonLoader: {
          template: '<div class="skeleton-loader" />',
          props: ['variant', 'lines'],
        },
        EmptyState: {
          template: '<div class="empty-state">{{ title }} - {{ message }}</div>',
          props: ['title', 'message'],
        },
      },
    },
  })

  return { wrapper, auth, router }
}

describe('SigFormsView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockGetSigForms.mockResolvedValue({ forms: [], total: 0 })
  })

  it('shows loading skeleton initially', async () => {
    // Make getSigForms hang so loading stays true
    mockGetSigForms.mockReturnValue(new Promise(() => {}))
    const { wrapper } = await mountComponent()

    expect(wrapper.findAll('.skeleton-loader').length).toBeGreaterThan(0)
  })

  it('renders form cards after loading', async () => {
    mockGetSigForms.mockResolvedValue({ forms: sampleForms, total: 2 })
    const { wrapper } = await mountComponent({ userSigRole: 'MEMBER' })
    await nextTick()
    await nextTick()

    expect(wrapper.text()).toContain('Feedback Survey')
    expect(wrapper.text()).toContain('Registration Form')
    expect(wrapper.text()).toContain('5 responses')
    expect(wrapper.text()).toContain('42 responses')
    expect(wrapper.text()).toContain('Please share your feedback')
    expect(wrapper.text()).toContain('Forms (2)')
  })

  it('shows "Create Form" button for SIG admin', async () => {
    mockGetSigForms.mockResolvedValue({ forms: sampleForms, total: 2 })
    const { wrapper } = await mountComponent({ userSigRole: 'ADMIN' })
    await nextTick()
    await nextTick()

    expect(wrapper.text()).toContain('Create Form')
  })

  it('shows "Create Form" button for SIG sub-admin', async () => {
    mockGetSigForms.mockResolvedValue({ forms: sampleForms, total: 2 })
    const { wrapper } = await mountComponent({ userSigRole: 'SUB_ADMIN' })
    await nextTick()
    await nextTick()

    expect(wrapper.text()).toContain('Create Form')
  })

  it('shows "Create Form" button for platform admin', async () => {
    mockGetSigForms.mockResolvedValue({ forms: sampleForms, total: 2 })
    const { wrapper } = await mountComponent({
      userSigRole: 'MEMBER',
      platformRole: 'ADMIN',
    })
    await nextTick()
    await nextTick()

    expect(wrapper.text()).toContain('Create Form')
  })

  it('hides "Create Form" button for regular members', async () => {
    mockGetSigForms.mockResolvedValue({ forms: sampleForms, total: 2 })
    const { wrapper } = await mountComponent({
      userSigRole: 'MEMBER',
      platformRole: 'MEMBER',
    })
    await nextTick()
    await nextTick()

    expect(wrapper.text()).not.toContain('Create Form')
  })

  it('shows Active badge for active form', async () => {
    mockGetSigForms.mockResolvedValue({ forms: [sampleForms[0]], total: 1 })
    const { wrapper } = await mountComponent({ userSigRole: 'MEMBER' })
    await nextTick()
    await nextTick()

    const badges = wrapper.findAll('.base-badge')
    const badgeTexts = badges.map((b) => b.text())
    expect(badgeTexts).toContain('Active')
  })

  it('shows Closed badge for inactive form', async () => {
    mockGetSigForms.mockResolvedValue({ forms: [sampleForms[1]], total: 1 })
    const { wrapper } = await mountComponent({ userSigRole: 'MEMBER' })
    await nextTick()
    await nextTick()

    const badges = wrapper.findAll('.base-badge')
    const badgeTexts = badges.map((b) => b.text())
    expect(badgeTexts).toContain('Closed')
  })

  it('shows admin actions (Edit, Responses, Delete) for SIG admin form', async () => {
    // sampleForms[0] has user_is_sig_admin: true
    mockGetSigForms.mockResolvedValue({ forms: [sampleForms[0]], total: 1 })
    const { wrapper } = await mountComponent({ userSigRole: 'ADMIN' })
    await nextTick()
    await nextTick()

    expect(wrapper.text()).toContain('Edit')
    expect(wrapper.text()).toContain('Responses')
    expect(wrapper.text()).toContain('Delete')
  })

  it('shows admin actions for platform admin even if not SIG admin', async () => {
    // sampleForms[1] has user_is_sig_admin: false, but platform admin should see actions
    mockGetSigForms.mockResolvedValue({ forms: [sampleForms[1]], total: 1 })
    const { wrapper } = await mountComponent({
      userSigRole: 'MEMBER',
      platformRole: 'ADMIN',
    })
    await nextTick()
    await nextTick()

    expect(wrapper.text()).toContain('Edit')
    expect(wrapper.text()).toContain('Responses')
    expect(wrapper.text()).toContain('Delete')
  })

  it('shows EmptyState when no forms', async () => {
    mockGetSigForms.mockResolvedValue({ forms: [], total: 0 })
    const { wrapper } = await mountComponent({ userSigRole: 'MEMBER' })
    await nextTick()
    await nextTick()

    expect(wrapper.find('.empty-state').exists()).toBe(true)
    expect(wrapper.text()).toContain('No forms yet')
  })
})

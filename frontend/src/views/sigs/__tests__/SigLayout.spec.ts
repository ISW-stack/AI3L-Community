import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { nextTick, inject } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import SigLayout from '../SigLayout.vue'
import { useAuthStore } from '@/stores/auth'

// Mock composables/api to prevent actual axios initialization
vi.mock('@/composables/api', () => ({
  default: {
    post: vi.fn(),
    get: vi.fn(),
  },
}))

vi.mock('@/constants', () => ({
  HEARTBEAT_INTERVAL_MS: 30000,
}))

// Mock DOMPurify
vi.mock('dompurify', () => ({
  default: {
    sanitize: (html: string) => html,
  },
}))

// Mock @/api/sigs
const mockGetSig = vi.fn()
const mockUpdateSig = vi.fn()
const mockDeleteSig = vi.fn()
const mockGetSigMembers = vi.fn()
const mockLeaveSig = vi.fn()
const mockJoinSig = vi.fn()

vi.mock('@/api/sigs', () => ({
  getSig: (...args: unknown[]) => mockGetSig(...args),
  updateSig: (...args: unknown[]) => mockUpdateSig(...args),
  deleteSig: (...args: unknown[]) => mockDeleteSig(...args),
  getSigMembers: (...args: unknown[]) => mockGetSigMembers(...args),
  leaveSig: (...args: unknown[]) => mockLeaveSig(...args),
  joinSig: (...args: unknown[]) => mockJoinSig(...args),
}))

const fakeSig = {
  id: 'sig-1',
  name: 'Test SIG',
  description: '<p>A test description</p>',
  created_by: 'user-creator',
  creator_display_name: 'Creator User',
  member_count: 5,
  created_at: '2026-01-15T00:00:00Z',
}

const fakeMembersWithUser = {
  members: [
    {
      id: 'member-1',
      sig_id: 'sig-1',
      user_id: 'user1',
      role: 'MEMBER',
      display_name: 'Test User',
      username: 'testuser',
      avatar_url: null,
      created_at: '2026-01-15T00:00:00Z',
    },
  ],
}

const fakeMembersAdmin = {
  members: [
    {
      id: 'member-1',
      sig_id: 'sig-1',
      user_id: 'user1',
      role: 'ADMIN',
      display_name: 'Test User',
      username: 'testuser',
      avatar_url: null,
      created_at: '2026-01-15T00:00:00Z',
    },
  ],
}

const fakeMembersEmpty = {
  members: [],
}

function createTestRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: { template: '<div />' } },
      { path: '/sigs', name: 'sigs', component: { template: '<div />' } },
      {
        path: '/sigs/:id',
        component: SigLayout,
        children: [
          { path: '', redirect: { name: 'sig-posts' } },
          { path: 'posts', name: 'sig-posts', component: { template: '<div>Posts Content</div>' } },
          {
            path: 'members',
            name: 'sig-members',
            component: { template: '<div>Members Content</div>' },
          },
          {
            path: 'forms',
            name: 'sig-forms',
            component: { template: '<div>Forms Content</div>' },
          },
        ],
      },
    ],
  })
}

async function mountLayout(options?: {
  role?: string
  sigData?: typeof fakeSig | null
  membersData?: typeof fakeMembersWithUser
  rejectSig?: boolean
}) {
  const {
    role = 'MEMBER',
    sigData = fakeSig,
    membersData = fakeMembersEmpty,
    rejectSig = false,
  } = options ?? {}

  if (rejectSig) {
    mockGetSig.mockRejectedValueOnce(new Error('Not found'))
    mockGetSigMembers.mockResolvedValueOnce(fakeMembersEmpty)
  } else if (sigData === null) {
    // Simulate sig not found: getSig throws, so sig stays null
    mockGetSig.mockRejectedValueOnce(new Error('Not found'))
    mockGetSigMembers.mockResolvedValueOnce(fakeMembersEmpty)
  } else {
    mockGetSig.mockResolvedValueOnce(sigData)
    mockGetSigMembers.mockResolvedValueOnce(membersData)
  }

  const router = createTestRouter()
  const pinia = createPinia()
  setActivePinia(pinia)

  const auth = useAuthStore()
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

  await router.push('/sigs/sig-1/posts')
  await router.isReady()

  const wrapper = mount(SigLayout, {
    global: {
      plugins: [pinia, router],
      stubs: {
        BaseCard: { template: '<div class="base-card"><slot /></div>' },
        BaseButton: {
          template:
            '<button :disabled="$attrs.disabled" @click="$emit(\'click\')"><slot /></button>',
          props: ['loading', 'variant', 'size'],
        },
        BaseModal: {
          template:
            '<div class="base-modal" v-if="modelValue"><slot /><slot name="footer" /></div>',
          props: ['modelValue', 'title', 'size'],
        },
        BaseInput: {
          template:
            '<input class="base-input" :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
          props: ['modelValue', 'label', 'placeholder'],
        },
        BaseTextarea: {
          template:
            '<textarea class="base-textarea" :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)"></textarea>',
          props: ['modelValue', 'label', 'rows', 'placeholder'],
        },
        SkeletonLoader: { template: '<div class="skeleton-loader" />' },
        CopyShareLinkButton: { template: '<span class="copy-share-link" />' },
      },
    },
  })

  // Wait for onMounted fetchSigData to resolve
  await vi.dynamicImportSettled()
  await nextTick()
  await nextTick()

  return { wrapper, auth, router }
}

describe('SigLayout', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    mockGetSig.mockReset()
    mockUpdateSig.mockReset()
    mockDeleteSig.mockReset()
    mockGetSigMembers.mockReset()
    mockLeaveSig.mockReset()
    mockJoinSig.mockReset()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('shows loading skeleton initially', async () => {
    // Never resolve so loading stays true
    mockGetSig.mockReturnValue(new Promise(() => {}))
    mockGetSigMembers.mockReturnValue(new Promise(() => {}))

    const router = createTestRouter()
    const pinia = createPinia()
    setActivePinia(pinia)

    const auth = useAuthStore()
    auth.setSession('MEMBER', 3600)
    auth.user = { id: 'user1' } as any

    await router.push('/sigs/sig-1/posts')
    await router.isReady()

    const wrapper = mount(SigLayout, {
      global: {
        plugins: [pinia, router],
        stubs: {
          BaseCard: { template: '<div class="base-card"><slot /></div>' },
          BaseButton: { template: '<button><slot /></button>' },
          BaseModal: { template: '<div />' },
          BaseInput: { template: '<input />' },
          BaseTextarea: { template: '<textarea />' },
          SkeletonLoader: { template: '<div class="skeleton-loader" />' },
          CopyShareLinkButton: { template: '<span />' },
        },
      },
    })

    await nextTick()

    const skeletons = wrapper.findAll('.skeleton-loader')
    expect(skeletons.length).toBeGreaterThan(0)
  })

  it('shows "SIG not found" when sig is null after loading', async () => {
    const { wrapper } = await mountLayout({ sigData: null })

    expect(wrapper.text()).toContain('SIG not found')
    expect(wrapper.text()).toContain('Return to Directory')
  })

  it('renders SIG name and description after loading', async () => {
    const { wrapper } = await mountLayout({
      sigData: fakeSig,
      membersData: fakeMembersEmpty,
    })

    expect(wrapper.text()).toContain('Test SIG')
    expect(wrapper.html()).toContain('<p>A test description</p>')
  })

  it('shows Join SIG button for non-member authenticated users', async () => {
    const { wrapper } = await mountLayout({
      role: 'MEMBER',
      sigData: fakeSig,
      membersData: fakeMembersEmpty,
    })

    const buttons = wrapper.findAll('button')
    const joinBtn = buttons.filter((b) => b.text().includes('Join SIG'))
    expect(joinBtn.length).toBeGreaterThan(0)
  })

  it('shows Edit button for SIG admin', async () => {
    const { wrapper } = await mountLayout({
      role: 'MEMBER',
      sigData: fakeSig,
      membersData: fakeMembersAdmin,
    })

    const buttons = wrapper.findAll('button')
    const editBtn = buttons.filter((b) => b.text() === 'Edit')
    expect(editBtn.length).toBeGreaterThan(0)
  })

  it('shows Delete SIG button for platform admin', async () => {
    const { wrapper } = await mountLayout({
      role: 'ADMIN',
      sigData: fakeSig,
      membersData: fakeMembersWithUser,
    })

    const buttons = wrapper.findAll('button')
    const deleteBtn = buttons.filter((b) => b.text().includes('Delete SIG'))
    expect(deleteBtn.length).toBeGreaterThan(0)
  })

  it('shows Leave SIG button for non-admin members', async () => {
    const { wrapper } = await mountLayout({
      role: 'MEMBER',
      sigData: fakeSig,
      membersData: fakeMembersWithUser,
    })

    const buttons = wrapper.findAll('button')
    const leaveBtn = buttons.filter((b) => b.text().includes('Leave SIG'))
    expect(leaveBtn.length).toBeGreaterThan(0)
  })

  it('hides Join button for existing members', async () => {
    const { wrapper } = await mountLayout({
      role: 'MEMBER',
      sigData: fakeSig,
      membersData: fakeMembersWithUser,
    })

    const buttons = wrapper.findAll('button')
    const joinBtn = buttons.filter((b) => b.text().includes('Join SIG'))
    expect(joinBtn.length).toBe(0)
  })

  it('renders navigation items (Posts, Members, Forms)', async () => {
    const { wrapper } = await mountLayout({
      sigData: fakeSig,
      membersData: fakeMembersEmpty,
    })

    expect(wrapper.text()).toContain('Posts')
    expect(wrapper.text()).toContain('Members')
    expect(wrapper.text()).toContain('Forms')
  })

  it('shows edit form when Edit is clicked', async () => {
    const { wrapper } = await mountLayout({
      role: 'ADMIN',
      sigData: fakeSig,
      membersData: fakeMembersWithUser,
    })

    const buttons = wrapper.findAll('button')
    const editBtn = buttons.find((b) => b.text() === 'Edit')
    expect(editBtn).toBeTruthy()

    await editBtn!.trigger('click')
    await nextTick()

    // After clicking Edit, edit form should be visible with Save Changes and Cancel buttons
    expect(wrapper.text()).toContain('Save Changes')
    expect(wrapper.text()).toContain('Cancel')
    expect(wrapper.find('.base-input').exists()).toBe(true)
    expect(wrapper.find('.base-textarea').exists()).toBe(true)
  })

  it('provides sig and userSigRole via inject', async () => {
    // Use a child component that reads injected values
    const ChildComponent = {
      template: '<div class="injected">{{ sigVal?.name }} | {{ roleVal }}</div>',
      setup() {
        const sigVal = inject('sig')
        const roleVal = inject('userSigRole')
        return { sigVal, roleVal }
      },
    }

    // Provide enough mock responses for both onMounted and possible watcher calls
    mockGetSig.mockResolvedValue(fakeSig)
    mockGetSigMembers.mockResolvedValue(fakeMembersWithUser)

    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/', component: { template: '<div />' } },
        { path: '/sigs', name: 'sigs', component: { template: '<div />' } },
        {
          path: '/sigs/:id',
          component: SigLayout,
          children: [
            { path: '', redirect: { name: 'sig-posts' } },
            { path: 'posts', name: 'sig-posts', component: ChildComponent },
            { path: 'members', name: 'sig-members', component: { template: '<div />' } },
            { path: 'forms', name: 'sig-forms', component: { template: '<div />' } },
          ],
        },
      ],
    })

    const pinia = createPinia()
    setActivePinia(pinia)

    const auth = useAuthStore()
    auth.setSession('MEMBER', 3600)
    auth.user = {
      id: 'user1',
      username: 'testuser',
      display_name: 'Test User',
      role: 'MEMBER',
      bio: null,
      affiliation: null,
      orcid: null,
      avatar_url: null,
      is_banned: false,
      ban_reason: null,
    } as any

    await router.push('/sigs/sig-1/posts')
    await router.isReady()

    const wrapper = mount(SigLayout, {
      global: {
        plugins: [pinia, router],
        stubs: {
          BaseCard: { template: '<div class="base-card"><slot /></div>' },
          BaseButton: { template: '<button><slot /></button>' },
          BaseModal: { template: '<div />' },
          BaseInput: { template: '<input />' },
          BaseTextarea: { template: '<textarea />' },
          SkeletonLoader: { template: '<div class="skeleton-loader" />' },
          CopyShareLinkButton: { template: '<span />' },
          // Disable transition so router-view child renders immediately
          transition: { template: '<div><slot /></div>' },
        },
      },
    })

    // Flush all pending promises and ticks
    await vi.dynamicImportSettled()
    await nextTick()
    await nextTick()
    await nextTick()
    await nextTick()

    const injectedEl = wrapper.find('.injected')
    expect(injectedEl.exists()).toBe(true)
    expect(injectedEl.text()).toContain('Test SIG')
    expect(injectedEl.text()).toContain('MEMBER')
  })
})

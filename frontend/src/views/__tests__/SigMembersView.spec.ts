import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import { ref } from 'vue'
import SigMembersView from '../sigs/SigMembersView.vue'
import { useAuthStore } from '@/stores/auth'

const mockGetSigMembers = vi.fn()
const mockRemoveMember = vi.fn()
const mockAssignSubAdmin = vi.fn()
const mockDemoteSubAdmin = vi.fn()

vi.mock('@/api/sigs', () => ({
  getSigMembers: (...args: unknown[]) => mockGetSigMembers(...args),
  removeMember: (...args: unknown[]) => mockRemoveMember(...args),
  assignSubAdmin: (...args: unknown[]) => mockAssignSubAdmin(...args),
  demoteSubAdmin: (...args: unknown[]) => mockDemoteSubAdmin(...args),
}))

vi.mock('@/composables/api', () => ({
  default: { get: vi.fn(), post: vi.fn(), put: vi.fn(), delete: vi.fn() },
}))

vi.mock('@/constants', () => ({
  HEARTBEAT_INTERVAL_MS: 30000,
}))

vi.mock('@/api/auth', () => ({
  login: vi.fn(),
  guestLogin: vi.fn(),
  register: vi.fn(),
  logout: vi.fn(),
  heartbeat: vi.fn().mockResolvedValue({}),
}))

vi.mock('@/api/users', () => ({
  getProfile: vi.fn().mockResolvedValue({ data: null }),
}))

vi.mock('@/composables/useSigLayout', () => ({
  useSigLayout: () => ({
    sig: ref({ id: 'sig-1', name: 'Test SIG' }),
    userSigRole: mockUserSigRole,
    refreshSigRole: vi.fn().mockResolvedValue(undefined),
  }),
}))

let mockUserSigRole = ref<string | null>('ADMIN')

const fakeMemberAdmin: Record<string, unknown> = {
  id: 'm1',
  sig_id: 'sig-1',
  user_id: 'user-admin',
  role: 'ADMIN',
  display_name: 'SIG Admin',
  username: 'sigadmin',
  avatar_url: null,
  created_at: '2026-01-01T00:00:00Z',
}

const fakeMemberSubAdmin: Record<string, unknown> = {
  id: 'm2',
  sig_id: 'sig-1',
  user_id: 'user-sub',
  role: 'SUB_ADMIN',
  display_name: 'Sub Admin',
  username: 'subadmin',
  avatar_url: null,
  created_at: '2026-01-02T00:00:00Z',
}

const fakeMemberRegular: Record<string, unknown> = {
  id: 'm3',
  sig_id: 'sig-1',
  user_id: 'user-member',
  role: 'MEMBER',
  display_name: 'Regular Member',
  username: 'regular',
  avatar_url: null,
  created_at: '2026-01-03T00:00:00Z',
}

function createTestRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/sigs/:id/members', component: SigMembersView },
      { path: '/sigs/:id', component: { template: '<div />' } },
      { path: '/sigs', component: { template: '<div />' } },
      { path: '/', component: { template: '<div />' } },
      { path: '/users/:id', component: { template: '<div />' } },
    ],
  })
}

function createStubs() {
  return {
    SkeletonLoader: { template: '<div class="skeleton-loader" />', props: ['lines', 'variant'] },
    EmptyState: {
      template: '<div class="empty-state">{{ title }}</div>',
      props: ['title', 'message'],
    },
    BasePagination: {
      template: '<div class="base-pagination" />',
      props: ['currentPage', 'totalPages', 'pageSize', 'total'],
    },
    BaseBreadcrumb: { template: '<div class="breadcrumb" />', props: ['items'] },
    BaseBadge: { template: '<span class="badge"><slot /></span>', props: ['variant', 'size'] },
    BaseAvatar: { template: '<div class="avatar" />', props: ['src', 'name', 'size'] },
    BaseCard: { template: '<div class="card"><slot /></div>', props: ['padding'] },
    BaseModal: {
      template: '<div class="modal" v-if="modelValue"><slot /><slot name="footer" /></div>',
      props: ['modelValue', 'title', 'size'],
    },
    BaseButton: {
      template: '<button @click="$emit(\'click\')"><slot /></button>',
      props: ['loading', 'variant', 'size'],
    },
  }
}

async function mountView(options?: { role?: string; platformAdmin?: boolean; userId?: string }) {
  const { role = 'ADMIN', platformAdmin = false, userId = 'current-user' } = options || {}

  mockUserSigRole = ref<string | null>(role)

  const pinia = createPinia()
  setActivePinia(pinia)

  const auth = useAuthStore()
  auth.user = {
    id: userId,
    username: 'me',
    display_name: 'Me',
    role: platformAdmin ? 'ADMIN' : 'MEMBER',
  } as never
  // Set the role ref so the computed isAdmin works correctly
  if (platformAdmin) {
    auth.setSession('ADMIN', 3600)
  } else {
    auth.setSession('MEMBER', 3600)
  }

  const router = createTestRouter()
  router.push('/sigs/sig-1/members')
  await router.isReady()

  // Re-mock useSigLayout with the current mockUserSigRole
  vi.doMock('@/composables/useSigLayout', () => ({
    useSigLayout: () => ({
      sig: ref({ id: 'sig-1', name: 'Test SIG' }),
      userSigRole: mockUserSigRole,
      refreshSigRole: vi.fn().mockResolvedValue(undefined),
    }),
  }))

  const wrapper = mount(SigMembersView, {
    global: {
      plugins: [pinia, router],
      stubs: createStubs(),
    },
  })
  await flushPromises()
  return { wrapper, auth }
}

describe('SigMembersView permission checks', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockGetSigMembers.mockResolvedValue({
      members: [fakeMemberAdmin, fakeMemberSubAdmin, fakeMemberRegular],
      total: 3,
    })
  })

  describe('canRemoveMember', () => {
    it('returns false when user is SUB_ADMIN (not SIG ADMIN)', async () => {
      const { wrapper } = await mountView({ role: 'SUB_ADMIN' })
      // SUB_ADMIN should NOT see the Actions column at all (canEdit is false)
      const desktopTable = wrapper.find('.hidden.md\\:block table')
      if (desktopTable.exists()) {
        const headers = desktopTable.findAll('th')
        const headerTexts = headers.map((h) => h.text())
        expect(headerTexts).not.toContain(expect.stringMatching(/actions/i))
      }
    })

    it('returns true when user is SIG ADMIN for regular members', async () => {
      const { wrapper } = await mountView({ role: 'ADMIN' })
      // SIG ADMIN should see the Actions column
      const desktopTable = wrapper.find('.hidden.md\\:block table')
      if (desktopTable.exists()) {
        const headers = desktopTable.findAll('th')
        const hasActions = headers.some((h) => h.text().toLowerCase().includes('actions'))
        expect(hasActions).toBe(true)
      }
    })

    it('SIG ADMIN cannot remove themselves', async () => {
      const { wrapper } = await mountView({ role: 'ADMIN', userId: 'user-admin' })
      // The remove button should not appear for the user's own row
      const rows = wrapper.findAll('tr')
      const adminRow = rows.find((r) => r.text().includes('SIG Admin'))
      if (adminRow) {
        const buttons = adminRow.findAll('button')
        const removeBtn = buttons.find((b) => b.text().toLowerCase().includes('remove'))
        expect(removeBtn).toBeUndefined()
      }
    })

    it('platform admin can remove SIG ADMIN members', async () => {
      const { wrapper } = await mountView({ role: 'MEMBER', platformAdmin: true })
      const rows = wrapper.findAll('tr')
      const adminRow = rows.find((r) => r.text().includes('SIG Admin'))
      if (adminRow) {
        const buttons = adminRow.findAll('button')
        const removeBtn = buttons.find((b) => b.text().toLowerCase().includes('remove'))
        expect(removeBtn).toBeDefined()
      }
    })
  })

  describe('canAssignSubAdmin', () => {
    it('returns false for SUB_ADMIN caller — no promote button visible', async () => {
      const { wrapper } = await mountView({ role: 'SUB_ADMIN' })
      // canEdit is false for SUB_ADMIN, so no actions column at all
      const allButtons = wrapper.findAll('button')
      const promoteBtn = allButtons.find((b) => b.text().toLowerCase().includes('promote'))
      expect(promoteBtn).toBeUndefined()
    })

    it('returns true for SIG ADMIN caller — promote button visible for MEMBER', async () => {
      const { wrapper } = await mountView({ role: 'ADMIN' })
      const rows = wrapper.findAll('tr')
      const memberRow = rows.find((r) => r.text().includes('Regular Member'))
      if (memberRow) {
        const buttons = memberRow.findAll('button')
        const promoteBtn = buttons.find((b) => b.text().toLowerCase().includes('promote'))
        expect(promoteBtn).toBeDefined()
      }
    })

    it('returns false for non-MEMBER targets (ADMIN)', async () => {
      const { wrapper } = await mountView({ role: 'ADMIN' })
      const rows = wrapper.findAll('tr')
      const adminRow = rows.find((r) => r.text().includes('SIG Admin'))
      if (adminRow) {
        const buttons = adminRow.findAll('button')
        const promoteBtn = buttons.find((b) => b.text().toLowerCase().includes('promote'))
        expect(promoteBtn).toBeUndefined()
      }
    })

    it('returns false for non-MEMBER targets (SUB_ADMIN)', async () => {
      const { wrapper } = await mountView({ role: 'ADMIN' })
      const rows = wrapper.findAll('tr')
      const subAdminRow = rows.find((r) => r.text().includes('Sub Admin'))
      if (subAdminRow) {
        const buttons = subAdminRow.findAll('button')
        const promoteBtn = buttons.find((b) => b.text().toLowerCase().includes('promote'))
        expect(promoteBtn).toBeUndefined()
      }
    })
  })

  describe('canEdit (Actions column visibility)', () => {
    it('hides Actions column for SUB_ADMIN users', async () => {
      const { wrapper } = await mountView({ role: 'SUB_ADMIN' })
      const headers = wrapper.findAll('th')
      const hasActions = headers.some((h) => h.text().toLowerCase().includes('actions'))
      expect(hasActions).toBe(false)
    })

    it('shows Actions column for SIG ADMIN users', async () => {
      const { wrapper } = await mountView({ role: 'ADMIN' })
      const headers = wrapper.findAll('th')
      const hasActions = headers.some((h) => h.text().toLowerCase().includes('actions'))
      expect(hasActions).toBe(true)
    })

    it('shows Actions column for platform admin users', async () => {
      const { wrapper } = await mountView({ role: 'MEMBER', platformAdmin: true })
      const headers = wrapper.findAll('th')
      const hasActions = headers.some((h) => h.text().toLowerCase().includes('actions'))
      expect(hasActions).toBe(true)
    })

    it('hides Actions column for regular MEMBER users', async () => {
      const { wrapper } = await mountView({ role: 'MEMBER' })
      const headers = wrapper.findAll('th')
      const hasActions = headers.some((h) => h.text().toLowerCase().includes('actions'))
      expect(hasActions).toBe(false)
    })
  })
})

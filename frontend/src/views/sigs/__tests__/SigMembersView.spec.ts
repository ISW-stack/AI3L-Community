import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { ref } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import SigMembersView from '../SigMembersView.vue'
import { useAuthStore } from '@/stores/auth'
import type { SigMember } from '@/types'

vi.mock('@/composables/api', () => ({
  default: {
    post: vi.fn(),
    get: vi.fn(),
    delete: vi.fn(),
  },
}))

vi.mock('@/constants', () => ({
  HEARTBEAT_INTERVAL_MS: 30000,
}))

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

function makeMember(overrides: Partial<SigMember> = {}): SigMember {
  return {
    id: 'mem-1',
    sig_id: 'sig-1',
    user_id: 'user-1',
    role: 'MEMBER',
    display_name: 'Alice Test',
    username: 'alice',
    avatar_url: null,
    created_at: '2026-01-15T00:00:00Z',
    ...overrides,
  }
}

const sampleMembers: SigMember[] = [
  makeMember({
    id: 'mem-1',
    user_id: 'user-1',
    role: 'ADMIN',
    display_name: 'Admin User',
    username: 'adminuser',
  }),
  makeMember({
    id: 'mem-2',
    user_id: 'user-2',
    role: 'SUB_ADMIN',
    display_name: 'Sub Admin',
    username: 'subadmin',
  }),
  makeMember({
    id: 'mem-3',
    user_id: 'user-3',
    role: 'MEMBER',
    display_name: 'Regular Member',
    username: 'regular',
  }),
]

function createTestRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: { template: '<div />' } },
      { path: '/sigs/:id/members', name: 'sig-members', component: SigMembersView },
      { path: '/users/:id', name: 'user-profile', component: { template: '<div />' } },
    ],
  })
}

const mockRefreshSigRole = vi.fn().mockResolvedValue(undefined)

async function mountComponent(
  options: {
    role?: string
    userSigRole?: string | null
    members?: SigMember[]
    total?: number
    currentUserId?: string
    refreshSigRole?: () => Promise<void>
  } = {},
) {
  const {
    role = 'MEMBER',
    userSigRole = null,
    members = sampleMembers,
    total = members.length,
    currentUserId = 'current-user',
    refreshSigRole = mockRefreshSigRole,
  } = options

  mockGetSigMembers.mockResolvedValue({ members, total })

  const router = createTestRouter()
  const pinia = createPinia()
  setActivePinia(pinia)

  const auth = useAuthStore()
  auth.setSession(role, 3600)
  auth.user = { id: currentUserId } as never

  await router.push('/sigs/sig-1/members')
  await router.isReady()

  const wrapper = mount(SigMembersView, {
    global: {
      plugins: [pinia, router],
      provide: {
        sig: ref({
          id: 'sig-1',
          name: 'Test SIG',
          description: null,
          created_by: 'u1',
          creator_display_name: null,
          member_count: 3,
          created_at: '2026-01-01T00:00:00Z',
        }),
        userSigRole: ref(userSigRole),
        refreshSigRole,
      },
      stubs: {
        BaseCard: { template: '<div class="base-card"><slot /></div>' },
        BaseBadge: {
          template: '<span class="base-badge" :data-variant="$attrs.variant"><slot /></span>',
          inheritAttrs: false,
        },
        BaseAvatar: { template: '<span class="base-avatar" />' },
        SkeletonLoader: { template: '<div class="skeleton-loader" />' },
        EmptyState: { template: '<div class="empty-state" />', props: ['title', 'message'] },
        BaseModal: {
          template:
            '<div class="base-modal" v-if="modelValue"><slot /><slot name="footer" /></div>',
          props: ['modelValue', 'title', 'size'],
        },
        BaseButton: {
          template: '<button :class="$attrs.class" @click="$emit(\'click\')"><slot /></button>',
          props: ['variant', 'size', 'loading'],
        },
        BasePagination: {
          template:
            '<div class="base-pagination" v-if="totalPages > 1" @click="$emit(\'update:currentPage\', currentPage + 1)">Page {{ currentPage }} of {{ totalPages }}</div>',
          props: ['currentPage', 'totalPages', 'pageSize', 'total'],
        },
      },
    },
  })

  return { wrapper, auth, router }
}

describe('SigMembersView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockRefreshSigRole.mockResolvedValue(undefined)
  })

  it('shows loading skeleton initially', async () => {
    // Make getSigMembers hang so loading stays true
    mockGetSigMembers.mockReturnValue(new Promise(() => {}))

    const router = createTestRouter()
    const pinia = createPinia()
    setActivePinia(pinia)

    const auth = useAuthStore()
    auth.setSession('MEMBER', 3600)

    await router.push('/sigs/sig-1/members')
    await router.isReady()

    const wrapper = mount(SigMembersView, {
      global: {
        plugins: [pinia, router],
        provide: {
          sig: ref({
            id: 'sig-1',
            name: 'Test SIG',
            description: null,
            created_by: 'u1',
            creator_display_name: null,
            member_count: 3,
            created_at: '2026-01-01T00:00:00Z',
          }),
          userSigRole: ref(null),
        },
        stubs: {
          BaseCard: { template: '<div class="base-card"><slot /></div>' },
          BaseBadge: { template: '<span class="base-badge"><slot /></span>' },
          BaseAvatar: { template: '<span class="base-avatar" />' },
          SkeletonLoader: { template: '<div class="skeleton-loader" />' },
          EmptyState: { template: '<div class="empty-state" />' },
        },
      },
    })

    expect(wrapper.find('.skeleton-loader').exists()).toBe(true)
    expect(wrapper.find('table').exists()).toBe(false)
  })

  it('renders member table after loading', async () => {
    const { wrapper } = await mountComponent()
    await flushPromises()

    expect(wrapper.find('.skeleton-loader').exists()).toBe(false)
    expect(wrapper.find('table').exists()).toBe(true)
  })

  it('shows member display name and username', async () => {
    const { wrapper } = await mountComponent()
    await flushPromises()

    expect(wrapper.text()).toContain('Admin User')
    expect(wrapper.text()).toContain('@adminuser')
    expect(wrapper.text()).toContain('Regular Member')
    expect(wrapper.text()).toContain('@regular')
  })

  it('shows role badges with correct variants', async () => {
    const { wrapper } = await mountComponent()
    await flushPromises()

    const badges = wrapper.findAll('.base-badge')
    const variants = badges.map((b) => b.attributes('data-variant'))

    expect(variants).toContain('orange') // ADMIN
    expect(variants).toContain('purple') // SUB_ADMIN
    expect(variants).toContain('brand') // MEMBER
  })

  it('shows Promote button for platform admin when member is MEMBER role', async () => {
    const { wrapper } = await mountComponent({ role: 'ADMIN' })
    await flushPromises()

    const buttons = wrapper.findAll('button')
    const promoteButtons = buttons.filter((b) => b.text().includes('Promote'))

    // Only the MEMBER-role member should get a Promote button
    expect(promoteButtons.length).toBeGreaterThan(0)

    // ADMIN and SUB_ADMIN should NOT get Promote
    const tableRows = wrapper.findAll('tbody tr')
    // Row 0 = ADMIN role, Row 1 = SUB_ADMIN role — neither should have Promote
    // Row 2 = MEMBER role — should have Promote
    const lastRowText = tableRows[2].text()
    expect(lastRowText).toContain('Promote')

    const firstRowText = tableRows[0].text()
    expect(firstRowText).not.toContain('Promote')
  })

  it('hides Promote button for non-admin users', async () => {
    const { wrapper } = await mountComponent({ role: 'MEMBER', userSigRole: null })
    await flushPromises()

    const buttons = wrapper.findAll('button')
    const promoteButtons = buttons.filter((b) => b.text().includes('Promote'))
    expect(promoteButtons.length).toBe(0)
  })

  it('shows Remove button for SIG admin but not for own user or other ADMIN members', async () => {
    const { wrapper } = await mountComponent({
      role: 'MEMBER',
      userSigRole: 'ADMIN',
      currentUserId: 'user-2', // current user is user-2 (SUB_ADMIN)
    })
    await flushPromises()

    // Scope to desktop table view to avoid double-counting with mobile cards
    const table = wrapper.find('table')
    const tableRows = table.findAll('tbody tr')

    // Row for user-2 (self) should NOT have Remove
    const selfRow = tableRows[1] // user-2 is SUB_ADMIN at index 1
    expect(selfRow.text()).not.toContain('Remove')

    // Row 0 = ADMIN member — SIG admin (non-platform-admin) should NOT see Remove for ADMIN
    expect(tableRows[0].text()).not.toContain('Remove')
    // Row 2 = MEMBER — SIG admin should see Remove for MEMBER
    expect(tableRows[2].text()).toContain('Remove')
  })

  it('shows EmptyState when no members', async () => {
    const { wrapper } = await mountComponent({ members: [], total: 0 })
    await flushPromises()

    expect(wrapper.find('.empty-state').exists()).toBe(true)
    expect(wrapper.find('table').exists()).toBe(false)
  })

  it('shows confirmation modal when Remove is clicked instead of immediately removing', async () => {
    const { wrapper } = await mountComponent({
      role: 'MEMBER',
      userSigRole: 'ADMIN',
      currentUserId: 'user-2',
    })
    await flushPromises()

    // Modal should not be visible initially
    expect(wrapper.find('.base-modal').exists()).toBe(false)

    // Click Remove on a member in the desktop table
    const table = wrapper.find('table')
    const removeButtons = table.findAll('button').filter((b) => b.text().includes('Remove'))
    expect(removeButtons.length).toBeGreaterThan(0)

    await removeButtons[0].trigger('click')
    await flushPromises()

    // Modal should appear
    expect(wrapper.find('.base-modal').exists()).toBe(true)

    // removeMember API should NOT have been called
    expect(mockRemoveMember).not.toHaveBeenCalled()
  })

  it('displays member name in removal confirmation dialog', async () => {
    const { wrapper } = await mountComponent({
      role: 'MEMBER',
      userSigRole: 'ADMIN',
      currentUserId: 'user-2',
    })
    await flushPromises()

    // Click Remove on user-3 (Regular Member) — SIG admin can remove MEMBER but not ADMIN
    const table = wrapper.find('table')
    const tableRows = table.findAll('tbody tr')

    const memberRow = tableRows[2] // user-3 = Regular Member
    const removeBtn = memberRow.findAll('button').find((b) => b.text().includes('Remove'))
    expect(removeBtn).toBeTruthy()

    await removeBtn!.trigger('click')
    await flushPromises()

    // Modal should contain the member's display name
    const modal = wrapper.find('.base-modal')
    expect(modal.exists()).toBe(true)
    expect(modal.text()).toContain('Regular Member')
  })

  it('calls removeMember API after confirming in modal', async () => {
    mockRemoveMember.mockResolvedValue({})
    mockGetSigMembers.mockResolvedValue({ members: sampleMembers, total: sampleMembers.length })

    const { wrapper } = await mountComponent({
      role: 'MEMBER',
      userSigRole: 'ADMIN',
      currentUserId: 'user-2',
    })
    await flushPromises()

    // Click Remove on user-3 (Regular Member) in the table
    const table = wrapper.find('table')
    const tableRows = table.findAll('tbody tr')
    const memberRow = tableRows[2] // user-3 = Regular Member
    const removeBtn = memberRow.findAll('button').find((b) => b.text().includes('Remove'))
    expect(removeBtn).toBeTruthy()

    await removeBtn!.trigger('click')
    await flushPromises()

    // Modal should be visible
    const modal = wrapper.find('.base-modal')
    expect(modal.exists()).toBe(true)

    // Click the danger confirm button (the "Remove" button inside modal)
    const modalButtons = modal.findAll('button')
    const confirmBtn = modalButtons.find((b) => b.text().includes('Remove'))
    expect(confirmBtn).toBeTruthy()

    await confirmBtn!.trigger('click')
    await flushPromises()

    // removeMember should have been called with correct SIG id and user id
    expect(mockRemoveMember).toHaveBeenCalledWith('sig-1', 'user-3')
  })

  it('closes modal without removing when cancel is clicked', async () => {
    const { wrapper } = await mountComponent({
      role: 'MEMBER',
      userSigRole: 'ADMIN',
      currentUserId: 'user-2',
    })
    await flushPromises()

    // Click Remove on a member
    const table = wrapper.find('table')
    const removeButtons = table.findAll('button').filter((b) => b.text().includes('Remove'))
    await removeButtons[0].trigger('click')
    await flushPromises()

    // Modal should be visible
    expect(wrapper.find('.base-modal').exists()).toBe(true)

    // Click Cancel button inside the modal
    const modal = wrapper.find('.base-modal')
    const modalButtons = modal.findAll('button')
    const cancelBtn = modalButtons.find((b) => b.text().includes('Cancel'))
    expect(cancelBtn).toBeTruthy()

    await cancelBtn!.trigger('click')
    await flushPromises()

    // Modal should close
    expect(wrapper.find('.base-modal').exists()).toBe(false)

    // removeMember should never have been called
    expect(mockRemoveMember).not.toHaveBeenCalled()
  })

  it('shows Demote button for platform admin when member is SUB_ADMIN', async () => {
    const { wrapper } = await mountComponent({ role: 'ADMIN' })
    await flushPromises()

    const table = wrapper.find('table')
    const tableRows = table.findAll('tbody tr')

    // Row 1 = SUB_ADMIN — should have Demote
    expect(tableRows[1].text()).toContain('Demote')

    // Row 0 = ADMIN, Row 2 = MEMBER — should NOT have Demote
    expect(tableRows[0].text()).not.toContain('Demote')
    expect(tableRows[2].text()).not.toContain('Demote')
  })

  it('shows Demote button for SIG owner (ADMIN role) on SUB_ADMIN members', async () => {
    const { wrapper } = await mountComponent({
      role: 'MEMBER',
      userSigRole: 'ADMIN',
      currentUserId: 'user-1',
    })
    await flushPromises()

    const table = wrapper.find('table')
    const tableRows = table.findAll('tbody tr')

    // Row 1 = SUB_ADMIN — should have Demote
    expect(tableRows[1].text()).toContain('Demote')
  })

  it('hides Demote button for SUB_ADMIN users (only owners can demote)', async () => {
    const { wrapper } = await mountComponent({
      role: 'MEMBER',
      userSigRole: 'SUB_ADMIN',
      currentUserId: 'user-2',
    })
    await flushPromises()

    const buttons = wrapper.findAll('button')
    const demoteButtons = buttons.filter((b) => b.text().includes('Demote'))
    expect(demoteButtons.length).toBe(0)
  })

  it('shows demote confirmation modal with correct member name', async () => {
    const { wrapper } = await mountComponent({ role: 'ADMIN', currentUserId: 'user-1' })
    await flushPromises()

    // Click Demote on user-2 (SUB_ADMIN) in the table
    const table = wrapper.find('table')
    const tableRows = table.findAll('tbody tr')
    const subAdminRow = tableRows[1]
    const demoteBtn = subAdminRow.findAll('button').find((b) => b.text().includes('Demote'))
    expect(demoteBtn).toBeTruthy()

    await demoteBtn!.trigger('click')
    await flushPromises()

    // Modal should show the sub-admin's display name
    const modal = wrapper.find('.base-modal')
    expect(modal.exists()).toBe(true)
    expect(modal.text()).toContain('Sub Admin')

    // demoteSubAdmin API should NOT have been called yet
    expect(mockDemoteSubAdmin).not.toHaveBeenCalled()
  })

  it('calls demoteSubAdmin API after confirming demotion in modal', async () => {
    mockDemoteSubAdmin.mockResolvedValue({})
    mockGetSigMembers.mockResolvedValue({ members: sampleMembers, total: sampleMembers.length })

    const { wrapper } = await mountComponent({
      role: 'ADMIN',
      currentUserId: 'user-1',
    })
    await flushPromises()

    // Click Demote on user-2 (SUB_ADMIN) in the table
    const table = wrapper.find('table')
    const tableRows = table.findAll('tbody tr')
    const subAdminRow = tableRows[1]
    const demoteBtn = subAdminRow.findAll('button').find((b) => b.text().includes('Demote'))
    expect(demoteBtn).toBeTruthy()

    await demoteBtn!.trigger('click')
    await flushPromises()

    // Modal should be visible with demote title
    const modal = wrapper.find('.base-modal')
    expect(modal.exists()).toBe(true)
    expect(modal.text()).toContain('Sub Admin')

    // Click the confirm button inside modal
    const modalButtons = modal.findAll('button')
    const confirmBtn = modalButtons.find((b) => b.text().includes('Demote'))
    expect(confirmBtn).toBeTruthy()

    await confirmBtn!.trigger('click')
    await flushPromises()

    expect(mockDemoteSubAdmin).toHaveBeenCalledWith('sig-1', 'user-2')
  })

  it('closes demote modal without calling API when cancel is clicked', async () => {
    const { wrapper } = await mountComponent({ role: 'ADMIN', currentUserId: 'user-1' })
    await flushPromises()

    const table = wrapper.find('table')
    const tableRows = table.findAll('tbody tr')
    const subAdminRow = tableRows[1]
    const demoteBtn = subAdminRow.findAll('button').find((b) => b.text().includes('Demote'))
    expect(demoteBtn).toBeTruthy()

    await demoteBtn!.trigger('click')
    await flushPromises()

    expect(wrapper.find('.base-modal').exists()).toBe(true)

    const modal = wrapper.find('.base-modal')
    const cancelBtn = modal.findAll('button').find((b) => b.text().includes('Cancel'))
    expect(cancelBtn).toBeTruthy()

    await cancelBtn!.trigger('click')
    await flushPromises()

    expect(wrapper.find('.base-modal').exists()).toBe(false)
    expect(mockDemoteSubAdmin).not.toHaveBeenCalled()
  })

  it('shows error toast when demoteSubAdmin API fails', async () => {
    mockDemoteSubAdmin.mockRejectedValue({ response: { data: { detail: 'Demote failed' } } })
    mockGetSigMembers.mockResolvedValue({ members: sampleMembers, total: sampleMembers.length })

    const { wrapper } = await mountComponent({ role: 'ADMIN', currentUserId: 'user-1' })
    await flushPromises()

    const table = wrapper.find('table')
    const tableRows = table.findAll('tbody tr')
    const subAdminRow = tableRows[1]
    const demoteBtn = subAdminRow.findAll('button').find((b) => b.text().includes('Demote'))
    await demoteBtn!.trigger('click')
    await flushPromises()

    const modal = wrapper.find('.base-modal')
    const confirmBtn = modal.findAll('button').find((b) => b.text().includes('Demote'))
    await confirmBtn!.trigger('click')
    await flushPromises()

    const { useToastStore } = await import('@/stores/toast')
    const toast = useToastStore()
    expect(toast.toasts.length).toBeGreaterThan(0)
    expect(toast.toasts[0].type).toBe('error')
  })

  it('SUB_ADMIN cannot see Remove button for ADMIN members', async () => {
    const { wrapper } = await mountComponent({
      role: 'MEMBER',
      userSigRole: 'SUB_ADMIN',
      currentUserId: 'user-2', // current user is the SUB_ADMIN
    })
    await flushPromises()

    // Scope to desktop table view
    const table = wrapper.find('table')
    const tableRows = table.findAll('tbody tr')

    // Row 0 = user-1 (ADMIN role) — SUB_ADMIN should NOT see Remove for ADMIN
    const adminRow = tableRows[0]
    expect(adminRow.text()).not.toContain('Remove')

    // Row 2 = user-3 (MEMBER role) — SUB_ADMIN should see Remove for MEMBER
    const memberRow = tableRows[2]
    expect(memberRow.text()).toContain('Remove')
  })

  it('platform admin can see Remove button for ADMIN members', async () => {
    const { wrapper } = await mountComponent({
      role: 'ADMIN', // platform admin
      currentUserId: 'current-user',
    })
    await flushPromises()

    // Scope to desktop table view
    const table = wrapper.find('table')
    const tableRows = table.findAll('tbody tr')

    // Row 0 = user-1 (ADMIN role) — platform admin should see Remove
    const adminRow = tableRows[0]
    expect(adminRow.text()).toContain('Remove')
  })

  describe('pagination', () => {
    it('does not show pagination when total members fit in one page', async () => {
      const { wrapper } = await mountComponent({
        members: sampleMembers,
        total: 3,
      })
      await flushPromises()

      expect(wrapper.find('.base-pagination').exists()).toBe(false)
    })

    it('shows pagination when members exceed page size', async () => {
      // Create enough members to require pagination (total > PAGE_SIZE)
      const { wrapper } = await mountComponent({
        members: sampleMembers,
        total: 25, // total > PAGE_SIZE of 20
      })
      await flushPromises()

      expect(wrapper.find('.base-pagination').exists()).toBe(true)
    })

    it('fetches members with pagination params', async () => {
      await mountComponent()
      await flushPromises()

      // Should be called with offset and limit params
      expect(mockGetSigMembers).toHaveBeenCalledWith('sig-1', {
        offset: 0,
        limit: 20,
      })
    })

    it('page change triggers new fetch with updated offset', async () => {
      mockGetSigMembers.mockResolvedValue({ members: sampleMembers, total: 25 })

      const { wrapper } = await mountComponent({
        members: sampleMembers,
        total: 25,
      })
      await flushPromises()
      vi.clearAllMocks()

      mockGetSigMembers.mockResolvedValue({ members: sampleMembers, total: 25 })

      // Click on pagination to go to page 2
      const pagination = wrapper.find('.base-pagination')
      await pagination.trigger('click')
      await flushPromises()

      expect(mockGetSigMembers).toHaveBeenCalledWith('sig-1', {
        offset: 20,
        limit: 20,
      })
    })

    it('displays total member count in heading', async () => {
      const { wrapper } = await mountComponent({
        members: sampleMembers,
        total: 3,
      })
      await flushPromises()

      expect(wrapper.text()).toContain('Members')
      expect(wrapper.text()).toContain('3')
    })
  })

  it('shows Promote button for SIG owner (ADMIN role) when member is MEMBER', async () => {
    const { wrapper } = await mountComponent({
      role: 'MEMBER', // NOT platform admin
      userSigRole: 'ADMIN', // IS SIG owner
      currentUserId: 'user-1', // current user is the SIG admin
    })
    await flushPromises()

    const table = wrapper.find('table')
    const tableRows = table.findAll('tbody tr')

    // Row 2 = user-3 (MEMBER role) — SIG owner should see Promote
    expect(tableRows[2].text()).toContain('Promote')

    // Row 0 = user-1 (ADMIN) and Row 1 = user-2 (SUB_ADMIN) should NOT have Promote
    expect(tableRows[0].text()).not.toContain('Promote')
    expect(tableRows[1].text()).not.toContain('Promote')
  })

  it('hides Promote button for SUB_ADMIN SIG members', async () => {
    const { wrapper } = await mountComponent({
      role: 'MEMBER',
      userSigRole: 'SUB_ADMIN',
      currentUserId: 'user-2',
    })
    await flushPromises()

    const buttons = wrapper.findAll('button')
    const promoteButtons = buttons.filter((b) => b.text().includes('Promote'))
    expect(promoteButtons.length).toBe(0)
  })

  it('SIG owner Promote button calls assignSubAdmin API with correct args', async () => {
    mockAssignSubAdmin.mockResolvedValue({})
    mockGetSigMembers.mockResolvedValue({ members: sampleMembers, total: sampleMembers.length })

    const { wrapper } = await mountComponent({
      role: 'MEMBER',
      userSigRole: 'ADMIN',
      currentUserId: 'user-1',
    })
    await flushPromises()

    const table = wrapper.find('table')
    const tableRows = table.findAll('tbody tr')
    const memberRow = tableRows[2] // user-3 = MEMBER
    const promoteBtn = memberRow.findAll('button').find((b) => b.text().includes('Promote'))
    expect(promoteBtn).toBeTruthy()

    await promoteBtn!.trigger('click')
    await flushPromises()

    expect(mockAssignSubAdmin).toHaveBeenCalledWith('sig-1', 'user-3')
  })

  it('shows Promote button in mobile view for SIG owner', async () => {
    const { wrapper } = await mountComponent({
      role: 'MEMBER',
      userSigRole: 'ADMIN',
      currentUserId: 'user-1',
    })
    await flushPromises()

    // Find mobile card view (the grid that's hidden on md+)
    const mobileCards = wrapper.findAll('.base-card')
    // Card for user-3 (MEMBER role, index 2)
    const memberCard = mobileCards[2]
    expect(memberCard.text()).toContain('Promote')
  })

  describe('refreshSigRole integration', () => {
    it('calls refreshSigRole after successful promote (assignSubAdmin)', async () => {
      mockAssignSubAdmin.mockResolvedValue({})
      mockGetSigMembers.mockResolvedValue({ members: sampleMembers, total: sampleMembers.length })

      const { wrapper } = await mountComponent({
        role: 'MEMBER',
        userSigRole: 'ADMIN',
        currentUserId: 'user-1',
      })
      await flushPromises()

      const table = wrapper.find('table')
      const tableRows = table.findAll('tbody tr')
      const memberRow = tableRows[2] // user-3 = MEMBER
      const promoteBtn = memberRow.findAll('button').find((b) => b.text().includes('Promote'))
      expect(promoteBtn).toBeTruthy()

      await promoteBtn!.trigger('click')
      await flushPromises()

      expect(mockAssignSubAdmin).toHaveBeenCalledWith('sig-1', 'user-3')
      expect(mockRefreshSigRole).toHaveBeenCalledTimes(1)
    })

    it('calls refreshSigRole after successful demote', async () => {
      mockDemoteSubAdmin.mockResolvedValue({})
      mockGetSigMembers.mockResolvedValue({ members: sampleMembers, total: sampleMembers.length })

      const { wrapper } = await mountComponent({
        role: 'ADMIN',
        currentUserId: 'user-1',
      })
      await flushPromises()
      mockRefreshSigRole.mockClear()

      const table = wrapper.find('table')
      const tableRows = table.findAll('tbody tr')
      const subAdminRow = tableRows[1] // user-2 = SUB_ADMIN
      const demoteBtn = subAdminRow.findAll('button').find((b) => b.text().includes('Demote'))
      expect(demoteBtn).toBeTruthy()

      await demoteBtn!.trigger('click')
      await flushPromises()

      // Modal should be visible — click confirm
      const modal = wrapper.find('.base-modal')
      expect(modal.exists()).toBe(true)
      const confirmBtn = modal.findAll('button').find((b) => b.text().includes('Demote'))
      expect(confirmBtn).toBeTruthy()

      mockRefreshSigRole.mockClear()
      await confirmBtn!.trigger('click')
      await flushPromises()

      expect(mockDemoteSubAdmin).toHaveBeenCalledWith('sig-1', 'user-2')
      expect(mockRefreshSigRole).toHaveBeenCalled()
    })

    it('calls refreshSigRole after successful remove', async () => {
      mockRemoveMember.mockResolvedValue({})
      mockGetSigMembers.mockResolvedValue({ members: sampleMembers, total: sampleMembers.length })

      const { wrapper } = await mountComponent({
        role: 'MEMBER',
        userSigRole: 'ADMIN',
        currentUserId: 'user-2',
      })
      await flushPromises()
      mockRefreshSigRole.mockClear()

      // Click Remove on user-3 (Regular Member) in the table
      const table = wrapper.find('table')
      const tableRows = table.findAll('tbody tr')
      const memberRow = tableRows[2] // user-3 = Regular Member
      const removeBtn = memberRow.findAll('button').find((b) => b.text().includes('Remove'))
      expect(removeBtn).toBeTruthy()

      await removeBtn!.trigger('click')
      await flushPromises()

      // Modal should be visible — click confirm
      const modal = wrapper.find('.base-modal')
      expect(modal.exists()).toBe(true)
      const confirmBtn = modal.findAll('button').find((b) => b.text().includes('Remove'))
      expect(confirmBtn).toBeTruthy()

      mockRefreshSigRole.mockClear()
      await confirmBtn!.trigger('click')
      await flushPromises()

      expect(mockRemoveMember).toHaveBeenCalledWith('sig-1', 'user-3')
      expect(mockRefreshSigRole).toHaveBeenCalled()
    })

    it('does not call refreshSigRole when promote fails', async () => {
      mockAssignSubAdmin.mockRejectedValue(new Error('Promote failed'))
      mockGetSigMembers.mockResolvedValue({ members: sampleMembers, total: sampleMembers.length })

      const { wrapper } = await mountComponent({
        role: 'MEMBER',
        userSigRole: 'ADMIN',
        currentUserId: 'user-1',
      })
      await flushPromises()

      const table = wrapper.find('table')
      const tableRows = table.findAll('tbody tr')
      const memberRow = tableRows[2]
      const promoteBtn = memberRow.findAll('button').find((b) => b.text().includes('Promote'))

      await promoteBtn!.trigger('click')
      await flushPromises()

      expect(mockAssignSubAdmin).toHaveBeenCalled()
      expect(mockRefreshSigRole).not.toHaveBeenCalled()
    })

    it('does not call refreshSigRole when demote fails', async () => {
      mockDemoteSubAdmin.mockRejectedValue(new Error('Demote failed'))
      mockGetSigMembers.mockResolvedValue({ members: sampleMembers, total: sampleMembers.length })

      const { wrapper } = await mountComponent({
        role: 'ADMIN',
        currentUserId: 'user-1',
      })
      await flushPromises()

      const table = wrapper.find('table')
      const tableRows = table.findAll('tbody tr')
      const subAdminRow = tableRows[1]
      const demoteBtn = subAdminRow.findAll('button').find((b) => b.text().includes('Demote'))

      await demoteBtn!.trigger('click')
      await flushPromises()

      const modal = wrapper.find('.base-modal')
      const confirmBtn = modal.findAll('button').find((b) => b.text().includes('Demote'))

      await confirmBtn!.trigger('click')
      await flushPromises()

      expect(mockDemoteSubAdmin).toHaveBeenCalled()
      expect(mockRefreshSigRole).not.toHaveBeenCalled()
    })

    it('does not call refreshSigRole when remove fails', async () => {
      mockRemoveMember.mockRejectedValue(new Error('Remove failed'))
      mockGetSigMembers.mockResolvedValue({ members: sampleMembers, total: sampleMembers.length })

      const { wrapper } = await mountComponent({
        role: 'MEMBER',
        userSigRole: 'ADMIN',
        currentUserId: 'user-2',
      })
      await flushPromises()

      const table = wrapper.find('table')
      const tableRows = table.findAll('tbody tr')
      const memberRow = tableRows[2]
      const removeBtn = memberRow.findAll('button').find((b) => b.text().includes('Remove'))

      await removeBtn!.trigger('click')
      await flushPromises()

      const modal = wrapper.find('.base-modal')
      const confirmBtn = modal.findAll('button').find((b) => b.text().includes('Remove'))

      await confirmBtn!.trigger('click')
      await flushPromises()

      expect(mockRemoveMember).toHaveBeenCalled()
      expect(mockRefreshSigRole).not.toHaveBeenCalled()
    })
  })
})

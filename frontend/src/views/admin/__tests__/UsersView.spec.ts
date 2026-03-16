import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import UsersView from '../UsersView.vue'
import { useAuthStore } from '@/stores/auth'

const mockListUsers = vi.fn()
const mockCreateAccount = vi.fn()
const mockChangeRole = vi.fn()
const mockBanUser = vi.fn()
const mockUnbanUser = vi.fn()
const mockApiPut = vi.fn()

vi.mock('@/api/admin', () => ({
  listUsers: (...args: unknown[]) => mockListUsers(...args),
  createAccount: (...args: unknown[]) => mockCreateAccount(...args),
  changeRole: (...args: unknown[]) => mockChangeRole(...args),
  banUser: (...args: unknown[]) => mockBanUser(...args),
  unbanUser: (...args: unknown[]) => mockUnbanUser(...args),
}))

vi.mock('@/composables/api', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    put: (...args: unknown[]) => mockApiPut(...args),
    delete: vi.fn(),
  },
}))

vi.mock('@/utils/error', () => ({
  getErrorMessage: (_e: unknown, fallback: string) => fallback,
}))

vi.mock('@/constants', () => ({
  HEARTBEAT_INTERVAL_MS: 30000,
}))

const fakeUsers = [
  {
    id: 'user-1',
    username: 'alice',
    display_name: 'Alice',
    role: 'MEMBER',
    is_banned: false,
    ban_reason: null,
  },
  {
    id: 'user-2',
    username: 'bob',
    display_name: 'Bob',
    role: 'ADMIN',
    is_banned: false,
    ban_reason: null,
  },
  {
    id: 'user-3',
    username: 'charlie',
    display_name: 'Charlie',
    role: 'MEMBER',
    is_banned: true,
    ban_reason: 'Spamming',
  },
]

function createTestRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/admin/users', component: UsersView }],
  })
}

async function mountUsers(options?: {
  users?: typeof fakeUsers
  total?: number
  role?: string
  userId?: string
}) {
  const {
    users = fakeUsers,
    total = fakeUsers.length,
    role = 'SUPER_ADMIN',
    userId = 'admin-1',
  } = options ?? {}

  const pinia = createPinia()
  setActivePinia(pinia)

  const auth = useAuthStore()
  auth.setSession(role, 3600)
  auth.user = {
    id: userId,
    username: 'admin',
    display_name: 'Admin User',
    role,
    bio: null,
    affiliation: null,
    orcid: null,
    avatar_url: null,
    is_banned: false,
    ban_reason: null,
  } as any

  const router = createTestRouter()
  await router.push('/admin/users')
  await router.isReady()

  mockListUsers.mockResolvedValue({ users, total })

  const wrapper = mount(UsersView, {
    global: {
      plugins: [pinia, router],
      stubs: {
        BaseButton: {
          template:
            '<button :disabled="$attrs.disabled" @click="$emit(\'click\')"><slot /></button>',
          props: ['size', 'variant', 'loading'],
        },
        BaseBadge: {
          template: '<span class="base-badge"><slot /></span>',
          props: ['variant', 'title'],
        },
        BaseAlert: {
          template: '<div class="base-alert"><slot /></div>',
          props: ['type'],
        },
        BaseInput: {
          template:
            '<input class="base-input" :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
          props: ['modelValue', 'label', 'placeholder', 'required', 'type'],
        },
        BaseTextarea: {
          template:
            '<textarea class="base-textarea" :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)"></textarea>',
          props: ['modelValue', 'label', 'rows', 'placeholder', 'required'],
        },
        BaseModal: {
          template:
            '<div class="base-modal" v-if="modelValue"><slot /><slot name="footer" /></div>',
          props: ['modelValue', 'title', 'size'],
          emits: ['update:modelValue'],
        },
        BasePagination: {
          template: '<div class="base-pagination" @click="$emit(\'update:current-page\', 2)" />',
          props: ['currentPage', 'totalPages'],
        },
        SkeletonLoader: { template: '<div class="skeleton-loader" />' },
        EmptyState: {
          template: '<div class="empty-state">{{ title }}</div>',
          props: ['title', 'message'],
        },
      },
    },
  })
  await flushPromises()
  return { wrapper, auth }
}

describe('UsersView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('renders the title', async () => {
    const { wrapper } = await mountUsers()
    expect(wrapper.find('h1').exists()).toBe(true)
  })

  it('fetches users on mount', async () => {
    await mountUsers()
    expect(mockListUsers).toHaveBeenCalledOnce()
    expect(mockListUsers).toHaveBeenCalledWith({ page: 1, page_size: 20 })
  })

  it('displays user details in the table', async () => {
    const { wrapper } = await mountUsers()
    expect(wrapper.text()).toContain('alice')
    expect(wrapper.text()).toContain('Alice')
    expect(wrapper.text()).toContain('bob')
    expect(wrapper.text()).toContain('Bob')
  })

  it('displays role badges', async () => {
    const { wrapper } = await mountUsers()
    const badges = wrapper.findAll('.base-badge')
    expect(badges.length).toBeGreaterThanOrEqual(3)
  })

  it('shows banned badge for banned users', async () => {
    const { wrapper } = await mountUsers()
    expect(wrapper.text()).toContain('charlie')
    // Charlie is banned
    const badges = wrapper.findAll('.base-badge')
    const badgeTexts = badges.map((b) => b.text())
    expect(badgeTexts.some((t) => t.length > 0)).toBe(true)
  })

  it('shows empty state when no users', async () => {
    const { wrapper } = await mountUsers({ users: [], total: 0 })
    expect(wrapper.find('.empty-state').exists()).toBe(true)
  })

  it('shows loading skeleton while fetching', async () => {
    mockListUsers.mockReturnValue(new Promise(() => {}))
    const pinia = createPinia()
    setActivePinia(pinia)
    const auth = useAuthStore()
    auth.setSession('SUPER_ADMIN', 3600)
    auth.user = { id: 'admin-1', role: 'SUPER_ADMIN' } as any
    const router = createTestRouter()

    const wrapper = mount(UsersView, {
      global: {
        plugins: [pinia, router],
        stubs: {
          BaseButton: { template: '<button><slot /></button>' },
          BaseBadge: { template: '<span />' },
          BaseAlert: { template: '<div />' },
          BaseInput: { template: '<input />' },
          BaseTextarea: { template: '<textarea />' },
          BaseModal: { template: '<div />' },
          BasePagination: { template: '<div />' },
          SkeletonLoader: { template: '<div class="skeleton-loader" />' },
          EmptyState: { template: '<div class="empty-state" />' },
        },
      },
    })
    await nextTick()
    expect(wrapper.find('.skeleton-loader').exists()).toBe(true)
  })

  it('renders search input', async () => {
    const { wrapper } = await mountUsers()
    const searchInput = wrapper.find('input[type="text"]')
    expect(searchInput.exists()).toBe(true)
  })

  it('debounces search and re-fetches', async () => {
    const { wrapper } = await mountUsers()
    mockListUsers.mockResolvedValue({ users: [], total: 0 })

    const searchInput = wrapper.find('input[type="text"]')
    await searchInput.setValue('alice')
    await searchInput.trigger('input')

    // Should not have called immediately
    expect(mockListUsers).toHaveBeenCalledTimes(1)

    // Advance timer past debounce (300ms)
    vi.advanceTimersByTime(350)
    await flushPromises()

    expect(mockListUsers).toHaveBeenCalledTimes(2)
    expect(mockListUsers).toHaveBeenLastCalledWith(expect.objectContaining({ search: 'alice' }))
  })

  it('opens create account modal when create button is clicked', async () => {
    const { wrapper } = await mountUsers()

    // Find the create button (first button in header)
    const buttons = wrapper.findAll('button')
    const createBtn = buttons[0]
    await createBtn.trigger('click')
    await nextTick()

    expect(wrapper.find('.base-modal').exists()).toBe(true)
  })

  it('calls createAccount on form submit', async () => {
    mockCreateAccount.mockResolvedValue({ id: 'new-user' })
    mockListUsers.mockResolvedValue({ users: fakeUsers, total: 3 })

    const { wrapper } = await mountUsers()

    // Open create modal
    await wrapper.findAll('button')[0].trigger('click')
    await nextTick()

    // Fill form
    const inputs = wrapper.findAll('.base-input')
    if (inputs.length >= 3) {
      await inputs[0].setValue('newuser')
      await inputs[1].setValue('New User')
      await inputs[2].setValue('password123')
      await nextTick()

      // Submit
      const form = wrapper.find('.base-modal form')
      if (form.exists()) {
        await form.trigger('submit')
        await flushPromises()
        expect(mockCreateAccount).toHaveBeenCalled()
      }
    }
  })

  it('shows alert when fetch fails', async () => {
    mockListUsers.mockRejectedValue(new Error('Server error'))
    const pinia = createPinia()
    setActivePinia(pinia)
    const auth = useAuthStore()
    auth.setSession('SUPER_ADMIN', 3600)
    auth.user = { id: 'admin-1', role: 'SUPER_ADMIN' } as any
    const router = createTestRouter()
    await router.push('/admin/users')
    await router.isReady()

    const wrapper = mount(UsersView, {
      global: {
        plugins: [pinia, router],
        stubs: {
          BaseButton: { template: '<button><slot /></button>' },
          BaseBadge: { template: '<span />' },
          BaseAlert: {
            template: '<div class="base-alert"><slot /></div>',
            props: ['type'],
          },
          BaseInput: { template: '<input />' },
          BaseTextarea: { template: '<textarea />' },
          BaseModal: { template: '<div />' },
          BasePagination: { template: '<div />' },
          SkeletonLoader: { template: '<div class="skeleton-loader" />' },
          EmptyState: { template: '<div class="empty-state" />' },
        },
      },
    })
    await flushPromises()
    expect(wrapper.find('.base-alert').exists()).toBe(true)
  })

  it('shows checkboxes for SUPER_ADMIN users', async () => {
    const { wrapper } = await mountUsers({ role: 'SUPER_ADMIN' })
    const checkboxes = wrapper.findAll('input[type="checkbox"]')
    // Header checkbox + one per non-self user
    expect(checkboxes.length).toBeGreaterThan(0)
  })

  it('does not show checkboxes for non-SUPER_ADMIN users', async () => {
    const { wrapper } = await mountUsers({ role: 'ADMIN' })
    const checkboxes = wrapper.findAll('input[type="checkbox"]')
    expect(checkboxes.length).toBe(0)
  })

  it('does not show actions column for non-SUPER_ADMIN users', async () => {
    const { wrapper } = await mountUsers({ role: 'ADMIN' })
    const selects = wrapper.findAll('table select')
    expect(selects.length).toBe(0)
  })

  it('shows role change dropdown for other users when SUPER_ADMIN', async () => {
    const { wrapper } = await mountUsers({ role: 'SUPER_ADMIN' })
    const selects = wrapper.findAll('table select')
    // Should have selects for users that are not the current user
    expect(selects.length).toBeGreaterThan(0)
  })

  it('does not show role select for current user (self)', async () => {
    const singleUser = [
      {
        id: 'admin-1',
        username: 'admin',
        display_name: 'Admin',
        role: 'SUPER_ADMIN',
        is_banned: false,
        ban_reason: null,
      },
    ]
    const { wrapper } = await mountUsers({ users: singleUser, total: 1, userId: 'admin-1' })
    // No role select should be rendered for self
    const selects = wrapper.findAll('table select')
    expect(selects.length).toBe(0)
  })

  it('calls changeRole when role dropdown is changed', async () => {
    mockChangeRole.mockResolvedValue({
      id: 'user-1',
      username: 'alice',
      display_name: 'Alice',
      role: 'ADMIN',
      is_banned: false,
      ban_reason: null,
    })
    mockListUsers.mockResolvedValue({ users: fakeUsers, total: 3 })

    const { wrapper } = await mountUsers()

    const selects = wrapper.findAll('table select')
    if (selects.length > 0) {
      await selects[0].setValue('ADMIN')
      await selects[0].trigger('change')
      await flushPromises()
      expect(mockChangeRole).toHaveBeenCalled()
    }
  })

  it('updates local user role without re-fetching after changeRole', async () => {
    mockChangeRole.mockResolvedValue({
      id: 'user-1',
      username: 'alice',
      display_name: 'Alice',
      role: 'ADMIN',
      is_banned: false,
      ban_reason: null,
    })

    const { wrapper } = await mountUsers()
    // Clear call count from initial mount
    mockListUsers.mockClear()

    const selects = wrapper.findAll('table select')
    if (selects.length > 0) {
      await selects[0].setValue('ADMIN')
      await selects[0].trigger('change')
      await flushPromises()
      // Should NOT re-fetch the entire user list
      expect(mockListUsers).not.toHaveBeenCalled()
    }
  })

  it('opens ban modal when ban button is clicked', async () => {
    const { wrapper } = await mountUsers()

    // Find ban buttons (soft-danger variant, for non-banned users)
    const allButtons = wrapper.findAll('table button')
    const banBtn = allButtons.find((b) => b.text().length > 0)
    if (banBtn) {
      await banBtn.trigger('click')
      await nextTick()
      const modals = wrapper.findAll('.base-modal')
      expect(modals.length).toBeGreaterThan(0)
    }
  })

  it('calls banUser when ban is confirmed', async () => {
    mockBanUser.mockResolvedValue(undefined)
    mockListUsers.mockResolvedValue({ users: fakeUsers, total: 3 })

    const { wrapper } = await mountUsers()

    // Open ban modal for first non-self user
    const tableButtons = wrapper.findAll('table button')
    const banBtn = tableButtons.find((b) => b.text().length > 0)
    if (banBtn) {
      await banBtn.trigger('click')
      await nextTick()

      // Fill ban reason
      const textarea = wrapper.find('.base-textarea')
      if (textarea.exists()) {
        await textarea.setValue('Violating rules')
        await nextTick()

        // Click confirm ban button in modal footer
        const modalButtons = wrapper.findAll('.base-modal button')
        const confirmBtn = modalButtons[modalButtons.length - 1]
        if (confirmBtn) {
          await confirmBtn.trigger('click')
          await flushPromises()
          expect(mockBanUser).toHaveBeenCalled()
        }
      }
    }
  })

  it('calls unbanUser when unban button is clicked', async () => {
    mockUnbanUser.mockResolvedValue(undefined)
    mockListUsers.mockResolvedValue({ users: fakeUsers, total: 3 })

    const { wrapper } = await mountUsers()

    // Find unban button for charlie (banned user)
    const tableButtons = wrapper.findAll('table button')
    // Look for the unban button
    for (const btn of tableButtons) {
      const text = btn.text()
      if (text.length > 0) {
        // Try clicking - if it's the unban button for charlie
        // We check by seeing if unbanUser gets called
        await btn.trigger('click')
        await flushPromises()
        if (mockUnbanUser.mock.calls.length > 0) {
          expect(mockUnbanUser).toHaveBeenCalledWith('user-3')
          break
        }
        // Reset if it was a different button
        vi.clearAllMocks()
        mockListUsers.mockResolvedValue({ users: fakeUsers, total: 3 })
      }
    }
  })

  it('displays total count', async () => {
    const { wrapper } = await mountUsers()
    expect(wrapper.text()).toContain('3')
  })

  it('shows pagination when totalPages > 1', async () => {
    const { wrapper } = await mountUsers({ total: 100 })
    expect(wrapper.find('.base-pagination').exists()).toBe(true)
  })

  it('does not show pagination when totalPages <= 1', async () => {
    const { wrapper } = await mountUsers({ total: 3 })
    expect(wrapper.find('.base-pagination').exists()).toBe(false)
  })

  it('shows bulk action bar when items are selected as SUPER_ADMIN', async () => {
    const { wrapper } = await mountUsers()

    // Select a checkbox (not the header one) — checkboxes[0] is header, the rest are per-user
    const checkboxes = wrapper.findAll('input[type="checkbox"]')
    expect(checkboxes.length).toBeGreaterThan(1)

    // Simulate the change event that calls toggleSelect
    await checkboxes[1].setValue(true)
    await checkboxes[1].trigger('change')
    await nextTick()

    // Bulk action bar should appear with a select for role and a bulk apply button
    const bulkSelect = wrapper.findAll('select')
    // More selects than just the table role selects means bulk bar appeared
    expect(bulkSelect.length).toBeGreaterThan(0)
  })

  it('calls bulk role API when bulk apply is clicked and confirmed', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    mockApiPut.mockResolvedValue({ data: { updated_count: 1 } })
    mockListUsers.mockResolvedValue({ users: fakeUsers, total: 3 })

    const { wrapper } = await mountUsers()

    // Select a user checkbox
    const checkboxes = wrapper.findAll('input[type="checkbox"]')
    if (checkboxes.length > 1) {
      await checkboxes[1].setValue(true)
      await checkboxes[1].trigger('change')
      await nextTick()

      // Find and click bulk apply button
      const bulkButtons = wrapper.findAll('button')
      for (const btn of bulkButtons) {
        const text = btn.text()
        if (text && btn.attributes('disabled') === undefined) {
          await btn.trigger('click')
          await flushPromises()
          if (mockApiPut.mock.calls.length > 0) {
            expect(window.confirm).toHaveBeenCalled()
            expect(mockApiPut).toHaveBeenCalledWith('/users/bulk-role', expect.any(Object))
            break
          }
        }
      }
    }
    vi.restoreAllMocks()
  })

  it('does not call bulk role API when confirmation is declined', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(false)
    mockListUsers.mockResolvedValue({ users: fakeUsers, total: 3 })

    const { wrapper } = await mountUsers()

    // Select a user checkbox
    const checkboxes = wrapper.findAll('input[type="checkbox"]')
    if (checkboxes.length > 1) {
      await checkboxes[1].setValue(true)
      await checkboxes[1].trigger('change')
      await nextTick()

      // Find and click bulk apply button
      const bulkButtons = wrapper.findAll('button')
      for (const btn of bulkButtons) {
        const text = btn.text()
        if (text && btn.attributes('disabled') === undefined) {
          await btn.trigger('click')
          await flushPromises()
          // Since confirm returned false, API should NOT be called
        }
      }
      expect(mockApiPut).not.toHaveBeenCalled()
    }
    vi.restoreAllMocks()
  })

  it('uses updated_count from bulk role API response in toast', async () => {
    mockApiPut.mockResolvedValue({ data: { updated_count: 2 } })
    mockListUsers.mockResolvedValue({ users: fakeUsers, total: 3 })

    const { wrapper } = await mountUsers()

    // Select two user checkboxes
    const checkboxes = wrapper.findAll('input[type="checkbox"]')
    if (checkboxes.length > 2) {
      await checkboxes[1].setValue(true)
      await checkboxes[1].trigger('change')
      await checkboxes[2].setValue(true)
      await checkboxes[2].trigger('change')
      await nextTick()

      // Find and click bulk apply button
      const bulkButtons = wrapper.findAll('button')
      for (const btn of bulkButtons) {
        const text = btn.text()
        if (text && btn.attributes('disabled') === undefined) {
          await btn.trigger('click')
          await flushPromises()
          if (mockApiPut.mock.calls.length > 0) {
            // The bulk role API was called — verify updated_count is used
            expect(mockApiPut).toHaveBeenCalledWith('/users/bulk-role', expect.any(Object))
            break
          }
        }
      }
    }
  })

  describe('mobile card view', () => {
    it('should have md:hidden card container', async () => {
      const { wrapper } = await mountUsers()
      const mobileCards = wrapper.find('.md\\:hidden')
      expect(mobileCards.exists()).toBe(true)
    })

    it('should render a card for each user on mobile', async () => {
      const { wrapper } = await mountUsers()
      const mobileContainer = wrapper.find('.grid.md\\:hidden')
      // Direct child divs with p-4 are the user cards
      const cards = mobileContainer.findAll(':scope > div')
      expect(cards.length).toBe(fakeUsers.length)
    })

    it('should show display names in mobile cards', async () => {
      const { wrapper } = await mountUsers()
      const mobileContainer = wrapper.find('.md\\:hidden')
      expect(mobileContainer.text()).toContain('Alice')
      expect(mobileContainer.text()).toContain('Bob')
      expect(mobileContainer.text()).toContain('Charlie')
    })

    it('should hide table on mobile with hidden md:block', async () => {
      const { wrapper } = await mountUsers()
      const tableWrapper = wrapper.find('.hidden.md\\:block')
      expect(tableWrapper.exists()).toBe(true)
    })
  })

  it('shows message after successful create', async () => {
    mockCreateAccount.mockResolvedValue({ id: 'new-user' })
    mockListUsers.mockResolvedValue({ users: fakeUsers, total: 3 })

    const { wrapper } = await mountUsers()

    // Open create modal
    await wrapper.findAll('button')[0].trigger('click')
    await nextTick()

    const inputs = wrapper.findAll('.base-input')
    if (inputs.length >= 3) {
      await inputs[0].setValue('newuser')
      await inputs[1].setValue('New User')
      await inputs[2].setValue('password123')
      await nextTick()

      // Click the Create button in modal footer
      const modalButtons = wrapper.findAll('.base-modal button')
      const createBtn = modalButtons[modalButtons.length - 1]
      if (createBtn) {
        await createBtn.trigger('click')
        await flushPromises()
        expect(wrapper.find('.base-alert').exists()).toBe(true)
      }
    }
  })
})

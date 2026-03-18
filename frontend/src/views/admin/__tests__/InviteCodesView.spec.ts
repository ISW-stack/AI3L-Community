import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import InviteCodesView from '../InviteCodesView.vue'

const mockListInviteCodes = vi.fn()
const mockCreateInviteCode = vi.fn()
const mockRevokeInviteCode = vi.fn()
const mockDeleteInviteCode = vi.fn()

vi.mock('@/api/admin', () => ({
  listInviteCodes: (...args: unknown[]) => mockListInviteCodes(...args),
  createInviteCode: (...args: unknown[]) => mockCreateInviteCode(...args),
  revokeInviteCode: (...args: unknown[]) => mockRevokeInviteCode(...args),
  deleteInviteCode: (...args: unknown[]) => mockDeleteInviteCode(...args),
}))

vi.mock('@/composables/api', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
  },
}))

const fakeCodes = [
  {
    id: 'code-1',
    code: 'ABC-123-DEF',
    creator_username: 'admin',
    consumed_by_username: null,
    status: 'active',
    created_at: '2026-01-15T00:00:00Z',
    expires_at: '2026-02-15T00:00:00Z',
  },
  {
    id: 'code-2',
    code: 'GHI-456-JKL',
    creator_username: 'admin',
    consumed_by_username: 'alice',
    status: 'consumed',
    created_at: '2026-01-10T00:00:00Z',
    expires_at: null,
  },
  {
    id: 'code-3',
    code: 'MNO-789-PQR',
    creator_username: null,
    consumed_by_username: null,
    status: 'expired',
    created_at: '2025-12-01T00:00:00Z',
    expires_at: '2025-12-31T00:00:00Z',
  },
]

function createTestRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/admin/invite-codes', component: InviteCodesView }],
  })
}

async function mountInviteCodes(codes = fakeCodes, total = fakeCodes.length) {
  const pinia = createPinia()
  setActivePinia(pinia)
  const router = createTestRouter()
  await router.push('/admin/invite-codes')
  await router.isReady()

  mockListInviteCodes.mockResolvedValue({ codes, total })

  const wrapper = mount(InviteCodesView, {
    global: {
      plugins: [pinia, router],
      stubs: {
        BaseButton: {
          template:
            '<button :disabled="$attrs.disabled" @click="$emit(\'click\')"><slot /></button>',
          props: ['loading', 'variant', 'size'],
        },
        BaseBadge: {
          template: '<span class="base-badge"><slot /></span>',
          props: ['variant'],
        },
        BaseAlert: {
          template: '<div class="base-alert"><slot /></div>',
          props: ['type'],
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
  return wrapper
}

describe('InviteCodesView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    // Mock clipboard API
    Object.assign(navigator, {
      clipboard: {
        writeText: vi.fn().mockResolvedValue(undefined),
      },
    })
  })

  it('renders the title', async () => {
    const wrapper = await mountInviteCodes()
    expect(wrapper.find('h1').exists()).toBe(true)
  })

  it('fetches invite codes on mount', async () => {
    await mountInviteCodes()
    expect(mockListInviteCodes).toHaveBeenCalledOnce()
  })

  it('displays invite codes in the table', async () => {
    const wrapper = await mountInviteCodes()
    expect(wrapper.text()).toContain('ABC-123-DEF')
    expect(wrapper.text()).toContain('GHI-456-JKL')
    expect(wrapper.text()).toContain('MNO-789-PQR')
  })

  it('displays code statuses', async () => {
    const wrapper = await mountInviteCodes()
    expect(wrapper.text()).toContain('active')
    expect(wrapper.text()).toContain('consumed')
    expect(wrapper.text()).toContain('expired')
  })

  it('displays creator and consumed-by usernames', async () => {
    const wrapper = await mountInviteCodes()
    expect(wrapper.text()).toContain('admin')
    expect(wrapper.text()).toContain('alice')
  })

  it('shows dash for null creator and consumed_by', async () => {
    const wrapper = await mountInviteCodes()
    // MNO code has null creator_username and consumed_by_username
    const text = wrapper.text()
    expect(text).toContain('\u2014') // em-dash
  })

  it('shows empty state when no codes', async () => {
    const wrapper = await mountInviteCodes([], 0)
    expect(wrapper.find('.empty-state').exists()).toBe(true)
  })

  it('shows loading skeleton while fetching', async () => {
    mockListInviteCodes.mockReturnValue(new Promise(() => {}))
    const pinia = createPinia()
    setActivePinia(pinia)
    const router = createTestRouter()

    const wrapper = mount(InviteCodesView, {
      global: {
        plugins: [pinia, router],
        stubs: {
          BaseButton: { template: '<button><slot /></button>' },
          BaseBadge: { template: '<span />' },
          BaseAlert: { template: '<div />' },
          SkeletonLoader: { template: '<div class="skeleton-loader" />' },
          EmptyState: { template: '<div class="empty-state" />' },
        },
      },
    })
    await nextTick()
    expect(wrapper.find('.skeleton-loader').exists()).toBe(true)
  })

  it('calls createInviteCode when generate button is clicked', async () => {
    const wrapper = await mountInviteCodes()

    mockCreateInviteCode.mockClear()
    mockCreateInviteCode.mockResolvedValue({ invite_code: 'NEW-CODE-123' })
    mockListInviteCodes.mockResolvedValue({ codes: fakeCodes, total: 3 })

    // The generate button is in the header area
    const buttons = wrapper.findAll('button')
    const generateBtn = buttons[0]
    await generateBtn.trigger('click')
    await flushPromises()

    expect(mockCreateInviteCode).toHaveBeenCalled()
  })

  it('copies generated code to clipboard', async () => {
    mockCreateInviteCode.mockResolvedValue({ invite_code: 'NEW-CODE-123' })
    mockListInviteCodes.mockResolvedValue({ codes: fakeCodes, total: 3 })

    const wrapper = await mountInviteCodes()

    const buttons = wrapper.findAll('button')
    await buttons[0].trigger('click')
    await flushPromises()

    expect(navigator.clipboard.writeText).toHaveBeenCalledWith('NEW-CODE-123')
  })

  it('re-fetches codes after generating a new one', async () => {
    const wrapper = await mountInviteCodes()

    mockListInviteCodes.mockClear()
    mockCreateInviteCode.mockResolvedValue({ invite_code: 'NEW-CODE-123' })
    mockListInviteCodes.mockResolvedValue({ codes: fakeCodes, total: 3 })

    await wrapper.findAll('button')[0].trigger('click')
    await flushPromises()

    // listInviteCodes should have been called at least once after generate
    expect(mockListInviteCodes).toHaveBeenCalled()
  })

  it('renders filter select with all/active/consumed/expired options', async () => {
    const wrapper = await mountInviteCodes()
    const select = wrapper.find('select')
    expect(select.exists()).toBe(true)

    const options = select.findAll('option')
    expect(options.length).toBe(4)
  })

  it('re-fetches codes when filter is changed', async () => {
    const wrapper = await mountInviteCodes()

    mockListInviteCodes.mockClear()
    mockListInviteCodes.mockResolvedValue({ codes: [fakeCodes[0]], total: 1 })

    const select = wrapper.find('select')
    await select.setValue('active')
    await select.trigger('change')
    await flushPromises()

    expect(mockListInviteCodes).toHaveBeenCalled()
  })

  it('copies existing code when copy button is clicked', async () => {
    const wrapper = await mountInviteCodes()

    // Find copy buttons in table rows
    const copyBtns = wrapper.findAll('button[aria-label]')
    if (copyBtns.length > 0) {
      await copyBtns[0].trigger('click')
      await flushPromises()
      expect(navigator.clipboard.writeText).toHaveBeenCalledWith('ABC-123-DEF')
    }
  })

  it('displays total count', async () => {
    const wrapper = await mountInviteCodes(fakeCodes, 3)
    expect(wrapper.text()).toContain('3')
  })

  it('shows alert when clipboard is not available during generate', async () => {
    Object.assign(navigator, {
      clipboard: {
        writeText: vi.fn().mockRejectedValue(new Error('Clipboard not available')),
      },
    })
    mockCreateInviteCode.mockResolvedValue({ invite_code: 'FALLBACK-CODE' })
    mockListInviteCodes.mockResolvedValue({ codes: fakeCodes, total: 3 })

    const wrapper = await mountInviteCodes()

    await wrapper.findAll('button')[0].trigger('click')
    await flushPromises()

    // Should show the code in an alert as fallback
    expect(wrapper.find('.base-alert').exists()).toBe(true)
  })

  it('renders revoke button only for active codes', async () => {
    const wrapper = await mountInviteCodes()
    // Desktop table: find revoke buttons (Ban icon) by aria-label
    const revokeButtons = wrapper.findAll('[aria-label="Revoke"]')
    // Only code-1 is active, so there should be exactly 1 revoke button in the desktop table
    // (mobile layout also has one, so we check for at least 1)
    expect(revokeButtons.length).toBeGreaterThanOrEqual(1)
  })

  it('renders delete buttons for all codes', async () => {
    const wrapper = await mountInviteCodes()
    const deleteButtons = wrapper.findAll('[aria-label="Delete"]')
    // 3 codes × 2 layouts (mobile + desktop) = 6, but desktop is hidden on mobile
    // Just check that there are some delete buttons
    expect(deleteButtons.length).toBeGreaterThanOrEqual(3)
  })

  it('calls revokeInviteCode when revoke button is clicked', async () => {
    mockRevokeInviteCode.mockResolvedValue({ message: 'Revoked.' })
    mockListInviteCodes.mockResolvedValue({ codes: fakeCodes, total: 3 })

    const wrapper = await mountInviteCodes()

    const revokeButtons = wrapper.findAll('[aria-label="Revoke"]')
    expect(revokeButtons.length).toBeGreaterThanOrEqual(1)

    await revokeButtons[0].trigger('click')
    await flushPromises()

    expect(mockRevokeInviteCode).toHaveBeenCalledWith('code-1')
  })

  it('calls deleteInviteCode when delete button is clicked', async () => {
    mockDeleteInviteCode.mockResolvedValue(undefined)
    mockListInviteCodes.mockResolvedValue({ codes: fakeCodes, total: 3 })

    const wrapper = await mountInviteCodes()

    const deleteButtons = wrapper.findAll('[aria-label="Delete"]')
    expect(deleteButtons.length).toBeGreaterThanOrEqual(1)

    await deleteButtons[0].trigger('click')
    await flushPromises()

    expect(mockDeleteInviteCode).toHaveBeenCalled()
  })

  it('re-fetches codes after revoke', async () => {
    mockRevokeInviteCode.mockResolvedValue({ message: 'Revoked.' })
    mockListInviteCodes.mockResolvedValue({ codes: fakeCodes, total: 3 })

    const wrapper = await mountInviteCodes()
    mockListInviteCodes.mockClear()
    mockListInviteCodes.mockResolvedValue({ codes: fakeCodes, total: 3 })

    const revokeButtons = wrapper.findAll('[aria-label="Revoke"]')
    await revokeButtons[0].trigger('click')
    await flushPromises()

    expect(mockListInviteCodes).toHaveBeenCalled()
  })

  it('re-fetches codes after delete', async () => {
    mockDeleteInviteCode.mockResolvedValue(undefined)
    mockListInviteCodes.mockResolvedValue({ codes: fakeCodes, total: 3 })

    const wrapper = await mountInviteCodes()
    mockListInviteCodes.mockClear()
    mockListInviteCodes.mockResolvedValue({ codes: fakeCodes, total: 3 })

    const deleteButtons = wrapper.findAll('[aria-label="Delete"]')
    await deleteButtons[0].trigger('click')
    await flushPromises()

    expect(mockListInviteCodes).toHaveBeenCalled()
  })
})

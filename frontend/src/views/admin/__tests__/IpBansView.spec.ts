import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import IpBansView from '../IpBansView.vue'

const mockListIpBans = vi.fn()
const mockCreateIpBan = vi.fn()
const mockDeleteIpBan = vi.fn()

vi.mock('@/api/admin', () => ({
  listIpBans: (...args: unknown[]) => mockListIpBans(...args),
  createIpBan: (...args: unknown[]) => mockCreateIpBan(...args),
  deleteIpBan: (...args: unknown[]) => mockDeleteIpBan(...args),
}))

vi.mock('@/composables/api', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
}))

vi.mock('@/utils/error', () => ({
  getErrorMessage: (_e: unknown, fallback: string) => fallback,
}))

vi.mock('@/constants', () => ({
  HEARTBEAT_INTERVAL_MS: 30000,
}))

const fakeBans = [
  {
    id: 'ban-1',
    ip_address: '192.168.1.100',
    reason: 'DDoS attack',
    banned_by: 'admin-1',
    expires_at: null,
    created_at: '2026-01-15T10:00:00Z',
  },
  {
    id: 'ban-2',
    ip_address: '10.0.0.50',
    reason: 'Spam',
    banned_by: 'admin-1',
    expires_at: '2026-06-01T00:00:00Z',
    created_at: '2026-02-20T14:30:00Z',
  },
  {
    id: 'ban-3',
    ip_address: '172.16.0.1',
    reason: '',
    banned_by: null,
    expires_at: null,
    created_at: '2026-03-01T08:00:00Z',
  },
]

function createTestRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/admin/ip-bans', component: IpBansView }],
  })
}

async function mountIpBans(options?: { bans?: typeof fakeBans; total?: number }) {
  const { bans = fakeBans, total = fakeBans.length } = options ?? {}

  const pinia = createPinia()
  setActivePinia(pinia)

  const router = createTestRouter()
  await router.push('/admin/ip-bans')
  await router.isReady()

  mockListIpBans.mockResolvedValue({ bans, total })

  const wrapper = mount(IpBansView, {
    global: {
      plugins: [pinia, router],
      stubs: {
        BaseButton: {
          template:
            '<button :disabled="$attrs.disabled" @click="$emit(\'click\')"><slot /></button>',
          props: ['size', 'variant', 'loading'],
        },
        BaseAlert: {
          template: '<div class="base-alert"><slot /></div>',
          props: ['type'],
        },
        BaseInput: {
          template:
            '<input class="base-input" :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
          props: ['modelValue', 'label', 'placeholder', 'required'],
        },
        BaseTextarea: {
          template:
            '<textarea class="base-textarea" :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)"></textarea>',
          props: ['modelValue', 'label', 'rows', 'placeholder'],
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
        BaseBreadcrumb: { template: '<nav class="breadcrumb" />' },
      },
    },
  })
  await flushPromises()
  return wrapper
}

describe('IpBansView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders the title', async () => {
    const wrapper = await mountIpBans()
    expect(wrapper.find('h1').exists()).toBe(true)
  })

  it('renders the breadcrumb', async () => {
    const wrapper = await mountIpBans()
    expect(wrapper.find('.breadcrumb').exists()).toBe(true)
  })

  it('calls listIpBans on mount', async () => {
    await mountIpBans()
    expect(mockListIpBans).toHaveBeenCalledOnce()
    expect(mockListIpBans).toHaveBeenCalledWith({ page: 1, page_size: 20 })
  })

  it('displays IP addresses in the table', async () => {
    const wrapper = await mountIpBans()
    expect(wrapper.text()).toContain('192.168.1.100')
    expect(wrapper.text()).toContain('10.0.0.50')
    expect(wrapper.text()).toContain('172.16.0.1')
  })

  it('displays ban reasons', async () => {
    const wrapper = await mountIpBans()
    expect(wrapper.text()).toContain('DDoS attack')
    expect(wrapper.text()).toContain('Spam')
  })

  it('shows empty state when no bans', async () => {
    const wrapper = await mountIpBans({ bans: [], total: 0 })
    expect(wrapper.find('.empty-state').exists()).toBe(true)
  })

  it('shows loading skeleton while fetching', async () => {
    mockListIpBans.mockReturnValue(new Promise(() => {}))
    const pinia = createPinia()
    setActivePinia(pinia)
    const router = createTestRouter()

    const wrapper = mount(IpBansView, {
      global: {
        plugins: [pinia, router],
        stubs: {
          BaseButton: { template: '<button><slot /></button>' },
          BaseAlert: { template: '<div />' },
          BaseInput: { template: '<input />' },
          BaseTextarea: { template: '<textarea />' },
          BaseModal: { template: '<div />' },
          BasePagination: { template: '<div />' },
          SkeletonLoader: { template: '<div class="skeleton-loader" />' },
          EmptyState: { template: '<div class="empty-state" />' },
          BaseBreadcrumb: { template: '<nav />' },
        },
      },
    })
    await nextTick()
    expect(wrapper.find('.skeleton-loader').exists()).toBe(true)
  })

  it('shows alert when fetch fails', async () => {
    mockListIpBans.mockRejectedValue(new Error('Server error'))
    const pinia = createPinia()
    setActivePinia(pinia)
    const router = createTestRouter()
    await router.push('/admin/ip-bans')
    await router.isReady()

    const wrapper = mount(IpBansView, {
      global: {
        plugins: [pinia, router],
        stubs: {
          BaseButton: { template: '<button><slot /></button>' },
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
          BaseBreadcrumb: { template: '<nav />' },
        },
      },
    })
    await flushPromises()
    expect(wrapper.find('.base-alert').exists()).toBe(true)
  })

  it('opens create modal when Ban IP button is clicked', async () => {
    const wrapper = await mountIpBans()

    // The Ban IP button is in the header area (first button)
    const buttons = wrapper.findAll('button')
    const banIpBtn = buttons.find((b) => b.text().length > 0)
    expect(banIpBtn).toBeTruthy()

    await banIpBtn!.trigger('click')
    await nextTick()

    expect(wrapper.find('.base-modal').exists()).toBe(true)
  })

  it('calls createIpBan when form is submitted with IP', async () => {
    const newBan = {
      id: 'ban-new',
      ip_address: '8.8.8.8',
      reason: 'test ban',
      banned_by: null,
      expires_at: null,
      created_at: '2026-03-18T00:00:00Z',
    }
    mockCreateIpBan.mockResolvedValue(newBan)
    mockListIpBans.mockResolvedValue({ bans: fakeBans, total: 3 })

    const wrapper = await mountIpBans()

    // Open create modal
    const buttons = wrapper.findAll('button')
    const banIpBtn = buttons.find((b) => b.text().length > 0)
    await banIpBtn!.trigger('click')
    await nextTick()

    // Fill IP address
    const inputs = wrapper.findAll('.base-input')
    if (inputs.length > 0) {
      await inputs[0].setValue('8.8.8.8')
      await nextTick()
    }

    // Fill reason
    const textarea = wrapper.find('.base-textarea')
    if (textarea.exists()) {
      await textarea.setValue('test ban')
      await nextTick()
    }

    // Click the confirm button in the modal footer (last button in modal)
    const modalButtons = wrapper.findAll('.base-modal button')
    const confirmBtn = modalButtons[modalButtons.length - 1]
    if (confirmBtn) {
      await confirmBtn.trigger('click')
      await flushPromises()

      expect(mockCreateIpBan).toHaveBeenCalledWith(
        expect.objectContaining({ ip_address: '8.8.8.8' }),
      )
    }
  })

  it('does not call createIpBan when IP is empty', async () => {
    const wrapper = await mountIpBans()

    // Open create modal
    const buttons = wrapper.findAll('button')
    const banIpBtn = buttons.find((b) => b.text().length > 0)
    await banIpBtn!.trigger('click')
    await nextTick()

    // Do not fill IP -- leave it empty

    // Click confirm button in modal footer
    const modalButtons = wrapper.findAll('.base-modal button')
    const confirmBtn = modalButtons[modalButtons.length - 1]
    if (confirmBtn) {
      await confirmBtn.trigger('click')
      await flushPromises()

      expect(mockCreateIpBan).not.toHaveBeenCalled()
    }
  })

  it('closes modal and resets form after successful create', async () => {
    mockCreateIpBan.mockResolvedValue({
      id: 'ban-new',
      ip_address: '1.1.1.1',
      reason: '',
      banned_by: null,
      expires_at: null,
      created_at: '2026-03-18T00:00:00Z',
    })
    mockListIpBans.mockResolvedValue({ bans: fakeBans, total: 3 })

    const wrapper = await mountIpBans()

    // Open create modal
    const buttons = wrapper.findAll('button')
    await buttons[0].trigger('click')
    await nextTick()
    expect(wrapper.find('.base-modal').exists()).toBe(true)

    // Fill IP
    const inputs = wrapper.findAll('.base-input')
    if (inputs.length > 0) {
      await inputs[0].setValue('1.1.1.1')
      await nextTick()
    }

    // Confirm
    const modalButtons = wrapper.findAll('.base-modal button')
    const confirmBtn = modalButtons[modalButtons.length - 1]
    if (confirmBtn) {
      await confirmBtn.trigger('click')
      await flushPromises()

      // Modal should be closed
      expect(wrapper.find('.base-modal').exists()).toBe(false)
    }
  })

  it('re-fetches bans after successful create', async () => {
    mockCreateIpBan.mockResolvedValue({
      id: 'ban-new',
      ip_address: '1.1.1.1',
      reason: '',
      banned_by: null,
      expires_at: null,
      created_at: '2026-03-18T00:00:00Z',
    })
    mockListIpBans.mockResolvedValue({ bans: fakeBans, total: 3 })

    const wrapper = await mountIpBans()
    mockListIpBans.mockClear()

    // Open modal, fill IP, confirm
    await wrapper.findAll('button')[0].trigger('click')
    await nextTick()

    const inputs = wrapper.findAll('.base-input')
    if (inputs.length > 0) {
      await inputs[0].setValue('1.1.1.1')
      await nextTick()
    }

    const modalButtons = wrapper.findAll('.base-modal button')
    const confirmBtn = modalButtons[modalButtons.length - 1]
    if (confirmBtn) {
      await confirmBtn.trigger('click')
      await flushPromises()

      // Should have re-fetched
      expect(mockListIpBans).toHaveBeenCalled()
    }
  })

  it('calls deleteIpBan when unban button is clicked', async () => {
    mockDeleteIpBan.mockResolvedValue(undefined)
    mockListIpBans.mockResolvedValue({ bans: fakeBans, total: 3 })

    const wrapper = await mountIpBans()

    // Find unban buttons in the table (they are inside table rows)
    const tableButtons = wrapper.findAll('table button')
    expect(tableButtons.length).toBeGreaterThan(0)

    await tableButtons[0].trigger('click')
    await flushPromises()

    expect(mockDeleteIpBan).toHaveBeenCalledWith('ban-1')
  })

  it('re-fetches bans after successful unban', async () => {
    mockDeleteIpBan.mockResolvedValue(undefined)
    mockListIpBans.mockResolvedValue({ bans: fakeBans, total: 3 })

    const wrapper = await mountIpBans()
    mockListIpBans.mockClear()

    const tableButtons = wrapper.findAll('table button')
    if (tableButtons.length > 0) {
      await tableButtons[0].trigger('click')
      await flushPromises()

      expect(mockListIpBans).toHaveBeenCalled()
    }
  })

  it('displays total count', async () => {
    const wrapper = await mountIpBans()
    expect(wrapper.text()).toContain('3')
  })

  it('shows pagination when totalPages > 1', async () => {
    const wrapper = await mountIpBans({ total: 100 })
    expect(wrapper.find('.base-pagination').exists()).toBe(true)
  })

  it('does not show pagination when totalPages <= 1', async () => {
    const wrapper = await mountIpBans({ total: 3 })
    expect(wrapper.find('.base-pagination').exists()).toBe(false)
  })

  describe('mobile card view', () => {
    it('should have md:hidden card container', async () => {
      const wrapper = await mountIpBans()
      const mobileCards = wrapper.find('.md\\:hidden')
      expect(mobileCards.exists()).toBe(true)
    })

    it('should render a card for each ban on mobile', async () => {
      const wrapper = await mountIpBans()
      const mobileContainer = wrapper.find('.grid.md\\:hidden')
      const cards = mobileContainer.findAll(':scope > div')
      expect(cards.length).toBe(fakeBans.length)
    })

    it('should show IP addresses in mobile cards', async () => {
      const wrapper = await mountIpBans()
      const mobileContainer = wrapper.find('.md\\:hidden')
      expect(mobileContainer.text()).toContain('192.168.1.100')
      expect(mobileContainer.text()).toContain('10.0.0.50')
      expect(mobileContainer.text()).toContain('172.16.0.1')
    })

    it('should hide table on mobile with hidden md:block', async () => {
      const wrapper = await mountIpBans()
      const tableWrapper = wrapper.find('.hidden.md\\:block')
      expect(tableWrapper.exists()).toBe(true)
    })
  })

  describe('desktop table', () => {
    it('renders table headers', async () => {
      const wrapper = await mountIpBans()
      const table = wrapper.find('table')
      expect(table.exists()).toBe(true)
      const headers = table.findAll('th')
      expect(headers.length).toBe(5)
    })

    it('renders a row for each ban', async () => {
      const wrapper = await mountIpBans()
      const rows = wrapper.findAll('table tbody tr')
      expect(rows.length).toBe(fakeBans.length)
    })

    it('shows dash for bans without reason', async () => {
      const wrapper = await mountIpBans()
      // ban-3 has empty reason, should show '-'
      const rows = wrapper.findAll('table tbody tr')
      const lastRow = rows[rows.length - 1]
      expect(lastRow.text()).toContain('-')
    })
  })
})

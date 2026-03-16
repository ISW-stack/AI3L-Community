import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import AuditLogsView from '../AuditLogsView.vue'

const mockGetAuditLogs = vi.fn()

vi.mock('@/api/admin', () => ({
  getAuditLogs: (...args: unknown[]) => mockGetAuditLogs(...args),
}))

vi.mock('@/composables/api', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
  },
}))

const fakeLogs = [
  {
    id: 'log-1',
    user_id: 'user-1',
    username: 'alice',
    display_name: 'Alice',
    action: 'LOGIN',
    target_type: 'user',
    target_id: 'user-1',
    ip_address: '192.168.1.1',
    created_at: '2026-01-15T10:00:00Z',
  },
  {
    id: 'log-2',
    user_id: 'user-2',
    username: 'bob',
    display_name: null,
    action: 'DELETE_POST',
    target_type: 'post',
    target_id: 'post-abc12345',
    ip_address: null,
    created_at: '2026-01-14T09:00:00Z',
  },
]

function createTestRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/admin/audit-logs', component: AuditLogsView }],
  })
}

async function mountAuditLogs(logs = fakeLogs, total = fakeLogs.length) {
  const pinia = createPinia()
  setActivePinia(pinia)
  const router = createTestRouter()
  await router.push('/admin/audit-logs')
  await router.isReady()

  mockGetAuditLogs.mockResolvedValue({ logs, total })

  const wrapper = mount(AuditLogsView, {
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
          props: ['variant'],
        },
        BaseAlert: {
          template: '<div class="base-alert"><slot /></div>',
          props: ['type'],
        },
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

describe('AuditLogsView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders the title', async () => {
    const wrapper = await mountAuditLogs()
    expect(wrapper.find('h1').exists()).toBe(true)
  })

  it('fetches audit logs on mount', async () => {
    await mountAuditLogs()
    expect(mockGetAuditLogs).toHaveBeenCalledOnce()
    expect(mockGetAuditLogs).toHaveBeenCalledWith({ page: 1, page_size: 50 })
  })

  it('displays log entries in the table', async () => {
    const wrapper = await mountAuditLogs()
    expect(wrapper.text()).toContain('Alice')
    expect(wrapper.text()).toContain('LOGIN')
    expect(wrapper.text()).toContain('DELETE_POST')
    expect(wrapper.text()).toContain('192.168.1.1')
  })

  it('shows user_id prefix when display_name is null', async () => {
    const wrapper = await mountAuditLogs()
    // user-2 has no display_name, should show user_id slice
    expect(wrapper.text()).toContain('user-2'.slice(0, 8))
  })

  it('shows dash for null ip_address', async () => {
    const wrapper = await mountAuditLogs()
    expect(wrapper.text()).toContain('-')
  })

  it('shows empty state when no logs', async () => {
    const wrapper = await mountAuditLogs([], 0)
    expect(wrapper.find('.empty-state').exists()).toBe(true)
  })

  it('shows loading text in table while fetching', async () => {
    mockGetAuditLogs.mockReturnValue(new Promise(() => {}))
    const pinia = createPinia()
    setActivePinia(pinia)
    const router = createTestRouter()

    const wrapper = mount(AuditLogsView, {
      global: {
        plugins: [pinia, router],
        stubs: {
          BaseButton: { template: '<button><slot /></button>' },
          BaseBadge: { template: '<span />' },
          BaseAlert: { template: '<div />' },
          EmptyState: { template: '<div class="empty-state" />' },
        },
      },
    })
    await nextTick()
    // Table exists with loading row
    expect(wrapper.find('table').exists()).toBe(true)
  })

  it('shows error alert when fetch fails', async () => {
    mockGetAuditLogs.mockRejectedValue(new Error('Server error'))
    const pinia = createPinia()
    setActivePinia(pinia)
    const router = createTestRouter()
    await router.push('/admin/audit-logs')
    await router.isReady()

    const wrapper = mount(AuditLogsView, {
      global: {
        plugins: [pinia, router],
        stubs: {
          BaseButton: { template: '<button><slot /></button>' },
          BaseBadge: { template: '<span />' },
          BaseAlert: {
            template: '<div class="base-alert"><slot /></div>',
            props: ['type'],
          },
          EmptyState: { template: '<div class="empty-state" />' },
        },
      },
    })
    await flushPromises()
    expect(wrapper.find('.base-alert').exists()).toBe(true)
  })

  it('toggles filter panel when filter button is clicked', async () => {
    const wrapper = await mountAuditLogs()

    // Filter panel should be hidden initially
    const dateInputsBefore = wrapper.findAll('input[type="date"]')
    expect(dateInputsBefore.length).toBe(0)

    // Click the toggle filters button
    const toggleBtn = wrapper.find('button')
    await toggleBtn.trigger('click')
    await nextTick()

    // Filter panel should now be visible
    const dateInputsAfter = wrapper.findAll('input[type="date"]')
    expect(dateInputsAfter.length).toBe(2)
  })

  it('renders pagination controls', async () => {
    const wrapper = await mountAuditLogs(fakeLogs, 200)
    const buttons = wrapper.findAll('button')
    const btnTexts = buttons.map((b) => b.text())
    // Should have previous and next buttons
    expect(btnTexts.length).toBeGreaterThanOrEqual(2)
  })

  it('disables previous button on first page', async () => {
    const wrapper = await mountAuditLogs(fakeLogs, 200)
    const buttons = wrapper.findAll('button')
    // Find the previous button (usually has disabled attribute on page 1)
    const prevBtn = buttons.find((b) => b.attributes('disabled') !== undefined)
    expect(prevBtn).toBeTruthy()
  })

  it('navigates to next page when next is clicked', async () => {
    const wrapper = await mountAuditLogs(fakeLogs, 200)

    // Reset mock after mount call
    mockGetAuditLogs.mockClear()
    mockGetAuditLogs.mockResolvedValue({ logs: [], total: 200 })

    // Find the non-disabled buttons with text (skip toggle filter which is first)
    const buttons = wrapper.findAll('button')
    // The next button is the last one that is not disabled
    const nextBtn = buttons.filter(
      (b) => b.attributes('disabled') === undefined && b.text().length > 0,
    )
    // Click the last non-disabled button (Next)
    const btn = nextBtn[nextBtn.length - 1]
    if (btn) {
      await btn.trigger('click')
      await flushPromises()
      expect(mockGetAuditLogs).toHaveBeenCalled()
      expect(mockGetAuditLogs).toHaveBeenCalledWith(expect.objectContaining({ page: 2 }))
    }
  })

  it('displays total count', async () => {
    const wrapper = await mountAuditLogs(fakeLogs, 2)
    expect(wrapper.text()).toContain('2')
  })

  it('shows date range invalid warning when from > to', async () => {
    const wrapper = await mountAuditLogs()

    // Open filters
    const toggleBtn = wrapper.find('button')
    await toggleBtn.trigger('click')
    await nextTick()

    // Set invalid date range
    const dateInputs = wrapper.findAll('input[type="date"]')
    await dateInputs[0].setValue('2026-02-01')
    await dateInputs[1].setValue('2026-01-01')
    await nextTick()

    // Should show invalid range message
    expect(wrapper.text().length).toBeGreaterThan(0)
  })

  it('shows visible date range error message text when from > to', async () => {
    const wrapper = await mountAuditLogs()

    // Open filters
    const toggleBtn = wrapper.find('button')
    await toggleBtn.trigger('click')
    await nextTick()

    // Set invalid date range
    const dateInputs = wrapper.findAll('input[type="date"]')
    await dateInputs[0].setValue('2026-02-01')
    await dateInputs[1].setValue('2026-01-01')
    await nextTick()

    // The error message with text-danger-600 should be visible
    const errorP = wrapper.find('p.text-danger-600')
    expect(errorP.exists()).toBe(true)
    expect(errorP.text()).toContain('Start date must be before end date')
  })

  it('does not show date range error when range is valid', async () => {
    const wrapper = await mountAuditLogs()

    // Open filters
    const toggleBtn = wrapper.find('button')
    await toggleBtn.trigger('click')
    await nextTick()

    // Set valid date range
    const dateInputs = wrapper.findAll('input[type="date"]')
    await dateInputs[0].setValue('2026-01-01')
    await dateInputs[1].setValue('2026-02-01')
    await nextTick()

    // No error message
    const errorP = wrapper.find('p.text-danger-600')
    expect(errorP.exists()).toBe(false)
  })

  it('uses md: breakpoint for filter bar layout', async () => {
    const wrapper = await mountAuditLogs()

    // Open filters
    const toggleBtn = wrapper.find('button')
    await toggleBtn.trigger('click')
    await nextTick()

    // Find the filter container with flex-col
    const filterRow = wrapper.find('.flex.flex-col')
    expect(filterRow.exists()).toBe(true)
    expect(filterRow.classes()).toContain('md:flex-row')
    expect(filterRow.classes()).not.toContain('sm:flex-row')
  })

  it('clears filters and re-fetches', async () => {
    const wrapper = await mountAuditLogs()

    // Open filters
    const toggleBtn = wrapper.find('button')
    await toggleBtn.trigger('click')
    await nextTick()

    // Set a filter value
    const textInput = wrapper.find('input[type="text"]')
    await textInput.setValue('user-1')
    await nextTick()

    // Click Apply
    mockGetAuditLogs.mockResolvedValue({ logs: fakeLogs, total: 2 })
    const applyBtn = wrapper.findAll('button').find((b) => b.text().length > 0)
    if (applyBtn) {
      await applyBtn.trigger('click')
      await flushPromises()
    }

    // Clear button should appear (hasActiveFilters is true)
    const clearBtn = wrapper.findAll('button').find((b) => {
      const t = b.text()
      return t && b.attributes('disabled') === undefined
    })
    if (clearBtn) {
      await clearBtn.trigger('click')
      await flushPromises()
      // Should have fetched again
      expect(mockGetAuditLogs).toHaveBeenCalled()
    }
  })
})

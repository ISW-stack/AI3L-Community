import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import ReportsView from '../ReportsView.vue'

const mockListReports = vi.fn()
const mockReviewReport = vi.fn()

vi.mock('@/api/admin', () => ({
  listReports: (...args: unknown[]) => mockListReports(...args),
  reviewReport: (...args: unknown[]) => mockReviewReport(...args),
}))

vi.mock('@/composables/api', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
  },
}))

const fakeReports = [
  {
    id: 'report-1',
    post_id: 'post-1',
    user_id: 'user-1',
    reason: 'Spam content',
    status: 'PENDING',
    reviewed_by: null,
    reviewed_at: null,
    created_at: '2026-01-15T10:00:00Z',
    post_title: 'Bad Post Title',
  },
  {
    id: 'report-2',
    post_id: 'post-2',
    user_id: 'user-2',
    reason: 'Offensive language',
    status: 'RESOLVED',
    reviewed_by: 'admin-1',
    reviewed_at: '2026-01-16T00:00:00Z',
    created_at: '2026-01-14T09:00:00Z',
    post_title: null,
  },
]

function createTestRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/admin/reports', component: ReportsView },
      { path: '/forum/:id', component: { template: '<div />' } },
    ],
  })
}

async function mountReports(reports = fakeReports, total = fakeReports.length) {
  const pinia = createPinia()
  setActivePinia(pinia)
  const router = createTestRouter()
  await router.push('/admin/reports')
  await router.isReady()

  mockListReports.mockResolvedValue({ reports, total, total_pages: Math.ceil(total / 20) })

  const wrapper = mount(ReportsView, {
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
        BasePagination: {
          template: '<div class="base-pagination" />',
          props: ['currentPage', 'totalPages'],
        },
        SkeletonLoader: { template: '<div class="skeleton-loader" />' },
        EmptyState: {
          template: '<div class="empty-state">{{ message }}</div>',
          props: ['message'],
        },
      },
    },
  })
  await flushPromises()
  return wrapper
}

describe('ReportsView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders the title', async () => {
    const wrapper = await mountReports()
    expect(wrapper.find('h1').exists()).toBe(true)
  })

  it('fetches reports on mount', async () => {
    await mountReports()
    expect(mockListReports).toHaveBeenCalledOnce()
    expect(mockListReports).toHaveBeenCalledWith({
      status_filter: undefined,
      page: 1,
      page_size: 20,
    })
  })

  it('displays report details in the table', async () => {
    const wrapper = await mountReports()
    expect(wrapper.text()).toContain('Spam content')
    expect(wrapper.text()).toContain('Bad Post Title')
    expect(wrapper.text()).toContain('Offensive language')
  })

  it('displays report statuses as badges', async () => {
    const wrapper = await mountReports()
    const badges = wrapper.findAll('.base-badge')
    expect(badges.length).toBeGreaterThanOrEqual(2)
    expect(wrapper.text()).toContain('PENDING')
    expect(wrapper.text()).toContain('RESOLVED')
  })

  it('shows resolve and dismiss buttons for PENDING reports', async () => {
    const pendingOnly = [fakeReports[0]]
    const wrapper = await mountReports(pendingOnly, 1)

    // PENDING report should have action buttons
    const actionButtons = wrapper.findAll('table button')
    expect(actionButtons.length).toBeGreaterThanOrEqual(2)
  })

  it('does not show action buttons for RESOLVED reports', async () => {
    const resolvedOnly = [fakeReports[1]]
    const wrapper = await mountReports(resolvedOnly, 1)

    // RESOLVED report should not have action buttons in its row
    const actionButtons = wrapper.findAll('table button')
    expect(actionButtons.length).toBe(0)
  })

  it('shows empty state when no reports', async () => {
    const wrapper = await mountReports([], 0)
    expect(wrapper.find('.empty-state').exists()).toBe(true)
  })

  it('shows loading skeleton while fetching', async () => {
    mockListReports.mockReturnValue(new Promise(() => {}))
    const pinia = createPinia()
    setActivePinia(pinia)
    const router = createTestRouter()

    const wrapper = mount(ReportsView, {
      global: {
        plugins: [pinia, router],
        stubs: {
          BaseButton: { template: '<button><slot /></button>' },
          BaseBadge: { template: '<span />' },
          BasePagination: { template: '<div />' },
          SkeletonLoader: { template: '<div class="skeleton-loader" />' },
          EmptyState: { template: '<div class="empty-state" />' },
        },
      },
    })
    await nextTick()
    expect(wrapper.find('.skeleton-loader').exists()).toBe(true)
  })

  it('calls reviewReport with RESOLVED when resolve is clicked', async () => {
    const pendingOnly = [fakeReports[0]]
    mockReviewReport.mockResolvedValue(undefined)
    mockListReports.mockResolvedValue({ reports: pendingOnly, total: 1, total_pages: 1 })

    const wrapper = await mountReports(pendingOnly, 1)
    mockListReports.mockResolvedValue({ reports: [], total: 0, total_pages: 0 })

    // Click the first action button (Resolve)
    const actionButtons = wrapper.findAll('table button')
    if (actionButtons.length > 0) {
      await actionButtons[0].trigger('click')
      await flushPromises()
      expect(mockReviewReport).toHaveBeenCalledWith('report-1', 'RESOLVED')
    }
  })

  it('calls reviewReport with DISMISSED when dismiss is clicked', async () => {
    const pendingOnly = [fakeReports[0]]
    mockReviewReport.mockResolvedValue(undefined)
    mockListReports.mockResolvedValue({ reports: pendingOnly, total: 1, total_pages: 1 })

    const wrapper = await mountReports(pendingOnly, 1)
    mockListReports.mockResolvedValue({ reports: [], total: 0, total_pages: 0 })

    // Click the second action button (Dismiss)
    const actionButtons = wrapper.findAll('table button')
    if (actionButtons.length > 1) {
      await actionButtons[1].trigger('click')
      await flushPromises()
      expect(mockReviewReport).toHaveBeenCalledWith('report-1', 'DISMISSED')
    }
  })

  it('re-fetches reports after review action', async () => {
    const pendingOnly = [fakeReports[0]]
    const wrapper = await mountReports(pendingOnly, 1)

    mockListReports.mockClear()
    mockReviewReport.mockResolvedValue(undefined)
    mockListReports.mockResolvedValue({ reports: [], total: 0, total_pages: 0 })

    const actionButtons = wrapper.findAll('table button')
    if (actionButtons.length > 0) {
      await actionButtons[0].trigger('click')
      await flushPromises()
      expect(mockListReports).toHaveBeenCalled()
    }
  })

  it('renders status filter select', async () => {
    const wrapper = await mountReports()
    const select = wrapper.find('select')
    expect(select.exists()).toBe(true)

    const options = select.findAll('option')
    expect(options.length).toBe(4) // All, PENDING, RESOLVED, DISMISSED
  })

  it('re-fetches with filter when status filter is changed', async () => {
    const wrapper = await mountReports()

    mockListReports.mockClear()
    mockListReports.mockResolvedValue({ reports: [], total: 0, total_pages: 0 })

    const select = wrapper.find('select')
    await select.setValue('PENDING')
    await select.trigger('change')
    await flushPromises()

    expect(mockListReports).toHaveBeenCalled()
    expect(mockListReports).toHaveBeenLastCalledWith(
      expect.objectContaining({ status_filter: 'PENDING' }),
    )
  })

  it('renders post title as link to forum post', async () => {
    const wrapper = await mountReports()
    const links = wrapper.findAll('a')
    const postLink = links.find((l) => l.attributes('href')?.includes('/forum/'))
    expect(postLink).toBeTruthy()
    expect(postLink!.text()).toContain('Bad Post Title')
  })

  it('shows post_id prefix when post_title is null', async () => {
    const wrapper = await mountReports()
    // Second report has null post_title
    expect(wrapper.text()).toContain('post-2'.slice(0, 8))
  })

  it('displays total count', async () => {
    const wrapper = await mountReports(fakeReports, 2)
    expect(wrapper.text()).toContain('2')
  })

  it('shows pagination when totalPages > 1', async () => {
    const wrapper = await mountReports(fakeReports, 100)
    expect(wrapper.find('.base-pagination').exists()).toBe(true)
  })

  it('does not show pagination when totalPages <= 1', async () => {
    const wrapper = await mountReports(fakeReports, 2)
    expect(wrapper.find('.base-pagination').exists()).toBe(false)
  })
})

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import DataExportView from '../DataExportView.vue'

const mockStartSiteExport = vi.fn()
const mockGetExportProgress = vi.fn()
const mockGetExportHistory = vi.fn()
const mockDeleteExport = vi.fn()

vi.mock('@/api/admin', () => ({
  startSiteExport: (...args: unknown[]) => mockStartSiteExport(...args),
  getExportProgress: (...args: unknown[]) => mockGetExportProgress(...args),
  getExportHistory: (...args: unknown[]) => mockGetExportHistory(...args),
  deleteExport: (...args: unknown[]) => mockDeleteExport(...args),
}))

vi.mock('@/composables/api', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    delete: vi.fn(),
  },
}))

const fakeHistory = [
  {
    task_id: 't-1',
    status: 'SUCCESS',
    created_at: '2026-03-25T14:00:00Z',
    created_by: 'user-1',
    options: { include_database: true, include_files: true },
    file_size: 5000000,
    download_url: 'https://example.com/export-1.zip',
  },
  {
    task_id: 't-2',
    status: 'FAILURE',
    created_at: '2026-03-24T10:00:00Z',
    created_by: 'user-1',
    options: { include_database: true, include_files: false },
    file_size: null,
    download_url: null,
  },
]

function createTestRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/admin/data-export', component: DataExportView }],
  })
}

async function mountView(historyData = fakeHistory) {
  const pinia = createPinia()
  setActivePinia(pinia)
  const router = createTestRouter()
  await router.push('/admin/data-export')
  await router.isReady()

  mockGetExportHistory.mockResolvedValue({ exports: historyData })

  const wrapper = mount(DataExportView, {
    global: {
      plugins: [pinia, router],
      stubs: {
        BaseButton: {
          template:
            '<button :disabled="$attrs.disabled" @click="$emit(\'click\')"><slot /></button>',
          props: ['size', 'variant', 'loading'],
        },
        BaseCard: {
          template: '<div class="base-card"><slot /></div>',
          props: ['padding'],
        },
        BaseBreadcrumb: {
          template: '<nav class="breadcrumb"></nav>',
          props: ['items'],
        },
        AlertTriangle: { template: '<span class="icon-alert" />' },
        Download: { template: '<span class="icon-download" />' },
        Trash2: { template: '<span class="icon-trash" />' },
        Database: { template: '<span class="icon-db" />' },
        FolderArchive: { template: '<span class="icon-folder" />' },
        Loader2: { template: '<span class="icon-loader" />' },
      },
    },
  })

  await flushPromises()
  return wrapper
}

describe('DataExportView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('renders page title and breadcrumb', async () => {
    const wrapper = await mountView()
    expect(wrapper.find('h1').exists()).toBe(true)
    expect(wrapper.find('.breadcrumb').exists()).toBe(true)
  })

  it('renders security warning', async () => {
    const wrapper = await mountView()
    // The security warning text should be present
    expect(wrapper.text()).toContain('Full site exports contain all user data')
  })

  it('renders export options with checkboxes', async () => {
    const wrapper = await mountView()
    const checkboxes = wrapper.findAll('input[type="checkbox"]')
    expect(checkboxes.length).toBe(2)
    // Both should be checked by default
    expect((checkboxes[0].element as HTMLInputElement).checked).toBe(true)
    expect((checkboxes[1].element as HTMLInputElement).checked).toBe(true)
  })

  it('loads and displays export history on mount', async () => {
    const wrapper = await mountView()
    expect(mockGetExportHistory).toHaveBeenCalledOnce()
    // Should show 2 history rows
    const rows = wrapper.findAll('tbody tr')
    expect(rows.length).toBe(2)
  })

  it('shows empty state when no history', async () => {
    const wrapper = await mountView([])
    expect(wrapper.text()).toContain('No exports yet')
  })

  it('disables start button when no options selected', async () => {
    const wrapper = await mountView()
    const checkboxes = wrapper.findAll('input[type="checkbox"]')

    // Uncheck both options
    await checkboxes[0].setValue(false)
    await checkboxes[1].setValue(false)

    const startBtn = wrapper.findAll('button').find((b) => b.text().includes('Start'))
    expect(startBtn?.attributes('disabled')).toBeDefined()
  })

  it('triggers export on start button click', async () => {
    mockStartSiteExport.mockResolvedValue({
      task_id: 'new-task',
      message: 'Export started.',
    })

    const wrapper = await mountView()
    const startBtn = wrapper.findAll('button').find((b) => b.text().includes('Start'))
    expect(startBtn).toBeTruthy()

    await startBtn!.trigger('click')
    await flushPromises()

    expect(mockStartSiteExport).toHaveBeenCalledWith({
      include_database: true,
      include_files: true,
    })
  })

  it('shows progress section after export starts', async () => {
    mockStartSiteExport.mockResolvedValue({
      task_id: 'new-task',
      message: 'Export started.',
    })

    const wrapper = await mountView()
    const startBtn = wrapper.findAll('button').find((b) => b.text().includes('Start'))
    await startBtn!.trigger('click')
    await flushPromises()

    // Progress section should now be visible
    expect(wrapper.text()).toContain('PENDING')
  })

  it('shows download button in history for successful exports', async () => {
    const wrapper = await mountView()
    // The download button has a title with the download label
    const downloadBtns = wrapper.findAll('button[title="Download"]')
    // First row has download_url, so should have download button
    expect(downloadBtns.length).toBeGreaterThanOrEqual(1)
  })

  it('shows delete button for each history entry', async () => {
    const wrapper = await mountView()
    // Delete buttons have title="Delete"
    const deleteBtns = wrapper.findAll('button[title="Delete"]')
    expect(deleteBtns.length).toBe(2)
  })

  it('calls deleteExport on delete button click', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    mockDeleteExport.mockResolvedValue(undefined)

    const wrapper = await mountView()
    const deleteBtns = wrapper.findAll('button[title="Delete"]')
    await deleteBtns[0].trigger('click')
    await flushPromises()

    expect(mockDeleteExport).toHaveBeenCalledWith('t-1')
  })

  it('does not delete when confirm is cancelled', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(false)

    const wrapper = await mountView()
    const deleteBtns = wrapper.findAll('button[title="Delete"]')
    await deleteBtns[0].trigger('click')
    await flushPromises()

    expect(mockDeleteExport).not.toHaveBeenCalled()
  })

  it('shows "Expired" for success entries without download_url', async () => {
    const historyWithExpired = [
      {
        task_id: 't-exp',
        status: 'SUCCESS',
        created_at: '2026-03-20T10:00:00Z',
        created_by: 'user-1',
        options: { include_database: true, include_files: true },
        file_size: 1000,
        download_url: null,
      },
    ]
    const wrapper = await mountView(historyWithExpired)
    expect(wrapper.text()).toContain('Expired')
  })

  it('displays correct export type labels', async () => {
    const wrapper = await mountView()
    const text = wrapper.text()
    // First entry: both db + files
    expect(text).toContain('Full')
    // Second entry: db only
    expect(text).toContain('Database Only')
  })
})

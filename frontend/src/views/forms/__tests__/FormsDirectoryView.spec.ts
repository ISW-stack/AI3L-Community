import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import FormsDirectoryView from '../FormsDirectoryView.vue'
import { useAuthStore } from '@/stores/auth'
import type { UserProfile } from '@/types/user'

interface FormsDirectoryVm {
  searchQuery: string
  fetchForms: () => Promise<void>
  handleSearchInput: (value: string) => void
}

const mockListStandaloneForms = vi.fn()

vi.mock('@/api/forms', () => ({
  listStandaloneForms: (...args: unknown[]) => mockListStandaloneForms(...args),
}))

vi.mock('@/composables/api', () => ({
  default: { get: vi.fn(), post: vi.fn() },
}))

vi.mock('@/constants', () => ({
  HEARTBEAT_INTERVAL_MS: 30000,
}))

const fakeForms = [
  {
    id: 'form1',
    sig_id: null,
    title: 'Research Survey',
    description: 'A survey about research methods',
    is_active: true,
    response_count: 10,
    deadline: '2026-04-01T00:00:00Z',
    created_by: 'user1',
    created_by_name: 'Alice',
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    banner_url: null,
    max_respondents: null,
    questions: [],
    is_schema_locked: false,
    allow_non_members: false,
  },
  {
    id: 'form2',
    sig_id: null,
    title: 'Feedback Form',
    description: null,
    is_active: false,
    response_count: 25,
    deadline: null,
    created_by: 'user2',
    created_by_name: 'Bob',
    created_at: '2026-02-01T00:00:00Z',
    updated_at: '2026-02-01T00:00:00Z',
    banner_url: null,
    max_respondents: null,
    questions: [],
    is_schema_locked: false,
    allow_non_members: false,
  },
]

function createTestRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/forms', component: FormsDirectoryView },
      { path: '/forms/new', component: { template: '<div />' } },
      { path: '/forms/:formId', component: { template: '<div />' } },
    ],
  })
}

function createStubs() {
  return {
    BaseCard: {
      template: '<div class="base-card"><slot /></div>',
      props: ['hoverable'],
    },
    BaseButton: {
      template: '<button @click="$emit(\'click\')"><slot /></button>',
      props: ['loading', 'variant', 'size', 'disabled'],
    },
    BaseBadge: {
      template: '<span class="base-badge"><slot /></span>',
      props: ['variant'],
    },
    BaseInput: {
      template:
        '<input class="base-input" :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
      props: ['modelValue', 'placeholder'],
    },
    BasePagination: {
      template: '<div class="base-pagination" />',
      props: ['currentPage', 'totalPages', 'pageSize', 'total'],
    },
    SkeletonLoader: { template: '<div class="skeleton-loader" />', props: ['lines', 'variant'] },
    EmptyState: {
      template: '<div class="empty-state">{{ title }}</div>',
      props: ['title', 'message'],
    },
  }
}

async function mountDirectory(options?: { role?: string }) {
  const { role = 'MEMBER' } = options ?? {}
  const pinia = createPinia()
  setActivePinia(pinia)
  const router = createTestRouter()

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
  } as unknown as UserProfile

  await router.push('/forms')
  await router.isReady()

  const wrapper = mount(FormsDirectoryView, {
    global: { plugins: [pinia, router], stubs: createStubs() },
  })
  await flushPromises()
  return { wrapper, auth }
}

describe('FormsDirectoryView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockListStandaloneForms.mockResolvedValue({ forms: fakeForms, total: 2 })
  })

  it('renders page title "Forms"', async () => {
    const { wrapper } = await mountDirectory()
    expect(wrapper.text()).toContain('Forms')
  })

  it('shows private notice', async () => {
    const { wrapper } = await mountDirectory()
    expect(wrapper.text()).toContain('private to you')
  })

  it('fetches standalone forms on mount', async () => {
    await mountDirectory()
    expect(mockListStandaloneForms).toHaveBeenCalledWith(1, 12, undefined)
  })

  it('renders form cards', async () => {
    const { wrapper } = await mountDirectory()
    expect(wrapper.text()).toContain('Research Survey')
    expect(wrapper.text()).toContain('Feedback Form')
  })

  it('renders form descriptions', async () => {
    const { wrapper } = await mountDirectory()
    expect(wrapper.text()).toContain('A survey about research methods')
  })

  it('renders response counts', async () => {
    const { wrapper } = await mountDirectory()
    expect(wrapper.text()).toContain('10 responses')
    expect(wrapper.text()).toContain('25 responses')
  })

  it('renders status badges', async () => {
    const { wrapper } = await mountDirectory()
    expect(wrapper.text()).toContain('Active')
    expect(wrapper.text()).toContain('Closed')
  })

  it('renders total count', async () => {
    const { wrapper } = await mountDirectory()
    expect(wrapper.text()).toContain('2 total forms')
  })

  it('shows create button for authenticated non-guest users', async () => {
    const { wrapper } = await mountDirectory({ role: 'MEMBER' })
    const links = wrapper.findAll('a')
    const createLink = links.find((l) => l.attributes('href')?.includes('/forms/new'))
    expect(createLink).toBeTruthy()
  })

  it('hides create button for guest users', async () => {
    const { wrapper } = await mountDirectory({ role: 'GUEST' })
    const links = wrapper.findAll('a')
    const createLink = links.find((l) => l.attributes('href')?.includes('/forms/new'))
    expect(createLink).toBeUndefined()
  })

  it('shows empty state when no forms exist', async () => {
    mockListStandaloneForms.mockResolvedValue({ forms: [], total: 0 })
    const { wrapper } = await mountDirectory()
    expect(wrapper.find('.empty-state').exists()).toBe(true)
  })

  it('shows loading skeleton only on initial fetch', async () => {
    mockListStandaloneForms.mockReturnValue(new Promise(() => {}))
    const pinia = createPinia()
    setActivePinia(pinia)
    const router = createTestRouter()
    const auth = useAuthStore()
    auth.setSession('MEMBER', 3600)
    auth.user = { id: 'user1' } as unknown as UserProfile

    await router.push('/forms')
    await router.isReady()

    const wrapper = mount(FormsDirectoryView, {
      global: { plugins: [pinia, router], stubs: createStubs() },
    })
    await flushPromises()

    expect(wrapper.find('.skeleton-loader').exists()).toBe(true)
  })

  it('does not show skeleton on subsequent search fetches', async () => {
    const { wrapper } = await mountDirectory()
    // After initial load, skeleton should be gone
    expect(wrapper.find('.skeleton-loader').exists()).toBe(false)

    // Trigger a search — should NOT show skeleton
    mockListStandaloneForms.mockReturnValue(new Promise(() => {}))
    const vm = wrapper.vm as unknown as FormsDirectoryVm
    vm.searchQuery = 'test'
    vm.fetchForms()
    await flushPromises()

    expect(wrapper.find('.skeleton-loader').exists()).toBe(false)
    // Previous content should still be visible (with opacity applied)
    expect(wrapper.text()).toContain('Research Survey')
  })

  it('applies loading opacity during search without removing content', async () => {
    const { wrapper } = await mountDirectory()

    // Start a search that won't resolve
    mockListStandaloneForms.mockReturnValue(new Promise(() => {}))
    const vm = wrapper.vm as unknown as FormsDirectoryVm
    vm.searchQuery = 'test'
    vm.fetchForms()
    await flushPromises()

    // Content area should have opacity class
    const contentDiv = wrapper.find('.opacity-50')
    expect(contentDiv.exists()).toBe(true)
  })

  it('content area has min-height to prevent layout shift', async () => {
    mockListStandaloneForms.mockResolvedValue({ forms: [], total: 0 })
    const { wrapper } = await mountDirectory()
    const vm = wrapper.vm as unknown as FormsDirectoryVm
    vm.searchQuery = 'nonexistent'
    await vm.fetchForms()
    await flushPromises()

    // The wrapper div should have min-h class
    const minHeightDiv = wrapper.find('.min-h-\\[400px\\]')
    expect(minHeightDiv.exists()).toBe(true)
  })

  it('links form cards to detail page', async () => {
    const { wrapper } = await mountDirectory()
    const links = wrapper.findAll('a')
    const formLink = links.find((l) => l.attributes('href')?.includes('/forms/form1'))
    expect(formLink).toBeTruthy()
  })

  it('shows creator name', async () => {
    const { wrapper } = await mountDirectory()
    expect(wrapper.text()).toContain('Alice')
    expect(wrapper.text()).toContain('Bob')
  })

  it('renders search input', async () => {
    const { wrapper } = await mountDirectory()
    const searchInput = wrapper.find('.base-input')
    expect(searchInput.exists()).toBe(true)
  })

  it('filters forms by search query (server-side)', async () => {
    const { wrapper } = await mountDirectory()
    // Both forms should be visible initially
    expect(wrapper.text()).toContain('Research Survey')
    expect(wrapper.text()).toContain('Feedback Form')

    // Mock API to return only Research Survey when searching
    mockListStandaloneForms.mockResolvedValue({ forms: [fakeForms[0]], total: 1 })

    // Trigger search via the component API
    const vm = wrapper.vm as unknown as FormsDirectoryVm
    vm.searchQuery = 'Research'
    // Call fetchForms directly since debounce won't trigger in tests
    await vm.fetchForms()
    await flushPromises()

    // Only "Research Survey" should be visible
    expect(wrapper.text()).toContain('Research Survey')
    expect(wrapper.text()).not.toContain('Feedback Form')
  })

  it('shows empty state when search has no matches', async () => {
    mockListStandaloneForms.mockResolvedValue({ forms: [], total: 0 })
    const { wrapper } = await mountDirectory()
    const vm = wrapper.vm as unknown as FormsDirectoryVm
    vm.searchQuery = 'nonexistent'
    await vm.fetchForms()
    await flushPromises()

    const emptyStates = wrapper.findAll('.empty-state')
    expect(emptyStates.length).toBeGreaterThan(0)
  })

  it('clears search timeout on unmount', async () => {
    const { wrapper } = await mountDirectory()
    const clearTimeoutSpy = vi.spyOn(globalThis, 'clearTimeout')

    // Trigger a search to start the debounce timer
    const vm = wrapper.vm as unknown as FormsDirectoryVm
    vm.handleSearchInput('test')

    // Unmount should clear the pending timer
    wrapper.unmount()

    expect(clearTimeoutSpy).toHaveBeenCalled()
    clearTimeoutSpy.mockRestore()
  })
})

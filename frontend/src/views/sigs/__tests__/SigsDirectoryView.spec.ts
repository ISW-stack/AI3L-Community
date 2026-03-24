import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import SigsDirectoryView from '../SigsDirectoryView.vue'
import { useAuthStore } from '@/stores/auth'
import type { UserProfile } from '@/types/user'

const mockListSigs = vi.fn()

vi.mock('@/api/sigs', () => ({
  listSigs: (...args: unknown[]) => mockListSigs(...args),
}))

vi.mock('@/composables/api', () => ({
  default: { get: vi.fn(), post: vi.fn() },
}))

vi.mock('@/constants', () => ({
  HEARTBEAT_INTERVAL_MS: 30000,
}))

const fakeSigs = [
  {
    id: 'sig1',
    name: 'NLP Research Group',
    description: 'Focused on natural language processing',
    member_count: 15,
    created_at: '2026-01-01T00:00:00Z',
  },
  {
    id: 'sig2',
    name: 'AI in Education',
    description: 'Exploring AI applications in education',
    member_count: 8,
    created_at: '2026-02-01T00:00:00Z',
  },
  {
    id: 'sig3',
    name: 'Computer Vision Lab',
    description: null,
    member_count: 3,
    created_at: '2026-03-01T00:00:00Z',
  },
]

function createTestRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/sigs', component: SigsDirectoryView },
      { path: '/sigs/create', component: { template: '<div />' } },
      { path: '/sigs/:id', component: { template: '<div />' } },
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
      props: ['loading', 'variant', 'size'],
    },
    BaseInput: {
      template:
        '<input class="base-input" :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
      props: ['modelValue', 'placeholder'],
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

  await router.push('/sigs')
  await router.isReady()

  const wrapper = mount(SigsDirectoryView, {
    global: { plugins: [pinia, router], stubs: createStubs() },
  })
  await flushPromises()
  return { wrapper, auth }
}

describe('SigsDirectoryView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockListSigs.mockResolvedValue({ sigs: fakeSigs, total: 3 })
  })

  it('renders directory title', async () => {
    const { wrapper } = await mountDirectory()
    expect(wrapper.text()).toContain('Special Interest Groups')
  })

  it('fetches SIGs on mount', async () => {
    await mountDirectory()
    expect(mockListSigs).toHaveBeenCalled()
  })

  it('renders SIG cards', async () => {
    const { wrapper } = await mountDirectory()
    expect(wrapper.text()).toContain('NLP Research Group')
    expect(wrapper.text()).toContain('AI in Education')
    expect(wrapper.text()).toContain('Computer Vision Lab')
  })

  it('renders SIG descriptions', async () => {
    const { wrapper } = await mountDirectory()
    expect(wrapper.text()).toContain('Focused on natural language processing')
    expect(wrapper.text()).toContain('Exploring AI applications in education')
  })

  it('renders member counts', async () => {
    const { wrapper } = await mountDirectory()
    expect(wrapper.text()).toContain('15')
    expect(wrapper.text()).toContain('8')
    expect(wrapper.text()).toContain('3')
  })

  it('renders total count', async () => {
    const { wrapper } = await mountDirectory()
    expect(wrapper.text()).toContain('3')
  })

  it('shows create button for admin', async () => {
    const { wrapper } = await mountDirectory({ role: 'ADMIN' })
    const links = wrapper.findAll('a')
    const createLink = links.find((l) => l.attributes('href')?.includes('/sigs/create'))
    expect(createLink).toBeTruthy()
  })

  it('hides create button for non-admin', async () => {
    const { wrapper } = await mountDirectory({ role: 'MEMBER' })
    const links = wrapper.findAll('a')
    const createLink = links.find((l) => l.attributes('href')?.includes('/sigs/create'))
    expect(createLink).toBeUndefined()
  })

  it('shows search input', async () => {
    const { wrapper } = await mountDirectory()
    expect(wrapper.find('.base-input').exists()).toBe(true)
  })

  it('filters SIGs by search query (name)', async () => {
    const { wrapper } = await mountDirectory()
    const searchInput = wrapper.find('.base-input')
    await searchInput.setValue('NLP')
    await nextTick()

    // Only NLP Research Group should be visible
    expect(wrapper.text()).toContain('NLP Research Group')
    expect(wrapper.text()).not.toContain('AI in Education')
    expect(wrapper.text()).not.toContain('Computer Vision Lab')
  })

  it('filters SIGs by search query (description)', async () => {
    const { wrapper } = await mountDirectory()
    const searchInput = wrapper.find('.base-input')
    await searchInput.setValue('education')
    await nextTick()

    expect(wrapper.text()).not.toContain('NLP Research Group')
    expect(wrapper.text()).toContain('AI in Education')
  })

  it('shows empty state when search matches nothing', async () => {
    const { wrapper } = await mountDirectory()
    const searchInput = wrapper.find('.base-input')
    await searchInput.setValue('nonexistent query xyz')
    await nextTick()

    expect(wrapper.find('.empty-state').exists()).toBe(true)
  })

  it('shows empty state when no SIGs exist', async () => {
    mockListSigs.mockResolvedValue({ sigs: [], total: 0 })
    const { wrapper } = await mountDirectory()
    expect(wrapper.find('.empty-state').exists()).toBe(true)
  })

  it('shows loading skeleton initially', async () => {
    mockListSigs.mockReturnValue(new Promise(() => {}))
    const pinia = createPinia()
    setActivePinia(pinia)
    const router = createTestRouter()
    const auth = useAuthStore()
    auth.setSession('MEMBER', 3600)
    auth.user = { id: 'user1' } as unknown as UserProfile

    await router.push('/sigs')
    await router.isReady()

    const wrapper = mount(SigsDirectoryView, {
      global: { plugins: [pinia, router], stubs: createStubs() },
    })
    await flushPromises()

    expect(wrapper.find('.skeleton-loader').exists()).toBe(true)
  })

  it('links SIG cards to detail page', async () => {
    const { wrapper } = await mountDirectory()
    const links = wrapper.findAll('a')
    const sigLink = links.find((l) => l.attributes('href')?.includes('/sigs/sig1'))
    expect(sigLink).toBeTruthy()
  })
})

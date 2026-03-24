import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import AlbumsDirectoryView from '../AlbumsDirectoryView.vue'
import { useAuthStore } from '@/stores/auth'
import type { UserProfile } from '@/types/user'

const mockListAlbums = vi.fn()

vi.mock('@/api/albums', () => ({
  listAlbums: (...args: unknown[]) => mockListAlbums(...args),
}))

vi.mock('@/composables/api', () => ({
  default: { get: vi.fn(), post: vi.fn() },
}))

vi.mock('@/constants', () => ({
  HEARTBEAT_INTERVAL_MS: 30000,
}))

const fakeAlbums = [
  {
    id: 'album1',
    title: 'Conference Photos',
    description: 'Photos from AIED 2026',
    cover_photo_url: null,
    created_by: 'user1',
    created_by_name: 'Alice',
    is_archived: false,
    photo_count: 24,
    member_count: 5,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
  },
  {
    id: 'album2',
    title: 'Workshop Slides',
    description: null,
    cover_photo_url: 'http://example.com/cover.jpg',
    created_by: 'user2',
    created_by_name: 'Bob',
    is_archived: true,
    photo_count: 10,
    member_count: 3,
    created_at: '2026-02-01T00:00:00Z',
    updated_at: '2026-02-01T00:00:00Z',
  },
]

function createTestRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/albums', component: AlbumsDirectoryView },
      { path: '/albums/create', component: { template: '<div />' } },
      { path: '/albums/:id', component: { template: '<div />' } },
    ],
  })
}

function createStubs() {
  return {
    AlbumCard: {
      template: '<div class="album-card">{{ album.title }}</div>',
      props: ['album'],
    },
    BaseButton: {
      template: '<button @click="$emit(\'click\')"><slot /></button>',
      props: ['loading', 'variant', 'size'],
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

  await router.push('/albums')
  await router.isReady()

  const wrapper = mount(AlbumsDirectoryView, {
    global: { plugins: [pinia, router], stubs: createStubs() },
  })
  await flushPromises()
  return { wrapper, auth }
}

describe('AlbumsDirectoryView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockListAlbums.mockResolvedValue({ albums: fakeAlbums, total: 2 })
  })

  it('renders page title "Albums"', async () => {
    const { wrapper } = await mountDirectory()
    expect(wrapper.text()).toContain('Albums')
  })

  it('fetches albums on mount', async () => {
    await mountDirectory()
    expect(mockListAlbums).toHaveBeenCalledWith(1, 12)
  })

  it('renders album cards', async () => {
    const { wrapper } = await mountDirectory()
    expect(wrapper.text()).toContain('Conference Photos')
    expect(wrapper.text()).toContain('Workshop Slides')
  })

  it('renders total count', async () => {
    const { wrapper } = await mountDirectory()
    expect(wrapper.text()).toContain('2 total albums')
  })

  it('shows create button for admin', async () => {
    const { wrapper } = await mountDirectory({ role: 'ADMIN' })
    const links = wrapper.findAll('a')
    const createLink = links.find((l) => l.attributes('href')?.includes('/albums/create'))
    expect(createLink).toBeTruthy()
  })

  it('hides create button for non-admin', async () => {
    const { wrapper } = await mountDirectory({ role: 'MEMBER' })
    const links = wrapper.findAll('a')
    const createLink = links.find((l) => l.attributes('href')?.includes('/albums/create'))
    expect(createLink).toBeUndefined()
  })

  it('shows empty state when no albums exist', async () => {
    mockListAlbums.mockResolvedValue({ albums: [], total: 0 })
    const { wrapper } = await mountDirectory()
    expect(wrapper.find('.empty-state').exists()).toBe(true)
  })

  it('shows loading skeleton while fetching', async () => {
    mockListAlbums.mockReturnValue(new Promise(() => {}))
    const pinia = createPinia()
    setActivePinia(pinia)
    const router = createTestRouter()
    const auth = useAuthStore()
    auth.setSession('MEMBER', 3600)
    auth.user = { id: 'user1' } as unknown as UserProfile

    await router.push('/albums')
    await router.isReady()

    const wrapper = mount(AlbumsDirectoryView, {
      global: { plugins: [pinia, router], stubs: createStubs() },
    })
    await flushPromises()

    expect(wrapper.find('.skeleton-loader').exists()).toBe(true)
  })

  it('links album cards to detail page', async () => {
    const { wrapper } = await mountDirectory()
    const links = wrapper.findAll('a')
    const albumLink = links.find((l) => l.attributes('href')?.includes('/albums/album1'))
    expect(albumLink).toBeTruthy()
  })
})

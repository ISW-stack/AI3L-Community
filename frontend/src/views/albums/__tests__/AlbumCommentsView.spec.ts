import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { ref } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import AlbumCommentsView from '../AlbumCommentsView.vue'
import type { Album } from '@/types/album'

const mockListAlbumComments = vi.fn()
const mockCreateAlbumComment = vi.fn()
const mockDeleteAlbumComment = vi.fn()

vi.mock('@/api/albums', () => ({
  listAlbumComments: (...args: unknown[]) => mockListAlbumComments(...args),
  createAlbumComment: (...args: unknown[]) => mockCreateAlbumComment(...args),
  deleteAlbumComment: (...args: unknown[]) => mockDeleteAlbumComment(...args),
}))

vi.mock('@/composables/api', () => ({
  default: { get: vi.fn(), post: vi.fn() },
}))

vi.mock('@/constants', () => ({
  HEARTBEAT_INTERVAL_MS: 30000,
}))

const fakeAlbum: Album = {
  id: 'album-1',
  title: 'Test Album',
  description: null,
  cover_photo_url: null,
  created_by: 'user1',
  created_by_name: 'Alice',
  is_archived: false,
  photo_count: 2,
  member_count: 3,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
}

const fakeComments = [
  {
    id: 'comment1',
    album_id: 'album-1',
    photo_id: null,
    user_id: 'user1',
    display_name: 'Alice',
    avatar_url: null,
    parent_id: null,
    content: 'Great album!',
    is_deleted: false,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
  },
]

function createTestRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: { template: '<div />' } },
      {
        path: '/albums/:id',
        component: { template: '<router-view />' },
        children: [{ path: 'comments', name: 'album-comments', component: AlbumCommentsView }],
      },
    ],
  })
}

function createStubs() {
  return {
    BaseButton: {
      template: '<button @click="$emit(\'click\')"><slot /></button>',
      props: ['loading', 'variant', 'size', 'disabled'],
    },
    BasePagination: {
      template: '<div class="base-pagination" />',
      props: ['currentPage', 'totalPages', 'pageSize', 'total'],
    },
    BaseCard: {
      template: '<div class="base-card"><slot /></div>',
      props: ['class'],
    },
    BaseAvatar: {
      props: ['src', 'name', 'size'],
      template: '<img :alt="name" />',
    },
    SkeletonLoader: { template: '<div class="skeleton-loader" />', props: ['lines', 'variant'] },
    EmptyState: {
      template: '<div class="empty-state">{{ title }}</div>',
      props: ['title', 'message'],
    },
  }
}

async function mountCommentsView(options?: { role?: string | null; isGuest?: boolean }) {
  const { role = 'MEMBER', isGuest = false } = options ?? {}
  const pinia = createPinia()
  setActivePinia(pinia)
  const router = createTestRouter()

  // Set up auth store
  const { useAuthStore } = await import('@/stores/auth')
  const auth = useAuthStore()
  if (!isGuest) {
    auth.setSession(role ?? 'MEMBER', 3600)
    auth.user = {
      id: 'user1',
      username: 'testuser',
      display_name: 'Test User',
      role: role ?? 'MEMBER',
      bio: null,
      affiliation: null,
      orcid: null,
      avatar_url: null,
      is_banned: false,
      ban_reason: null,
    } as any
  }

  await router.push('/albums/album-1/comments')
  await router.isReady()

  const albumRef = ref<Album | null>(fakeAlbum)
  const userAlbumRoleRef = ref<string | null>(role)

  const wrapper = mount(AlbumCommentsView, {
    global: {
      plugins: [pinia, router],
      stubs: createStubs(),
      provide: {
        album: albumRef,
        userAlbumRole: userAlbumRoleRef,
      },
    },
  })
  await flushPromises()
  return { wrapper, albumRef, userAlbumRoleRef }
}

describe('AlbumCommentsView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockListAlbumComments.mockResolvedValue({
      data: { comments: fakeComments, total: 1 },
    })
  })

  it('renders section title "Comments"', async () => {
    const { wrapper } = await mountCommentsView()
    expect(wrapper.text()).toContain('Comments')
  })

  it('fetches comments on mount', async () => {
    await mountCommentsView()
    expect(mockListAlbumComments).toHaveBeenCalledWith('album-1', 1, 20)
  })

  it('shows empty state when no comments', async () => {
    mockListAlbumComments.mockResolvedValue({ data: { comments: [], total: 0 } })
    const { wrapper } = await mountCommentsView()
    expect(wrapper.find('.empty-state').exists()).toBe(true)
  })

  it('resets pagination to page 1 when album changes', async () => {
    mockListAlbumComments.mockResolvedValue({
      data: { comments: fakeComments, total: 50 },
    })

    const pinia = createPinia()
    setActivePinia(pinia)
    const router = createTestRouter()

    const { useAuthStore } = await import('@/stores/auth')
    const auth = useAuthStore()
    auth.setSession('MEMBER', 3600)
    auth.user = {
      id: 'user1',
      username: 'testuser',
      display_name: 'Test User',
      role: 'MEMBER',
      bio: null,
      affiliation: null,
      orcid: null,
      avatar_url: null,
      is_banned: false,
      ban_reason: null,
    } as any

    await router.push('/albums/album-1/comments')
    await router.isReady()

    const albumRef = ref<Album | null>(fakeAlbum)
    const userAlbumRoleRef = ref<string | null>('MEMBER')

    mount(AlbumCommentsView, {
      global: {
        plugins: [pinia, router],
        stubs: createStubs(),
        provide: {
          album: albumRef,
          userAlbumRole: userAlbumRoleRef,
        },
      },
    })
    await flushPromises()

    // Initial fetch should be page 1
    expect(mockListAlbumComments).toHaveBeenCalledWith('album-1', 1, 20)

    mockListAlbumComments.mockClear()

    // Simulate changing the album
    const newAlbum: Album = {
      ...fakeAlbum,
      id: 'album-2',
      title: 'Another Album',
    }
    albumRef.value = newAlbum
    await flushPromises()

    // After album change, the fetch should be called with page 1 (reset)
    expect(mockListAlbumComments).toHaveBeenCalledWith('album-2', 1, 20)
  })
})

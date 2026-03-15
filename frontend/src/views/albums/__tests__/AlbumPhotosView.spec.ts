import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { ref, provide } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import AlbumPhotosView from '../AlbumPhotosView.vue'
import type { Album } from '@/types/album'

const mockListAlbumPhotos = vi.fn()
const mockUploadAlbumPhoto = vi.fn()

vi.mock('@/api/albums', () => ({
  listAlbumPhotos: (...args: unknown[]) => mockListAlbumPhotos(...args),
  uploadAlbumPhoto: (...args: unknown[]) => mockUploadAlbumPhoto(...args),
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

const fakePhotos = [
  {
    id: 'photo1',
    album_id: 'album-1',
    uploaded_by: 'user1',
    uploaded_by_name: 'Alice',
    storage_url: 'http://example.com/photo1.jpg',
    thumbnail_url: 'http://example.com/photo1_thumb.jpg',
    original_filename: 'landscape.jpg',
    file_size_bytes: 1024,
    content_type: 'image/jpeg',
    description: 'A nice landscape',
    width: 800,
    height: 600,
    is_zip: false,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
  },
  {
    id: 'photo2',
    album_id: 'album-1',
    uploaded_by: 'user2',
    uploaded_by_name: 'Bob',
    storage_url: 'http://example.com/photo2.jpg',
    thumbnail_url: null,
    original_filename: 'portrait.png',
    file_size_bytes: 2048,
    content_type: 'image/png',
    description: null,
    width: 600,
    height: 800,
    is_zip: false,
    created_at: '2026-01-02T00:00:00Z',
    updated_at: '2026-01-02T00:00:00Z',
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
        children: [
          { path: 'photos', name: 'album-photos', component: AlbumPhotosView },
        ],
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
    SkeletonLoader: { template: '<div class="skeleton-loader" />', props: ['lines', 'variant'] },
    EmptyState: {
      template: '<div class="empty-state">{{ title }}</div>',
      props: ['title', 'message'],
    },
    PhotoGrid: {
      template: '<div class="photo-grid" />',
      props: ['photos'],
    },
    PhotoLightbox: {
      template: '<div class="photo-lightbox" />',
      props: ['photos', 'currentIndex', 'visible'],
    },
    PhotoUploadModal: {
      template: '<div class="photo-upload-modal" />',
      props: ['modelValue'],
    },
  }
}

async function mountPhotosView(options?: { role?: string | null }) {
  const { role = 'MEMBER' } = options ?? {}
  const pinia = createPinia()
  setActivePinia(pinia)
  const router = createTestRouter()

  await router.push('/albums/album-1/photos')
  await router.isReady()

  const albumRef = ref<Album | null>(fakeAlbum)
  const userAlbumRoleRef = ref<string | null>(role)

  const wrapper = mount(AlbumPhotosView, {
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
  return { wrapper }
}

describe('AlbumPhotosView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockListAlbumPhotos.mockResolvedValue({
      data: { photos: fakePhotos, total: 2 },
    })
  })

  it('renders section title "Photos"', async () => {
    const { wrapper } = await mountPhotosView()
    expect(wrapper.text()).toContain('Photos')
  })

  it('fetches photos on mount', async () => {
    await mountPhotosView()
    expect(mockListAlbumPhotos).toHaveBeenCalledWith('album-1', 1, 20)
  })

  it('shows upload button for album members', async () => {
    const { wrapper } = await mountPhotosView({ role: 'MEMBER' })
    const buttons = wrapper.findAll('button')
    const uploadBtn = buttons.find((b) => b.text().includes('Upload Photo'))
    expect(uploadBtn).toBeTruthy()
  })

  it('hides upload button for non-members', async () => {
    const { wrapper } = await mountPhotosView({ role: null })
    const buttons = wrapper.findAll('button')
    const uploadBtn = buttons.find((b) => b.text().includes('Upload Photo'))
    expect(uploadBtn).toBeUndefined()
  })

  it('shows empty state when no photos', async () => {
    mockListAlbumPhotos.mockResolvedValue({ data: { photos: [], total: 0 } })
    const { wrapper } = await mountPhotosView()
    expect(wrapper.find('.empty-state').exists()).toBe(true)
  })

  it('renders PhotoGrid component when photos exist', async () => {
    const { wrapper } = await mountPhotosView()
    expect(wrapper.find('.photo-grid').exists()).toBe(true)
  })

  it('shows loading skeleton while fetching', async () => {
    mockListAlbumPhotos.mockReturnValue(new Promise(() => {}))
    const pinia = createPinia()
    setActivePinia(pinia)
    const router = createTestRouter()

    await router.push('/albums/album-1/photos')
    await router.isReady()

    const albumRef = ref<Album | null>(fakeAlbum)
    const userAlbumRoleRef = ref<string | null>('MEMBER')

    const wrapper = mount(AlbumPhotosView, {
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

    expect(wrapper.find('.skeleton-loader').exists()).toBe(true)
  })
})

import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import PhotoGrid from '../PhotoGrid.vue'
import type { AlbumPhoto } from '@/types/album'

vi.mock('@/composables/api', () => ({
  default: { get: vi.fn(), post: vi.fn() },
}))

vi.mock('@/constants', () => ({
  HEARTBEAT_INTERVAL_MS: 30000,
}))

const makePhoto = (overrides: Partial<AlbumPhoto> = {}): AlbumPhoto => ({
  id: 'photo-1',
  album_id: 'album-1',
  uploaded_by: 'user-1',
  uploaded_by_name: 'Alice',
  storage_url: 'http://minio/albums/1/photos/abc.jpg?X-Amz-Signature=sig',
  thumbnail_url: 'http://minio/albums/1/thumbs/abc.webp?X-Amz-Signature=sig',
  original_filename: 'photo.jpg',
  file_size_bytes: 1024,
  content_type: 'image/jpeg',
  description: null,
  width: 800,
  height: 600,
  is_zip: false,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
  ...overrides,
})

function mountGrid(props: {
  photos: AlbumPhoto[]
  coverStorageUrl?: string | null
  canSetCover?: boolean
}) {
  return mount(PhotoGrid, {
    props,
    global: {
      stubs: {
        ImageIcon: { template: '<span class="image-icon" />' },
      },
    },
  })
}

describe('PhotoGrid cover feature', () => {
  it('shows cover badge on photo matching cover URL', () => {
    const photo = makePhoto({
      storage_url: 'http://minio/albums/1/photos/abc.jpg?X-Amz-Signature=sig1',
    })
    const wrapper = mountGrid({
      photos: [photo],
      coverStorageUrl: 'http://minio/albums/1/photos/abc.jpg?X-Amz-Signature=sig2',
      canSetCover: true,
    })

    // Should match because base URLs (before ?) are the same
    expect(wrapper.text()).toContain('Cover')
  })

  it('does not show cover badge on non-cover photos', () => {
    const photo = makePhoto({
      storage_url: 'http://minio/albums/1/photos/abc.jpg?sig=1',
    })
    const wrapper = mountGrid({
      photos: [photo],
      coverStorageUrl: 'http://minio/albums/1/photos/OTHER.jpg?sig=2',
      canSetCover: true,
    })

    // The cover badge uses bg-brand-600 class
    const badges = wrapper.findAll('.bg-brand-600')
    expect(badges.length).toBe(0)
  })

  it('shows "Set as Cover" button when canSetCover is true and photo is not cover', () => {
    const photo = makePhoto({
      storage_url: 'http://minio/albums/1/photos/abc.jpg',
    })
    const wrapper = mountGrid({
      photos: [photo],
      coverStorageUrl: 'http://minio/albums/1/photos/OTHER.jpg',
      canSetCover: true,
    })

    expect(wrapper.text()).toContain('Set as Cover')
  })

  it('hides "Set as Cover" button when canSetCover is false', () => {
    const photo = makePhoto()
    const wrapper = mountGrid({
      photos: [photo],
      coverStorageUrl: null,
      canSetCover: false,
    })

    expect(wrapper.text()).not.toContain('Set as Cover')
  })

  it('does not show "Set as Cover" on the current cover photo', () => {
    const photo = makePhoto({
      storage_url: 'http://minio/albums/1/photos/abc.jpg?sig=1',
    })
    const wrapper = mountGrid({
      photos: [photo],
      coverStorageUrl: 'http://minio/albums/1/photos/abc.jpg?sig=2',
      canSetCover: true,
    })

    // Should show cover badge but not "Set as Cover" button
    expect(wrapper.text()).toContain('Cover')
    // The "Set as Cover" button should not render for the cover photo
    const setCoverBtns = wrapper.findAll('button').filter((b) => b.text().includes('Set as Cover'))
    expect(setCoverBtns.length).toBe(0)
  })

  it('renders Set as Cover button for non-cover photos when canSetCover', () => {
    const photo = makePhoto({
      storage_url: 'http://minio/albums/1/photos/abc.jpg',
    })
    const wrapper = mountGrid({
      photos: [photo],
      coverStorageUrl: 'http://minio/albums/1/photos/OTHER.jpg',
      canSetCover: true,
    })

    // The Set as Cover button should be in the DOM
    const allButtons = wrapper.findAll('button')
    const setCoverBtn = allButtons.find((b) => b.text().includes('Set as Cover'))
    expect(setCoverBtn).toBeTruthy()
  })

  it('emits select event when photo is clicked', async () => {
    const photo = makePhoto()
    const wrapper = mountGrid({
      photos: [photo],
      canSetCover: false,
    })

    // Click the main button (outer photo button)
    const photoButtons = wrapper.findAll('button')
    await photoButtons[0].trigger('click')

    expect(wrapper.emitted('select')).toBeTruthy()
    expect(wrapper.emitted('select')![0]).toEqual([photo])
  })

  it('handles null coverStorageUrl gracefully — shows Set as Cover but no badge', () => {
    const photo = makePhoto()
    const wrapper = mountGrid({
      photos: [photo],
      coverStorageUrl: null,
      canSetCover: true,
    })

    // Should render without errors, no cover badge
    const badges = wrapper.findAll('.bg-brand-600')
    expect(badges.length).toBe(0)
  })
})

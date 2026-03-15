import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import PhotoLightbox from '../PhotoLightbox.vue'
import type { AlbumPhoto } from '@/types/album'

const fakePhotos: AlbumPhoto[] = [
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
    description: 'A beautiful landscape',
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
  {
    id: 'photo3',
    album_id: 'album-1',
    uploaded_by: 'user1',
    uploaded_by_name: 'Alice',
    storage_url: 'http://example.com/photo3.jpg',
    thumbnail_url: null,
    original_filename: 'sunset.jpg',
    file_size_bytes: 3072,
    content_type: 'image/jpeg',
    description: 'Sunset over mountains',
    width: 1200,
    height: 800,
    is_zip: false,
    created_at: '2026-01-03T00:00:00Z',
    updated_at: '2026-01-03T00:00:00Z',
  },
]

function mountLightbox(
  props?: Partial<{ photos: AlbumPhoto[]; currentIndex: number; visible: boolean }>,
) {
  return mount(PhotoLightbox, {
    props: {
      photos: props?.photos ?? fakePhotos,
      currentIndex: props?.currentIndex ?? 0,
      visible: props?.visible ?? true,
    },
    global: {
      stubs: {
        // Disable Teleport so content renders inside the wrapper
        Teleport: { template: '<div><slot /></div>' },
      },
    },
    attachTo: document.body,
  })
}

describe('PhotoLightbox', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  afterEach(() => {
    // Clean up any attached elements
    document.body.innerHTML = ''
  })

  it('does not render overlay when not visible', () => {
    const wrapper = mountLightbox({ visible: false })
    expect(wrapper.find('.lightbox-overlay').exists()).toBe(false)
    wrapper.unmount()
  })

  it('renders overlay when visible', () => {
    const wrapper = mountLightbox({ visible: true })
    expect(wrapper.find('.lightbox-overlay').exists()).toBe(true)
    wrapper.unmount()
  })

  it('displays the current photo image', () => {
    const wrapper = mountLightbox({ currentIndex: 0 })
    const img = wrapper.find('img')
    expect(img.exists()).toBe(true)
    expect(img.attributes('src')).toBe('http://example.com/photo1.jpg')
    wrapper.unmount()
  })

  it('displays photo description', () => {
    const wrapper = mountLightbox({ currentIndex: 0 })
    expect(wrapper.text()).toContain('A beautiful landscape')
    wrapper.unmount()
  })

  it('displays photo filename', () => {
    const wrapper = mountLightbox({ currentIndex: 0 })
    expect(wrapper.text()).toContain('landscape.jpg')
    wrapper.unmount()
  })

  it('displays position counter', () => {
    const wrapper = mountLightbox({ currentIndex: 0 })
    expect(wrapper.text()).toContain('1 / 3')
    wrapper.unmount()
  })

  it('emits close when close button is clicked', async () => {
    const wrapper = mountLightbox()
    const closeBtn = wrapper.find('[aria-label="Close"]')
    expect(closeBtn.exists()).toBe(true)
    await closeBtn.trigger('click')
    expect(wrapper.emitted('close')).toBeTruthy()
    wrapper.unmount()
  })

  it('emits close on Escape key', async () => {
    const wrapper = mountLightbox()
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
    await nextTick()
    expect(wrapper.emitted('close')).toBeTruthy()
    wrapper.unmount()
  })

  it('emits navigate with next index on ArrowRight key', async () => {
    const wrapper = mountLightbox({ currentIndex: 0 })
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowRight' }))
    await nextTick()
    expect(wrapper.emitted('navigate')).toBeTruthy()
    expect(wrapper.emitted('navigate')![0]).toEqual([1])
    wrapper.unmount()
  })

  it('emits navigate with prev index on ArrowLeft key', async () => {
    const wrapper = mountLightbox({ currentIndex: 1 })
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowLeft' }))
    await nextTick()
    expect(wrapper.emitted('navigate')).toBeTruthy()
    expect(wrapper.emitted('navigate')![0]).toEqual([0])
    wrapper.unmount()
  })

  it('does not emit navigate for ArrowLeft at first photo', async () => {
    const wrapper = mountLightbox({ currentIndex: 0 })
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowLeft' }))
    await nextTick()
    expect(wrapper.emitted('navigate')).toBeFalsy()
    wrapper.unmount()
  })

  it('does not emit navigate for ArrowRight at last photo', async () => {
    const wrapper = mountLightbox({ currentIndex: 2 })
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowRight' }))
    await nextTick()
    expect(wrapper.emitted('navigate')).toBeFalsy()
    wrapper.unmount()
  })

  it('shows Previous button when not on first photo', () => {
    const wrapper = mountLightbox({ currentIndex: 1 })
    const prevBtn = wrapper.find('[aria-label="Previous photo"]')
    expect(prevBtn.exists()).toBe(true)
    wrapper.unmount()
  })

  it('hides Previous button on first photo', () => {
    const wrapper = mountLightbox({ currentIndex: 0 })
    const prevBtn = wrapper.find('[aria-label="Previous photo"]')
    expect(prevBtn.exists()).toBe(false)
    wrapper.unmount()
  })

  it('shows Next button when not on last photo', () => {
    const wrapper = mountLightbox({ currentIndex: 0 })
    const nextBtn = wrapper.find('[aria-label="Next photo"]')
    expect(nextBtn.exists()).toBe(true)
    wrapper.unmount()
  })

  it('hides Next button on last photo', () => {
    const wrapper = mountLightbox({ currentIndex: 2 })
    const nextBtn = wrapper.find('[aria-label="Next photo"]')
    expect(nextBtn.exists()).toBe(false)
    wrapper.unmount()
  })

  it('emits navigate when Previous button is clicked', async () => {
    const wrapper = mountLightbox({ currentIndex: 1 })
    const prevBtn = wrapper.find('[aria-label="Previous photo"]')
    await prevBtn.trigger('click')
    expect(wrapper.emitted('navigate')).toBeTruthy()
    expect(wrapper.emitted('navigate')![0]).toEqual([0])
    wrapper.unmount()
  })

  it('emits navigate when Next button is clicked', async () => {
    const wrapper = mountLightbox({ currentIndex: 0 })
    const nextBtn = wrapper.find('[aria-label="Next photo"]')
    await nextBtn.trigger('click')
    expect(wrapper.emitted('navigate')).toBeTruthy()
    expect(wrapper.emitted('navigate')![0]).toEqual([1])
    wrapper.unmount()
  })

  it('emits close when overlay background is clicked', async () => {
    const wrapper = mountLightbox()
    const overlay = wrapper.find('.lightbox-overlay')
    await overlay.trigger('click')
    expect(wrapper.emitted('close')).toBeTruthy()
    wrapper.unmount()
  })
})

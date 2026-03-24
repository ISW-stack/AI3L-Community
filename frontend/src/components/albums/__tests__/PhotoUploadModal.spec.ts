import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import PhotoUploadModal from '../PhotoUploadModal.vue'

vi.mock('@/composables/api', () => ({
  default: { get: vi.fn(), post: vi.fn() },
}))

vi.mock('@/constants', () => ({
  HEARTBEAT_INTERVAL_MS: 30000,
}))

function mountModal(modelValue = true) {
  const pinia = createPinia()
  setActivePinia(pinia)
  return mount(PhotoUploadModal, {
    props: { modelValue },
    global: {
      plugins: [pinia],
      stubs: {
        BaseModal: {
          template:
            '<div class="modal"><slot /><div class="footer"><slot name="footer" /></div></div>',
          props: ['modelValue', 'title', 'size'],
        },
        BaseButton: {
          template: '<button :disabled="disabled" @click="$emit(\'click\')"><slot /></button>',
          props: ['variant', 'disabled', 'loading', 'size'],
        },
        BaseAlert: {
          template: '<div class="alert" :data-type="type"><slot /></div>',
          props: ['type'],
        },
      },
    },
  })
}

function createFile(name: string, type: string, size = 100): File {
  const content = new Uint8Array(size)
  return new File([content], name, { type })
}

describe('PhotoUploadModal', () => {
  it('emits "upload" for image files', async () => {
    const wrapper = mountModal()
    const input = wrapper.find('input[type="file"]')

    const jpgFile = createFile('photo.jpg', 'image/jpeg')
    Object.defineProperty(input.element, 'files', { value: [jpgFile], writable: false })
    await input.trigger('change')

    // Click the upload button (last button in footer)
    const buttons = wrapper.findAll('button')
    const uploadBtn = buttons[buttons.length - 1]
    await uploadBtn.trigger('click')

    expect(wrapper.emitted('upload')).toBeTruthy()
    expect(wrapper.emitted('upload')![0][0]).toBeInstanceOf(File)
    expect((wrapper.emitted('upload')![0][0] as File).name).toBe('photo.jpg')
    expect(wrapper.emitted('uploadZip')).toBeFalsy()
  })

  it('emits "uploadZip" for ZIP files by MIME type', async () => {
    const wrapper = mountModal()
    const input = wrapper.find('input[type="file"]')

    const zipFile = createFile('archive.zip', 'application/zip')
    Object.defineProperty(input.element, 'files', { value: [zipFile], writable: false })
    await input.trigger('change')

    const buttons = wrapper.findAll('button')
    const uploadBtn = buttons[buttons.length - 1]
    await uploadBtn.trigger('click')

    expect(wrapper.emitted('uploadZip')).toBeTruthy()
    expect(wrapper.emitted('uploadZip')![0][0]).toBeInstanceOf(File)
    expect(wrapper.emitted('upload')).toBeFalsy()
  })

  it('emits "uploadZip" for x-zip-compressed type', async () => {
    const wrapper = mountModal()
    const input = wrapper.find('input[type="file"]')

    const zipFile = createFile('data.zip', 'application/x-zip-compressed')
    Object.defineProperty(input.element, 'files', { value: [zipFile], writable: false })
    await input.trigger('change')

    const buttons = wrapper.findAll('button')
    const uploadBtn = buttons[buttons.length - 1]
    await uploadBtn.trigger('click')

    expect(wrapper.emitted('uploadZip')).toBeTruthy()
    expect(wrapper.emitted('upload')).toBeFalsy()
  })

  it('emits "uploadZip" for .zip extension even with empty MIME', async () => {
    const wrapper = mountModal()
    const input = wrapper.find('input[type="file"]')

    // Some browsers/OS report empty MIME for ZIP files
    const zipFile = createFile('photos.zip', '')
    Object.defineProperty(input.element, 'files', { value: [zipFile], writable: false })
    await input.trigger('change')

    const buttons = wrapper.findAll('button')
    const uploadBtn = buttons[buttons.length - 1]
    await uploadBtn.trigger('click')

    expect(wrapper.emitted('uploadZip')).toBeTruthy()
    expect(wrapper.emitted('upload')).toBeFalsy()
  })

  it('shows ZIP info alert when ZIP file selected', async () => {
    const wrapper = mountModal()
    const input = wrapper.find('input[type="file"]')

    const zipFile = createFile('archive.zip', 'application/zip')
    Object.defineProperty(input.element, 'files', { value: [zipFile], writable: false })
    await input.trigger('change')

    const alerts = wrapper.findAll('.alert[data-type="info"]')
    expect(alerts.length).toBeGreaterThan(0)
  })

  it('does not show ZIP info alert for image files', async () => {
    const wrapper = mountModal()
    const input = wrapper.find('input[type="file"]')

    const imgFile = createFile('photo.png', 'image/png')
    Object.defineProperty(input.element, 'files', { value: [imgFile], writable: false })
    await input.trigger('change')

    const alerts = wrapper.findAll('.alert[data-type="info"]')
    expect(alerts.length).toBe(0)
  })

  it('does not emit upload when no file selected', async () => {
    const wrapper = mountModal()

    const buttons = wrapper.findAll('button')
    const uploadBtn = buttons[buttons.length - 1]
    await uploadBtn.trigger('click')

    expect(wrapper.emitted('upload')).toBeFalsy()
    expect(wrapper.emitted('uploadZip')).toBeFalsy()
  })

  it('accepts both image and zip in the file input accept attribute', () => {
    const wrapper = mountModal()
    const input = wrapper.find('input[type="file"]')
    const accept = input.attributes('accept') || ''
    expect(accept).toContain('image/jpeg')
    expect(accept).toContain('application/zip')
  })
})

describe('FE-15: PhotoUploadModal file size validation', () => {
  function createSizedFile(name: string, type: string, sizeBytes: number): File {
    // Create a minimal file and override size property
    const file = new File(['x'], name, { type })
    Object.defineProperty(file, 'size', { value: sizeBytes, writable: false })
    return file
  }

  it('rejects image file exceeding 10 MB', async () => {
    const wrapper = mountModal()
    const input = wrapper.find('input[type="file"]')

    const bigImage = createSizedFile('photo.jpg', 'image/jpeg', 11 * 1024 * 1024)
    Object.defineProperty(input.element, 'files', { value: [bigImage], writable: false })
    await input.trigger('change')

    const html = wrapper.html()
    expect(html).toContain('File too large')
    expect(html).toContain('10 MB')
  })

  it('rejects zip file exceeding 50 MB', async () => {
    const wrapper = mountModal()
    const input = wrapper.find('input[type="file"]')

    const bigZip = createSizedFile('archive.zip', 'application/zip', 51 * 1024 * 1024)
    Object.defineProperty(input.element, 'files', { value: [bigZip], writable: false })
    await input.trigger('change')

    const html = wrapper.html()
    expect(html).toContain('File too large')
    expect(html).toContain('50 MB')
  })

  it('accepts image file under 10 MB', async () => {
    const wrapper = mountModal()
    const input = wrapper.find('input[type="file"]')

    const smallImage = createSizedFile('photo.jpg', 'image/jpeg', 5 * 1024 * 1024)
    Object.defineProperty(input.element, 'files', { value: [smallImage], writable: false })
    await input.trigger('change')

    const html = wrapper.html()
    expect(html).not.toContain('File too large')
  })

  it('accepts zip file under 50 MB', async () => {
    const wrapper = mountModal()
    const input = wrapper.find('input[type="file"]')

    const smallZip = createSizedFile('archive.zip', 'application/zip', 40 * 1024 * 1024)
    Object.defineProperty(input.element, 'files', { value: [smallZip], writable: false })
    await input.trigger('change')

    const html = wrapper.html()
    expect(html).not.toContain('File too large')
  })

  it('does not set selectedFile when file is too large', async () => {
    const wrapper = mountModal()
    const input = wrapper.find('input[type="file"]')

    const bigImage = createSizedFile('huge.png', 'image/png', 15 * 1024 * 1024)
    Object.defineProperty(input.element, 'files', { value: [bigImage], writable: false })
    await input.trigger('change')

    // Upload button should not trigger upload since no file is selected
    const buttons = wrapper.findAll('button')
    const uploadBtn = buttons[buttons.length - 1]
    await uploadBtn.trigger('click')

    expect(wrapper.emitted('upload')).toBeFalsy()
  })
})

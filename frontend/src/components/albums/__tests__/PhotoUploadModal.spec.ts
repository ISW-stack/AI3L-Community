import { describe, it, expect, vi, beforeEach } from 'vitest'
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

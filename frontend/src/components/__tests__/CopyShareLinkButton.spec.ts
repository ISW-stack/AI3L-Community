import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import CopyShareLinkButton from '../CopyShareLinkButton.vue'

vi.mock('lucide-vue-next', () => ({
  Copy: { name: 'Copy', template: '<svg data-testid="copy-icon" />' },
  Check: { name: 'Check', template: '<svg data-testid="check-icon" />' },
}))

vi.mock('@/components/base/BaseButton.vue', () => ({
  default: {
    props: ['variant', 'size'],
    template: '<button @click="$emit(\'click\')"><slot /></button>',
  },
}))

describe('CopyShareLinkButton', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.restoreAllMocks()
  })

  it('should render the default label text', () => {
    const wrapper = mount(CopyShareLinkButton, {
      props: { url: 'https://example.com/share' },
    })
    // i18n key share.copyLink should render
    expect(wrapper.text()).toBeTruthy()
  })

  it('should render custom label when provided', () => {
    const wrapper = mount(CopyShareLinkButton, {
      props: { url: 'https://example.com/share', label: 'Share this' },
    })
    expect(wrapper.text()).toContain('Share this')
  })

  it('should show Copy icon initially', () => {
    const wrapper = mount(CopyShareLinkButton, {
      props: { url: 'https://example.com/share' },
    })
    expect(wrapper.find('[data-testid="copy-icon"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="check-icon"]').exists()).toBe(false)
  })

  it('should copy URL to clipboard and show Check icon on click', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined)
    Object.assign(navigator, { clipboard: { writeText } })

    const wrapper = mount(CopyShareLinkButton, {
      props: { url: 'https://example.com/share' },
    })

    await wrapper.find('button').trigger('click')
    // Wait for async copyLink to complete
    await vi.dynamicImportSettled()

    expect(writeText).toHaveBeenCalledWith('https://example.com/share')
    expect(wrapper.find('[data-testid="check-icon"]').exists()).toBe(true)
  })

  it('should handle clipboard failure gracefully', async () => {
    const writeText = vi.fn().mockRejectedValue(new Error('denied'))
    Object.assign(navigator, { clipboard: { writeText } })

    const wrapper = mount(CopyShareLinkButton, {
      props: { url: 'https://example.com/share' },
    })

    await wrapper.find('button').trigger('click')
    await vi.dynamicImportSettled()

    // Should still show Copy icon (not switched to Check)
    expect(wrapper.find('[data-testid="copy-icon"]').exists()).toBe(true)
  })
})

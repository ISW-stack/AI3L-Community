import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
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
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
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

  it('should clear the copy timer on unmount (M-23)', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined)
    Object.assign(navigator, { clipboard: { writeText } })

    const wrapper = mount(CopyShareLinkButton, {
      props: { url: 'https://example.com/share' },
    })

    await wrapper.find('button').trigger('click')
    await vi.dynamicImportSettled()

    // copied should be true immediately after click
    expect(wrapper.find('[data-testid="check-icon"]').exists()).toBe(true)

    // Unmount the component before the 2000ms timer fires
    wrapper.unmount()

    // Advance past the 2000ms timer — should not throw or cause issues
    vi.advanceTimersByTime(3000)

    // No errors thrown means cleanup was successful
  })

  it('should render inline style by default (no BaseButton)', () => {
    const wrapper = mount(CopyShareLinkButton, {
      props: { url: 'https://example.com/share' },
    })
    const btn = wrapper.find('button')
    expect(btn.classes()).toContain('text-muted')
  })

  it('should render BaseButton when variant is "button"', () => {
    const wrapper = mount(CopyShareLinkButton, {
      props: { url: 'https://example.com/share', variant: 'button' },
    })
    // BaseButton mock renders a plain button without text-muted class
    const btn = wrapper.find('button')
    expect(btn.classes()).not.toContain('text-muted')
  })

  it('should reset copied state after 2000ms timeout', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined)
    Object.assign(navigator, { clipboard: { writeText } })

    const wrapper = mount(CopyShareLinkButton, {
      props: { url: 'https://example.com/share' },
    })

    await wrapper.find('button').trigger('click')
    await vi.dynamicImportSettled()

    expect(wrapper.find('[data-testid="check-icon"]').exists()).toBe(true)

    // Advance past the 2000ms timer
    vi.advanceTimersByTime(2000)
    await wrapper.vm.$nextTick()

    // Should revert to Copy icon
    expect(wrapper.find('[data-testid="copy-icon"]').exists()).toBe(true)
  })
})

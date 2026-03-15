import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import BaseModal, { _resetModalCount } from '../base/BaseModal.vue'

function mountModal(props: Record<string, unknown> = {}) {
  return mount(BaseModal, {
    props: {
      modelValue: false,
      ...props,
    },
    global: {
      stubs: {
        Teleport: true,
        Transition: false,
      },
    },
  })
}

/** Mount a modal closed, then open it by flipping modelValue to true. */
async function mountAndOpen(extraProps: Record<string, unknown> = {}) {
  const wrapper = mountModal(extraProps)
  await wrapper.setProps({ modelValue: true })
  await nextTick()
  return wrapper
}

describe('BaseModal', () => {
  beforeEach(() => {
    document.body.style.overflow = ''
    _resetModalCount()
  })

  afterEach(() => {
    document.body.style.overflow = ''
    _resetModalCount()
  })

  // --- Single modal: body overflow hidden when open, restored when closed ---

  it('sets body overflow hidden when a single modal opens', async () => {
    const wrapper = mountModal()

    expect(document.body.style.overflow).toBe('')

    await wrapper.setProps({ modelValue: true })
    await nextTick()

    expect(document.body.style.overflow).toBe('hidden')

    wrapper.unmount()
  })

  it('restores body overflow when a single modal closes', async () => {
    const wrapper = await mountAndOpen()

    expect(document.body.style.overflow).toBe('hidden')

    await wrapper.setProps({ modelValue: false })
    await nextTick()

    expect(document.body.style.overflow).toBe('')

    wrapper.unmount()
  })

  // --- Multiple modals: body overflow stays hidden until ALL modals close ---

  it('keeps body overflow hidden when one of two modals closes', async () => {
    const modal1 = await mountAndOpen()
    const modal2 = await mountAndOpen()

    expect(document.body.style.overflow).toBe('hidden')

    // Close first modal
    await modal1.setProps({ modelValue: false })
    await nextTick()

    // Body should still be hidden because modal2 is still open
    expect(document.body.style.overflow).toBe('hidden')

    // Close second modal
    await modal2.setProps({ modelValue: false })
    await nextTick()

    // Now body should be restored
    expect(document.body.style.overflow).toBe('')

    modal1.unmount()
    modal2.unmount()
  })

  // --- Unmount while open: body overflow restored ---

  it('restores body overflow when modal is unmounted while open', async () => {
    const wrapper = await mountAndOpen()

    expect(document.body.style.overflow).toBe('hidden')

    wrapper.unmount()

    expect(document.body.style.overflow).toBe('')
  })

  it('keeps body overflow hidden when one of two open modals is unmounted', async () => {
    const modal1 = await mountAndOpen()
    const modal2 = await mountAndOpen()

    expect(document.body.style.overflow).toBe('hidden')

    // Unmount first modal while still open
    modal1.unmount()

    // Second modal still open, so overflow stays hidden
    expect(document.body.style.overflow).toBe('hidden')

    modal2.unmount()

    expect(document.body.style.overflow).toBe('')
  })

  // --- Emits update:modelValue on close ---

  it('emits update:modelValue false when clicking close button', async () => {
    const wrapper = await mountAndOpen({ title: 'Test' })

    const closeBtn = wrapper.find('button[aria-label="Close"]')
    expect(closeBtn.exists()).toBe(true)

    await closeBtn.trigger('click')

    expect(wrapper.emitted('update:modelValue')).toBeTruthy()
    const emissions = wrapper.emitted('update:modelValue')!
    expect(emissions[emissions.length - 1]).toEqual([false])

    wrapper.unmount()
  })

  it('does not emit close when persistent', async () => {
    const wrapper = await mountAndOpen({ persistent: true })

    // Clicking backdrop
    const backdrop = wrapper.find('[role="dialog"]')
    if (backdrop.exists()) {
      await backdrop.trigger('click')
    }

    // Only the initial open emission should exist
    const emissions = wrapper.emitted('update:modelValue') || []
    const closeEmissions = emissions.filter((e) => e[0] === false)
    expect(closeEmissions).toHaveLength(0)

    wrapper.unmount()
  })

  // --- Renders title ---

  it('renders the title when provided', async () => {
    const wrapper = await mountAndOpen({ title: 'My Modal' })

    expect(wrapper.text()).toContain('My Modal')

    wrapper.unmount()
  })

  // --- Size classes ---

  it('applies the correct size class', async () => {
    const wrapper = await mountAndOpen({ size: 'lg' })

    expect(wrapper.html()).toContain('max-w-lg')

    wrapper.unmount()
  })
})

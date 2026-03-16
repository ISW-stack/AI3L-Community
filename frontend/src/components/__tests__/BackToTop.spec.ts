import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import BackToTop from '../BackToTop.vue'

vi.mock('@/constants', () => ({
  HEARTBEAT_INTERVAL_MS: 30000,
}))

vi.mock('@/composables/api', () => ({
  default: { get: vi.fn(), post: vi.fn() },
}))

describe('BackToTop', () => {
  let scrollY: number

  beforeEach(() => {
    const pinia = createPinia()
    setActivePinia(pinia)
    scrollY = 0
    Object.defineProperty(window, 'scrollY', {
      get: () => scrollY,
      configurable: true,
    })
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('is hidden when scroll position is less than 300px', () => {
    scrollY = 100
    const wrapper = mount(BackToTop, {
      global: { plugins: [createPinia()] },
    })
    expect(wrapper.find('button').exists()).toBe(false)
  })

  it('becomes visible when scroll position exceeds 300px', async () => {
    scrollY = 0
    const wrapper = mount(BackToTop, {
      global: { plugins: [createPinia()] },
    })
    expect(wrapper.find('button').exists()).toBe(false)

    scrollY = 400
    window.dispatchEvent(new Event('scroll'))
    await wrapper.vm.$nextTick()

    expect(wrapper.find('button').exists()).toBe(true)
  })

  it('hides when scroll returns below threshold', async () => {
    scrollY = 400
    const wrapper = mount(BackToTop, {
      global: { plugins: [createPinia()] },
    })
    window.dispatchEvent(new Event('scroll'))
    await wrapper.vm.$nextTick()
    expect(wrapper.find('button').exists()).toBe(true)

    scrollY = 50
    window.dispatchEvent(new Event('scroll'))
    await wrapper.vm.$nextTick()
    expect(wrapper.find('button').exists()).toBe(false)
  })

  it('calls window.scrollTo on click', async () => {
    scrollY = 500
    const scrollToMock = vi.fn()
    window.scrollTo = scrollToMock

    const wrapper = mount(BackToTop, {
      global: { plugins: [createPinia()] },
    })
    window.dispatchEvent(new Event('scroll'))
    await wrapper.vm.$nextTick()

    await wrapper.find('button').trigger('click')
    expect(scrollToMock).toHaveBeenCalledWith({ top: 0, behavior: 'smooth' })
  })

  it('has correct aria-label', async () => {
    scrollY = 500
    const wrapper = mount(BackToTop, {
      global: { plugins: [createPinia()] },
    })
    window.dispatchEvent(new Event('scroll'))
    await wrapper.vm.$nextTick()

    const btn = wrapper.find('button')
    expect(btn.attributes('aria-label')).toBeTruthy()
  })

  it('removes scroll listener on unmount', () => {
    const removeEventSpy = vi.spyOn(window, 'removeEventListener')
    const wrapper = mount(BackToTop, {
      global: { plugins: [createPinia()] },
    })
    wrapper.unmount()
    expect(removeEventSpy).toHaveBeenCalledWith('scroll', expect.any(Function))
  })

  describe('safe area inset support (M12)', () => {
    it('uses back-to-top-btn class for safe area positioning', async () => {
      scrollY = 500
      const wrapper = mount(BackToTop, {
        global: { plugins: [createPinia()] },
      })
      window.dispatchEvent(new Event('scroll'))
      await wrapper.vm.$nextTick()

      const btn = wrapper.find('button')
      expect(btn.classes()).toContain('back-to-top-btn')
    })

    it('does not use inline bottom-8 right-8 positioning', async () => {
      scrollY = 500
      const wrapper = mount(BackToTop, {
        global: { plugins: [createPinia()] },
      })
      window.dispatchEvent(new Event('scroll'))
      await wrapper.vm.$nextTick()

      const btn = wrapper.find('button')
      // Should not have hardcoded bottom/right classes since CSS handles it
      expect(btn.classes()).not.toContain('bottom-8')
      expect(btn.classes()).not.toContain('right-8')
    })
  })
})

import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import BaseButton from '../base/BaseButton.vue'

describe('BaseButton', () => {
  describe('rendering', () => {
    it('should render slot content as text', () => {
      const wrapper = mount(BaseButton, {
        slots: {
          default: 'Click Me',
        },
      })
      expect(wrapper.text()).toContain('Click Me')
    })

    it('should render HTML slot content', () => {
      const wrapper = mount(BaseButton, {
        slots: {
          default: '<span class="inner">Label</span>',
        },
      })
      expect(wrapper.find('.inner').exists()).toBe(true)
      expect(wrapper.text()).toContain('Label')
    })

    it('should render as a button element', () => {
      const wrapper = mount(BaseButton, {
        slots: { default: 'Test' },
      })
      expect(wrapper.element.tagName).toBe('BUTTON')
    })
  })

  describe('click handling', () => {
    it('should emit click event when clicked', async () => {
      const wrapper = mount(BaseButton, {
        slots: { default: 'Click' },
      })

      await wrapper.trigger('click')
      expect(wrapper.emitted('click')).toBeTruthy()
    })

    it('should not emit click event when disabled', async () => {
      const wrapper = mount(BaseButton, {
        props: { disabled: true },
        slots: { default: 'Click' },
      })

      await wrapper.trigger('click')
      // Disabled button should not emit click (HTML native behavior)
      expect(wrapper.emitted('click')).toBeFalsy()
    })

    it('should not emit click event when loading', async () => {
      const wrapper = mount(BaseButton, {
        props: { loading: true },
        slots: { default: 'Click' },
      })

      await wrapper.trigger('click')
      expect(wrapper.emitted('click')).toBeFalsy()
    })
  })

  describe('disabled state', () => {
    it('should set disabled attribute when disabled prop is true', () => {
      const wrapper = mount(BaseButton, {
        props: { disabled: true },
        slots: { default: 'Disabled' },
      })

      expect(wrapper.attributes('disabled')).toBeDefined()
    })

    it('should apply opacity class when disabled', () => {
      const wrapper = mount(BaseButton, {
        props: { disabled: true },
        slots: { default: 'Disabled' },
      })

      expect(wrapper.classes()).toContain('opacity-50')
      expect(wrapper.classes()).toContain('cursor-not-allowed')
    })

    it('should not have disabled attribute by default', () => {
      const wrapper = mount(BaseButton, {
        slots: { default: 'Enabled' },
      })

      expect(wrapper.attributes('disabled')).toBeUndefined()
    })
  })

  describe('loading state', () => {
    it('should show loading spinner SVG when loading', () => {
      const wrapper = mount(BaseButton, {
        props: { loading: true },
        slots: { default: 'Loading' },
      })

      expect(wrapper.find('svg.animate-spin').exists()).toBe(true)
    })

    it('should not show loading spinner by default', () => {
      const wrapper = mount(BaseButton, {
        slots: { default: 'Not Loading' },
      })

      expect(wrapper.find('svg.animate-spin').exists()).toBe(false)
    })

    it('should set disabled attribute when loading', () => {
      const wrapper = mount(BaseButton, {
        props: { loading: true },
        slots: { default: 'Loading' },
      })

      expect(wrapper.attributes('disabled')).toBeDefined()
    })

    it('should apply opacity and cursor-not-allowed classes when loading', () => {
      const wrapper = mount(BaseButton, {
        props: { loading: true },
        slots: { default: 'Loading' },
      })

      expect(wrapper.classes()).toContain('opacity-50')
      expect(wrapper.classes()).toContain('cursor-not-allowed')
    })
  })

  describe('variant prop', () => {
    it('should apply primary variant classes by default', () => {
      const wrapper = mount(BaseButton, {
        slots: { default: 'Primary' },
      })

      expect(wrapper.classes()).toContain('bg-brand-600')
      expect(wrapper.classes()).toContain('text-white')
    })

    it('should apply danger variant classes', () => {
      const wrapper = mount(BaseButton, {
        props: { variant: 'danger' },
        slots: { default: 'Danger' },
      })

      expect(wrapper.classes()).toContain('bg-danger-600')
      expect(wrapper.classes()).toContain('text-white')
    })

    it('should apply secondary variant classes', () => {
      const wrapper = mount(BaseButton, {
        props: { variant: 'secondary' },
        slots: { default: 'Secondary' },
      })

      expect(wrapper.classes()).toContain('bg-surface-alt')
      expect(wrapper.classes()).toContain('text-muted')
    })

    it('should apply ghost variant classes', () => {
      const wrapper = mount(BaseButton, {
        props: { variant: 'ghost' },
        slots: { default: 'Ghost' },
      })

      expect(wrapper.classes()).toContain('text-brand-600')
    })
  })

  describe('size prop', () => {
    it('should apply md size classes by default', () => {
      const wrapper = mount(BaseButton, {
        slots: { default: 'Medium' },
      })

      expect(wrapper.classes()).toContain('px-4')
      expect(wrapper.classes()).toContain('py-2.5')
      expect(wrapper.classes()).toContain('text-sm')
      expect(wrapper.classes()).toContain('rounded-lg')
    })

    it('should apply sm size classes', () => {
      const wrapper = mount(BaseButton, {
        props: { size: 'sm' },
        slots: { default: 'Small' },
      })

      expect(wrapper.classes()).toContain('px-3')
      expect(wrapper.classes()).toContain('py-2.5')
      expect(wrapper.classes()).toContain('text-xs')
      expect(wrapper.classes()).toContain('rounded-md')
    })

    it('should apply lg size classes', () => {
      const wrapper = mount(BaseButton, {
        props: { size: 'lg' },
        slots: { default: 'Large' },
      })

      expect(wrapper.classes()).toContain('px-6')
      expect(wrapper.classes()).toContain('py-2.5')
    })

    it('should apply full width size classes', () => {
      const wrapper = mount(BaseButton, {
        props: { size: 'full' },
        slots: { default: 'Full' },
      })

      expect(wrapper.classes()).toContain('w-full')
    })
  })
})

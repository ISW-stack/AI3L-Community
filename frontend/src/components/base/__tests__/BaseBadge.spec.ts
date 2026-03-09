import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import BaseBadge from '../BaseBadge.vue'

describe('BaseBadge', () => {
  describe('rendering', () => {
    it('should render slot content', () => {
      const wrapper = mount(BaseBadge, {
        slots: { default: 'New' },
      })
      expect(wrapper.text()).toContain('New')
    })

    it('should render as a span element', () => {
      const wrapper = mount(BaseBadge, {
        slots: { default: 'Tag' },
      })
      expect(wrapper.element.tagName).toBe('SPAN')
    })
  })

  describe('variant prop', () => {
    it('should apply brand variant classes by default', () => {
      const wrapper = mount(BaseBadge, {
        slots: { default: 'Brand' },
      })
      expect(wrapper.classes()).toContain('bg-brand-100')
      expect(wrapper.classes()).toContain('text-brand-700')
    })

    it('should apply success variant classes', () => {
      const wrapper = mount(BaseBadge, {
        props: { variant: 'success' },
        slots: { default: 'Success' },
      })
      expect(wrapper.classes()).toContain('bg-success-100')
      expect(wrapper.classes()).toContain('text-success-700')
    })

    it('should apply warning variant classes', () => {
      const wrapper = mount(BaseBadge, {
        props: { variant: 'warning' },
        slots: { default: 'Warning' },
      })
      expect(wrapper.classes()).toContain('bg-warning-100')
      expect(wrapper.classes()).toContain('text-warning-700')
    })

    it('should apply danger variant classes', () => {
      const wrapper = mount(BaseBadge, {
        props: { variant: 'danger' },
        slots: { default: 'Danger' },
      })
      expect(wrapper.classes()).toContain('bg-danger-100')
      expect(wrapper.classes()).toContain('text-danger-700')
    })

    it('should apply neutral variant classes', () => {
      const wrapper = mount(BaseBadge, {
        props: { variant: 'neutral' },
        slots: { default: 'Neutral' },
      })
      expect(wrapper.classes()).toContain('bg-gray-100')
      expect(wrapper.classes()).toContain('text-gray-600')
    })

    it('should apply orange variant classes', () => {
      const wrapper = mount(BaseBadge, {
        props: { variant: 'orange' },
        slots: { default: 'Orange' },
      })
      expect(wrapper.classes()).toContain('bg-orange-100')
      expect(wrapper.classes()).toContain('text-orange-700')
    })

    it('should apply purple variant classes', () => {
      const wrapper = mount(BaseBadge, {
        props: { variant: 'purple' },
        slots: { default: 'Purple' },
      })
      expect(wrapper.classes()).toContain('bg-purple-100')
      expect(wrapper.classes()).toContain('text-purple-700')
    })
  })

  describe('size prop', () => {
    it('should apply sm size classes by default', () => {
      const wrapper = mount(BaseBadge, {
        slots: { default: 'Small' },
      })
      expect(wrapper.classes()).toContain('px-2')
      expect(wrapper.classes()).toContain('py-0.5')
    })

    it('should apply md size classes', () => {
      const wrapper = mount(BaseBadge, {
        props: { size: 'md' },
        slots: { default: 'Medium' },
      })
      expect(wrapper.classes()).toContain('px-2.5')
      expect(wrapper.classes()).toContain('py-1')
    })
  })
})

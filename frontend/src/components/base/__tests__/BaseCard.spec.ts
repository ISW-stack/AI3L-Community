import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import BaseCard from '../BaseCard.vue'

describe('BaseCard', () => {
  describe('rendering', () => {
    it('should render slot content', () => {
      const wrapper = mount(BaseCard, {
        slots: { default: '<p>Card content</p>' },
      })
      expect(wrapper.text()).toContain('Card content')
      expect(wrapper.find('p').exists()).toBe(true)
    })

    it('should render as a div element', () => {
      const wrapper = mount(BaseCard, {
        slots: { default: 'Content' },
      })
      expect(wrapper.element.tagName).toBe('DIV')
    })

    it('should always have base classes', () => {
      const wrapper = mount(BaseCard, {
        slots: { default: 'Content' },
      })
      expect(wrapper.classes()).toContain('bg-surface')
      expect(wrapper.classes()).toContain('rounded-lg')
      expect(wrapper.classes()).toContain('shadow')
    })
  })

  describe('hoverable prop', () => {
    it('should not have hover classes by default', () => {
      const wrapper = mount(BaseCard, {
        slots: { default: 'Content' },
      })
      expect(wrapper.classes()).not.toContain('hover:shadow-md')
    })

    it('should have hover classes when hoverable is true', () => {
      const wrapper = mount(BaseCard, {
        props: { hoverable: true },
        slots: { default: 'Content' },
      })
      expect(wrapper.classes()).toContain('hover:shadow-md')
      expect(wrapper.classes()).toContain('transition')
    })
  })

  describe('padding prop', () => {
    it('should apply md padding by default', () => {
      const wrapper = mount(BaseCard, {
        slots: { default: 'Content' },
      })
      expect(wrapper.classes()).toContain('p-5')
    })

    it('should apply no padding when padding is none', () => {
      const wrapper = mount(BaseCard, {
        props: { padding: 'none' },
        slots: { default: 'Content' },
      })
      expect(wrapper.classes()).not.toContain('p-4')
      expect(wrapper.classes()).not.toContain('p-5')
      expect(wrapper.classes()).not.toContain('p-6')
    })

    it('should apply sm padding', () => {
      const wrapper = mount(BaseCard, {
        props: { padding: 'sm' },
        slots: { default: 'Content' },
      })
      expect(wrapper.classes()).toContain('p-4')
    })

    it('should apply lg padding', () => {
      const wrapper = mount(BaseCard, {
        props: { padding: 'lg' },
        slots: { default: 'Content' },
      })
      expect(wrapper.classes()).toContain('p-6')
    })
  })
})

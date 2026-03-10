import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import BaseAlert from '../BaseAlert.vue'

describe('BaseAlert', () => {
  describe('rendering', () => {
    it('should render slot content', () => {
      const wrapper = mount(BaseAlert, {
        slots: { default: 'Something went wrong' },
      })
      expect(wrapper.text()).toContain('Something went wrong')
    })

    it('should have role="alert"', () => {
      const wrapper = mount(BaseAlert, {
        slots: { default: 'Alert' },
      })
      expect(wrapper.attributes('role')).toBe('alert')
    })

    it('should render HTML slot content', () => {
      const wrapper = mount(BaseAlert, {
        slots: { default: '<strong>Bold</strong> text' },
      })
      expect(wrapper.find('strong').exists()).toBe(true)
      expect(wrapper.text()).toContain('Bold text')
    })
  })

  describe('type prop', () => {
    it('should apply info classes by default', () => {
      const wrapper = mount(BaseAlert, {
        slots: { default: 'Info' },
      })
      expect(wrapper.classes()).toContain('bg-info-50')
      expect(wrapper.classes()).toContain('text-info-700')
    })

    it('should apply error classes', () => {
      const wrapper = mount(BaseAlert, {
        props: { type: 'error' },
        slots: { default: 'Error' },
      })
      expect(wrapper.classes()).toContain('bg-danger-50')
      expect(wrapper.classes()).toContain('text-danger-700')
    })

    it('should apply success classes', () => {
      const wrapper = mount(BaseAlert, {
        props: { type: 'success' },
        slots: { default: 'Success' },
      })
      expect(wrapper.classes()).toContain('bg-success-50')
      expect(wrapper.classes()).toContain('text-success-700')
    })

    it('should apply warning classes', () => {
      const wrapper = mount(BaseAlert, {
        props: { type: 'warning' },
        slots: { default: 'Warning' },
      })
      expect(wrapper.classes()).toContain('bg-warning-50')
      expect(wrapper.classes()).toContain('text-warning-700')
    })
  })

  describe('dismissible', () => {
    it('should not show dismiss button by default', () => {
      const wrapper = mount(BaseAlert, {
        slots: { default: 'Alert' },
      })
      expect(wrapper.find('button').exists()).toBe(false)
    })

    it('should show dismiss button when dismissible is true', () => {
      const wrapper = mount(BaseAlert, {
        props: { dismissible: true },
        slots: { default: 'Alert' },
      })
      const btn = wrapper.find('button')
      expect(btn.exists()).toBe(true)
      expect(btn.attributes('aria-label')).toBe('Dismiss')
    })

    it('should emit dismiss event when dismiss button is clicked', async () => {
      const wrapper = mount(BaseAlert, {
        props: { dismissible: true },
        slots: { default: 'Alert' },
      })
      await wrapper.find('button').trigger('click')
      expect(wrapper.emitted('dismiss')).toBeTruthy()
      expect(wrapper.emitted('dismiss')!.length).toBe(1)
    })
  })
})

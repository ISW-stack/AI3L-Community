import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import BaseInput from '../BaseInput.vue'

describe('BaseInput', () => {
  describe('rendering', () => {
    it('should render an input element', () => {
      const wrapper = mount(BaseInput)
      expect(wrapper.find('input').exists()).toBe(true)
    })

    it('should render label when label prop is provided', () => {
      const wrapper = mount(BaseInput, {
        props: { label: 'Username' },
      })
      const label = wrapper.find('label')
      expect(label.exists()).toBe(true)
      expect(label.text()).toBe('Username')
    })

    it('should not render label when label prop is not provided', () => {
      const wrapper = mount(BaseInput)
      expect(wrapper.find('label').exists()).toBe(false)
    })

    it('should generate id from label', () => {
      const wrapper = mount(BaseInput, {
        props: { label: 'First Name' },
      })
      const input = wrapper.find('input')
      expect(input.attributes('id')).toBe('input-first-name')
      expect(wrapper.find('label').attributes('for')).toBe('input-first-name')
    })

    it('should use custom id when provided', () => {
      const wrapper = mount(BaseInput, {
        props: { label: 'Name', id: 'custom-id' },
      })
      expect(wrapper.find('input').attributes('id')).toBe('custom-id')
    })
  })

  describe('v-model', () => {
    it('should display the modelValue', () => {
      const wrapper = mount(BaseInput, {
        props: { modelValue: 'hello' },
      })
      expect((wrapper.find('input').element as HTMLInputElement).value).toBe('hello')
    })

    it('should emit update:modelValue on input', async () => {
      const wrapper = mount(BaseInput, {
        props: { modelValue: '' },
      })
      await wrapper.find('input').setValue('new value')
      expect(wrapper.emitted('update:modelValue')).toBeTruthy()
      expect(wrapper.emitted('update:modelValue')![0]).toEqual(['new value'])
    })
  })

  describe('type prop', () => {
    it('should default to text type', () => {
      const wrapper = mount(BaseInput)
      expect(wrapper.find('input').attributes('type')).toBe('text')
    })

    it('should set the type attribute', () => {
      const wrapper = mount(BaseInput, {
        props: { type: 'password' },
      })
      expect(wrapper.find('input').attributes('type')).toBe('password')
    })
  })

  describe('placeholder', () => {
    it('should set the placeholder attribute', () => {
      const wrapper = mount(BaseInput, {
        props: { placeholder: 'Enter text...' },
      })
      expect(wrapper.find('input').attributes('placeholder')).toBe('Enter text...')
    })
  })

  describe('disabled state', () => {
    it('should not be disabled by default', () => {
      const wrapper = mount(BaseInput)
      expect(wrapper.find('input').attributes('disabled')).toBeUndefined()
    })

    it('should set disabled attribute when disabled is true', () => {
      const wrapper = mount(BaseInput, {
        props: { disabled: true },
      })
      expect(wrapper.find('input').attributes('disabled')).toBeDefined()
    })

    it('should apply disabled styling classes', () => {
      const wrapper = mount(BaseInput, {
        props: { disabled: true },
      })
      const input = wrapper.find('input')
      expect(input.classes()).toContain('bg-surface-alt')
      expect(input.classes()).toContain('cursor-not-allowed')
    })
  })

  describe('maxlength', () => {
    it('should set maxlength attribute', () => {
      const wrapper = mount(BaseInput, {
        props: { maxlength: 50 },
      })
      expect(wrapper.find('input').attributes('maxlength')).toBe('50')
    })
  })

  describe('error state', () => {
    it('should not show error message by default', () => {
      const wrapper = mount(BaseInput)
      expect(wrapper.find('p').exists()).toBe(false)
    })

    it('should show error message when error prop is set', () => {
      const wrapper = mount(BaseInput, {
        props: { error: 'This field is required' },
      })
      const errorEl = wrapper.find('p')
      expect(errorEl.exists()).toBe(true)
      expect(errorEl.text()).toBe('This field is required')
      expect(errorEl.classes()).toContain('text-danger-600')
    })

    it('should apply error border classes when error is set', () => {
      const wrapper = mount(BaseInput, {
        props: { error: 'Error' },
      })
      expect(wrapper.find('input').classes()).toContain('border-danger-500')
    })

    it('should apply normal border classes when no error', () => {
      const wrapper = mount(BaseInput)
      expect(wrapper.find('input').classes()).toContain('border-border')
    })
  })

  describe('iOS zoom prevention', () => {
    it('should have text-base class to prevent iOS auto-zoom', () => {
      const wrapper = mount(BaseInput)
      expect(wrapper.find('input').classes()).toContain('text-base')
    })

    it('should use md:text-sm breakpoint instead of sm:text-sm', () => {
      const wrapper = mount(BaseInput)
      const input = wrapper.find('input')
      expect(input.classes()).toContain('md:text-sm')
      expect(input.classes()).not.toContain('sm:text-sm')
    })
  })
})

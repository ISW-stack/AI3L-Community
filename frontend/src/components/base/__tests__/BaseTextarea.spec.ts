import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import BaseTextarea from '../BaseTextarea.vue'

describe('BaseTextarea', () => {
  describe('rendering', () => {
    it('should render a textarea element', () => {
      const wrapper = mount(BaseTextarea)
      expect(wrapper.find('textarea').exists()).toBe(true)
    })

    it('should render label when label prop is provided', () => {
      const wrapper = mount(BaseTextarea, {
        props: { label: 'Description' },
      })
      const label = wrapper.find('label')
      expect(label.exists()).toBe(true)
      expect(label.text()).toBe('Description')
    })

    it('should not render label when label prop is not provided', () => {
      const wrapper = mount(BaseTextarea)
      expect(wrapper.find('label').exists()).toBe(false)
    })

    it('should generate id from label', () => {
      const wrapper = mount(BaseTextarea, {
        props: { label: 'First Name' },
      })
      const textarea = wrapper.find('textarea')
      expect(textarea.attributes('id')).toBe('textarea-first-name')
      expect(wrapper.find('label').attributes('for')).toBe('textarea-first-name')
    })

    it('should use custom id when provided', () => {
      const wrapper = mount(BaseTextarea, {
        props: { label: 'Name', id: 'custom-id' },
      })
      expect(wrapper.find('textarea').attributes('id')).toBe('custom-id')
    })
  })

  describe('v-model', () => {
    it('should display the modelValue', () => {
      const wrapper = mount(BaseTextarea, {
        props: { modelValue: 'hello' },
      })
      expect((wrapper.find('textarea').element as HTMLTextAreaElement).value).toBe('hello')
    })

    it('should emit update:modelValue on input', async () => {
      const wrapper = mount(BaseTextarea, {
        props: { modelValue: '' },
      })
      await wrapper.find('textarea').setValue('new value')
      expect(wrapper.emitted('update:modelValue')).toBeTruthy()
      expect(wrapper.emitted('update:modelValue')![0]).toEqual(['new value'])
    })
  })

  describe('placeholder', () => {
    it('should set the placeholder attribute', () => {
      const wrapper = mount(BaseTextarea, {
        props: { placeholder: 'Enter text...' },
      })
      expect(wrapper.find('textarea').attributes('placeholder')).toBe('Enter text...')
    })
  })

  describe('disabled state', () => {
    it('should not be disabled by default', () => {
      const wrapper = mount(BaseTextarea)
      expect(wrapper.find('textarea').attributes('disabled')).toBeUndefined()
    })

    it('should set disabled attribute when disabled is true', () => {
      const wrapper = mount(BaseTextarea, {
        props: { disabled: true },
      })
      expect(wrapper.find('textarea').attributes('disabled')).toBeDefined()
    })

    it('should apply disabled styling classes', () => {
      const wrapper = mount(BaseTextarea, {
        props: { disabled: true },
      })
      const textarea = wrapper.find('textarea')
      expect(textarea.classes()).toContain('bg-surface-alt')
      expect(textarea.classes()).toContain('cursor-not-allowed')
    })
  })

  describe('maxlength', () => {
    it('should set maxlength attribute', () => {
      const wrapper = mount(BaseTextarea, {
        props: { maxlength: 500 },
      })
      expect(wrapper.find('textarea').attributes('maxlength')).toBe('500')
    })
  })

  describe('rows', () => {
    it('should default to 3 rows', () => {
      const wrapper = mount(BaseTextarea)
      expect(wrapper.find('textarea').attributes('rows')).toBe('3')
    })

    it('should use custom rows when provided', () => {
      const wrapper = mount(BaseTextarea, {
        props: { rows: 6 },
      })
      expect(wrapper.find('textarea').attributes('rows')).toBe('6')
    })
  })

  describe('error state', () => {
    it('should not show error message by default', () => {
      const wrapper = mount(BaseTextarea)
      expect(wrapper.find('p').exists()).toBe(false)
    })

    it('should show error message when error prop is set', () => {
      const wrapper = mount(BaseTextarea, {
        props: { error: 'This field is required' },
      })
      const errorEl = wrapper.find('p')
      expect(errorEl.exists()).toBe(true)
      expect(errorEl.text()).toBe('This field is required')
      expect(errorEl.classes()).toContain('text-danger-600')
    })

    it('should apply error border classes when error is set', () => {
      const wrapper = mount(BaseTextarea, {
        props: { error: 'Error' },
      })
      expect(wrapper.find('textarea').classes()).toContain('border-danger-500')
    })

    it('should apply normal border classes when no error', () => {
      const wrapper = mount(BaseTextarea)
      expect(wrapper.find('textarea').classes()).toContain('border-border')
    })
  })

  describe('iOS zoom prevention', () => {
    it('should have text-base class to prevent iOS auto-zoom', () => {
      const wrapper = mount(BaseTextarea)
      expect(wrapper.find('textarea').classes()).toContain('text-base')
    })
  })
})

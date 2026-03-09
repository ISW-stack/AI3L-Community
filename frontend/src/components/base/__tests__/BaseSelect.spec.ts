import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import BaseSelect from '../BaseSelect.vue'

const defaultOptions = [
  { value: 'a', label: 'Option A' },
  { value: 'b', label: 'Option B' },
  { value: 'c', label: 'Option C' },
]

describe('BaseSelect', () => {
  describe('rendering', () => {
    it('should render a select element', () => {
      const wrapper = mount(BaseSelect, {
        props: { options: defaultOptions },
      })
      expect(wrapper.find('select').exists()).toBe(true)
    })

    it('should render all options', () => {
      const wrapper = mount(BaseSelect, {
        props: { options: defaultOptions },
      })
      const options = wrapper.findAll('option')
      expect(options.length).toBe(3)
      expect(options[0].text()).toBe('Option A')
      expect(options[1].text()).toBe('Option B')
      expect(options[2].text()).toBe('Option C')
    })

    it('should render placeholder option when provided', () => {
      const wrapper = mount(BaseSelect, {
        props: { options: defaultOptions, placeholder: 'Select one...' },
      })
      const options = wrapper.findAll('option')
      expect(options.length).toBe(4)
      expect(options[0].text()).toBe('Select one...')
      expect(options[0].attributes('disabled')).toBeDefined()
    })
  })

  describe('label', () => {
    it('should render label when label prop is provided', () => {
      const wrapper = mount(BaseSelect, {
        props: { options: defaultOptions, label: 'Category' },
      })
      const label = wrapper.find('label')
      expect(label.exists()).toBe(true)
      expect(label.text()).toBe('Category')
    })

    it('should not render label when label prop is not provided', () => {
      const wrapper = mount(BaseSelect, {
        props: { options: defaultOptions },
      })
      expect(wrapper.find('label').exists()).toBe(false)
    })

    it('should generate id from label', () => {
      const wrapper = mount(BaseSelect, {
        props: { options: defaultOptions, label: 'My Select' },
      })
      expect(wrapper.find('select').attributes('id')).toBe('select-my-select')
      expect(wrapper.find('label').attributes('for')).toBe('select-my-select')
    })

    it('should use custom id when provided', () => {
      const wrapper = mount(BaseSelect, {
        props: { options: defaultOptions, label: 'Test', id: 'custom-select' },
      })
      expect(wrapper.find('select').attributes('id')).toBe('custom-select')
    })
  })

  describe('v-model', () => {
    it('should display the selected modelValue', () => {
      const wrapper = mount(BaseSelect, {
        props: { options: defaultOptions, modelValue: 'b' },
      })
      expect((wrapper.find('select').element as HTMLSelectElement).value).toBe('b')
    })

    it('should emit update:modelValue on change', async () => {
      const wrapper = mount(BaseSelect, {
        props: { options: defaultOptions, modelValue: 'a' },
      })
      await wrapper.find('select').setValue('c')
      expect(wrapper.emitted('update:modelValue')).toBeTruthy()
      expect(wrapper.emitted('update:modelValue')![0]).toEqual(['c'])
    })
  })

  describe('disabled state', () => {
    it('should not be disabled by default', () => {
      const wrapper = mount(BaseSelect, {
        props: { options: defaultOptions },
      })
      expect(wrapper.find('select').attributes('disabled')).toBeUndefined()
    })

    it('should set disabled attribute when disabled is true', () => {
      const wrapper = mount(BaseSelect, {
        props: { options: defaultOptions, disabled: true },
      })
      expect(wrapper.find('select').attributes('disabled')).toBeDefined()
    })

    it('should apply disabled styling classes', () => {
      const wrapper = mount(BaseSelect, {
        props: { options: defaultOptions, disabled: true },
      })
      expect(wrapper.find('select').classes()).toContain('bg-surface-alt')
      expect(wrapper.find('select').classes()).toContain('cursor-not-allowed')
    })
  })

  describe('error state', () => {
    it('should not show error message by default', () => {
      const wrapper = mount(BaseSelect, {
        props: { options: defaultOptions },
      })
      expect(wrapper.find('p').exists()).toBe(false)
    })

    it('should show error message when error prop is set', () => {
      const wrapper = mount(BaseSelect, {
        props: { options: defaultOptions, error: 'Required field' },
      })
      const errorEl = wrapper.find('p')
      expect(errorEl.exists()).toBe(true)
      expect(errorEl.text()).toBe('Required field')
      expect(errorEl.classes()).toContain('text-danger-600')
    })

    it('should apply error border classes when error is set', () => {
      const wrapper = mount(BaseSelect, {
        props: { options: defaultOptions, error: 'Error' },
      })
      expect(wrapper.find('select').classes()).toContain('border-danger-500')
    })
  })

  describe('slot override', () => {
    it('should allow custom options via default slot', () => {
      const wrapper = mount(BaseSelect, {
        props: { options: [] },
        slots: {
          default: '<option value="x">Custom X</option><option value="y">Custom Y</option>',
        },
      })
      const options = wrapper.findAll('option')
      expect(options.length).toBe(2)
      expect(options[0].text()).toBe('Custom X')
    })
  })
})

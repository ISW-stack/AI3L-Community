import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import BaseAvatar from '../BaseAvatar.vue'

describe('BaseAvatar', () => {
  describe('image rendering', () => {
    it('should render an image when src is provided', () => {
      const wrapper = mount(BaseAvatar, {
        props: { src: 'https://example.com/avatar.jpg', name: 'Alice' },
      })
      const img = wrapper.find('img')
      expect(img.exists()).toBe(true)
      expect(img.attributes('src')).toBe('https://example.com/avatar.jpg')
      expect(img.attributes('alt')).toBe('Alice')
    })

    it('should not render an image when src is null', () => {
      const wrapper = mount(BaseAvatar, {
        props: { src: null, name: 'Bob' },
      })
      expect(wrapper.find('img').exists()).toBe(false)
    })

    it('should not render an image when src is not provided', () => {
      const wrapper = mount(BaseAvatar, {
        props: { name: 'Bob' },
      })
      expect(wrapper.find('img').exists()).toBe(false)
    })
  })

  describe('initials fallback', () => {
    it('should show first letter uppercase when no src', () => {
      const wrapper = mount(BaseAvatar, {
        props: { name: 'alice' },
      })
      expect(wrapper.find('span').text()).toBe('A')
    })

    it('should show ? when name is empty string', () => {
      const wrapper = mount(BaseAvatar, {
        props: { name: '' },
      })
      expect(wrapper.find('span').text()).toBe('?')
    })
  })

  describe('size prop', () => {
    it('should apply sm size classes by default', () => {
      const wrapper = mount(BaseAvatar, {
        props: { name: 'Test' },
      })
      expect(wrapper.classes()).toContain('w-8')
      expect(wrapper.classes()).toContain('h-8')
    })

    it('should apply md size classes', () => {
      const wrapper = mount(BaseAvatar, {
        props: { name: 'Test', size: 'md' },
      })
      expect(wrapper.classes()).toContain('w-10')
      expect(wrapper.classes()).toContain('h-10')
    })

    it('should apply lg size classes', () => {
      const wrapper = mount(BaseAvatar, {
        props: { name: 'Test', size: 'lg' },
      })
      expect(wrapper.classes()).toContain('w-20')
      expect(wrapper.classes()).toContain('h-20')
    })
  })
})

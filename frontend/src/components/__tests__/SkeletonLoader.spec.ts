import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import SkeletonLoader from '../SkeletonLoader.vue'

describe('SkeletonLoader', () => {
  describe('default (text) variant', () => {
    it('should render 4 skeleton lines by default', () => {
      const wrapper = mount(SkeletonLoader)
      const lines = wrapper.findAll('.h-4')
      expect(lines.length).toBe(4)
    })

    it('should render custom number of lines', () => {
      const wrapper = mount(SkeletonLoader, {
        props: { lines: 2 },
      })
      const lines = wrapper.findAll('.h-4')
      expect(lines.length).toBe(2)
    })

    it('should have animate-pulse class', () => {
      const wrapper = mount(SkeletonLoader)
      expect(wrapper.classes()).toContain('animate-pulse')
    })

    it('should make last line shorter (w-2/3)', () => {
      const wrapper = mount(SkeletonLoader, {
        props: { lines: 3 },
      })
      const lines = wrapper.findAll('.h-4')
      expect(lines[2].classes()).toContain('w-2/3')
      expect(lines[0].classes()).toContain('w-full')
    })
  })

  describe('card variant', () => {
    it('should render card skeletons', () => {
      const wrapper = mount(SkeletonLoader, {
        props: { variant: 'card', lines: 2 },
      })
      const cards = wrapper.findAll('.bg-surface')
      expect(cards.length).toBe(2)
    })

    it('should default to 3 cards when lines not specified', () => {
      const wrapper = mount(SkeletonLoader, {
        props: { variant: 'card' },
      })
      const cards = wrapper.findAll('.bg-surface')
      expect(cards.length).toBe(3)
    })
  })

  describe('list variant', () => {
    it('should render list item skeletons with avatars', () => {
      const wrapper = mount(SkeletonLoader, {
        props: { variant: 'list', lines: 3 },
      })
      const avatars = wrapper.findAll('.rounded-full')
      expect(avatars.length).toBe(3)
    })

    it('should default to 5 items when lines not specified', () => {
      const wrapper = mount(SkeletonLoader, {
        props: { variant: 'list' },
      })
      const avatars = wrapper.findAll('.rounded-full')
      expect(avatars.length).toBe(5)
    })
  })
})

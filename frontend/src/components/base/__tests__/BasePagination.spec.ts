import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import BasePagination from '../BasePagination.vue'

describe('BasePagination', () => {
  describe('visibility', () => {
    it('should not render when totalPages is 1', () => {
      const wrapper = mount(BasePagination, {
        props: { currentPage: 1, totalPages: 1 },
      })
      expect(wrapper.find('div').exists()).toBe(false)
    })

    it('should not render when totalPages is 0', () => {
      const wrapper = mount(BasePagination, {
        props: { currentPage: 1, totalPages: 0 },
      })
      expect(wrapper.find('div').exists()).toBe(false)
    })

    it('should render when totalPages is greater than 1', () => {
      const wrapper = mount(BasePagination, {
        props: { currentPage: 1, totalPages: 3 },
      })
      expect(wrapper.find('div').exists()).toBe(true)
    })
  })

  describe('page buttons', () => {
    it('should render all page numbers when total <= maxVisible', () => {
      const wrapper = mount(BasePagination, {
        props: { currentPage: 1, totalPages: 3 },
      })
      const buttons = wrapper.findAll('button')
      // prev + 3 pages + next = 5 buttons
      expect(buttons.length).toBe(5)
      expect(buttons[1].text()).toBe('1')
      expect(buttons[2].text()).toBe('2')
      expect(buttons[3].text()).toBe('3')
    })

    it('should highlight the current page', () => {
      const wrapper = mount(BasePagination, {
        props: { currentPage: 2, totalPages: 3 },
      })
      const buttons = wrapper.findAll('button')
      // Page 2 button (index 2) should have active class
      expect(buttons[2].classes()).toContain('bg-brand-600')
      expect(buttons[2].classes()).toContain('text-white')
    })

    it('should not highlight non-current pages', () => {
      const wrapper = mount(BasePagination, {
        props: { currentPage: 2, totalPages: 3 },
      })
      const buttons = wrapper.findAll('button')
      // Page 1 button (index 1) should not have active class
      expect(buttons[1].classes()).not.toContain('bg-brand-600')
    })
  })

  describe('prev/next buttons', () => {
    it('should disable prev button on first page', () => {
      const wrapper = mount(BasePagination, {
        props: { currentPage: 1, totalPages: 5 },
      })
      const prevBtn = wrapper.findAll('button')[0]
      expect(prevBtn.attributes('disabled')).toBeDefined()
    })

    it('should disable next button on last page', () => {
      const wrapper = mount(BasePagination, {
        props: { currentPage: 5, totalPages: 5 },
      })
      const buttons = wrapper.findAll('button')
      const nextBtn = buttons[buttons.length - 1]
      expect(nextBtn.attributes('disabled')).toBeDefined()
    })

    it('should enable prev button when not on first page', () => {
      const wrapper = mount(BasePagination, {
        props: { currentPage: 3, totalPages: 5 },
      })
      const prevBtn = wrapper.findAll('button')[0]
      expect(prevBtn.attributes('disabled')).toBeUndefined()
    })

    it('should enable next button when not on last page', () => {
      const wrapper = mount(BasePagination, {
        props: { currentPage: 3, totalPages: 5 },
      })
      const buttons = wrapper.findAll('button')
      const nextBtn = buttons[buttons.length - 1]
      expect(nextBtn.attributes('disabled')).toBeUndefined()
    })
  })

  describe('page change events', () => {
    it('should emit update:currentPage with previous page on prev click', async () => {
      const wrapper = mount(BasePagination, {
        props: { currentPage: 3, totalPages: 5 },
      })
      await wrapper.findAll('button')[0].trigger('click')
      expect(wrapper.emitted('update:currentPage')).toBeTruthy()
      expect(wrapper.emitted('update:currentPage')![0]).toEqual([2])
    })

    it('should emit update:currentPage with next page on next click', async () => {
      const wrapper = mount(BasePagination, {
        props: { currentPage: 3, totalPages: 5 },
      })
      const buttons = wrapper.findAll('button')
      await buttons[buttons.length - 1].trigger('click')
      expect(wrapper.emitted('update:currentPage')).toBeTruthy()
      expect(wrapper.emitted('update:currentPage')![0]).toEqual([4])
    })

    it('should emit update:currentPage with page number on page button click', async () => {
      const wrapper = mount(BasePagination, {
        props: { currentPage: 1, totalPages: 3 },
      })
      // Click page 2 (index 2)
      await wrapper.findAll('button')[2].trigger('click')
      expect(wrapper.emitted('update:currentPage')).toBeTruthy()
      expect(wrapper.emitted('update:currentPage')![0]).toEqual([2])
    })
  })

  describe('maxVisible', () => {
    it('should limit visible pages based on maxVisible prop', () => {
      const wrapper = mount(BasePagination, {
        props: { currentPage: 5, totalPages: 10, maxVisible: 3 },
      })
      const buttons = wrapper.findAll('button')
      // prev + 3 pages + next = 5
      expect(buttons.length).toBe(5)
    })

    it('should show correct page range centered around current page', () => {
      const wrapper = mount(BasePagination, {
        props: { currentPage: 5, totalPages: 10, maxVisible: 3 },
      })
      const buttons = wrapper.findAll('button')
      expect(buttons[1].text()).toBe('4')
      expect(buttons[2].text()).toBe('5')
      expect(buttons[3].text()).toBe('6')
    })
  })
})

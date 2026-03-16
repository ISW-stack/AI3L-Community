import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import BasePagination from '../BasePagination.vue'

describe('BasePagination', () => {
  describe('visibility', () => {
    it('should not render when totalPages is 1', () => {
      const wrapper = mount(BasePagination, {
        props: { currentPage: 1, totalPages: 1 },
      })
      expect(wrapper.find('nav').exists()).toBe(false)
    })

    it('should not render when totalPages is 0', () => {
      const wrapper = mount(BasePagination, {
        props: { currentPage: 1, totalPages: 0 },
      })
      expect(wrapper.find('nav').exists()).toBe(false)
    })

    it('should render when totalPages is greater than 1', () => {
      const wrapper = mount(BasePagination, {
        props: { currentPage: 1, totalPages: 3 },
      })
      expect(wrapper.find('nav').exists()).toBe(true)
    })
  })

  describe('page buttons (desktop)', () => {
    it('should render all page numbers when total <= maxVisible', () => {
      const wrapper = mount(BasePagination, {
        props: { currentPage: 1, totalPages: 3 },
      })
      const desktopPag = wrapper.find('[data-testid="desktop-pagination"]')
      const buttons = desktopPag.findAll('button')
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
      const desktopPag = wrapper.find('[data-testid="desktop-pagination"]')
      const buttons = desktopPag.findAll('button')
      // Page 2 button (index 2) should have active class
      expect(buttons[2].classes()).toContain('bg-brand-600')
      expect(buttons[2].classes()).toContain('text-white')
    })

    it('should not highlight non-current pages', () => {
      const wrapper = mount(BasePagination, {
        props: { currentPage: 2, totalPages: 3 },
      })
      const desktopPag = wrapper.find('[data-testid="desktop-pagination"]')
      const buttons = desktopPag.findAll('button')
      // Page 1 button (index 1) should not have active class
      expect(buttons[1].classes()).not.toContain('bg-brand-600')
    })
  })

  describe('prev/next buttons', () => {
    it('should disable prev button on first page', () => {
      const wrapper = mount(BasePagination, {
        props: { currentPage: 1, totalPages: 5 },
      })
      const desktopPag = wrapper.find('[data-testid="desktop-pagination"]')
      const prevBtn = desktopPag.findAll('button')[0]
      expect(prevBtn.attributes('disabled')).toBeDefined()
    })

    it('should disable next button on last page', () => {
      const wrapper = mount(BasePagination, {
        props: { currentPage: 5, totalPages: 5 },
      })
      const desktopPag = wrapper.find('[data-testid="desktop-pagination"]')
      const buttons = desktopPag.findAll('button')
      const nextBtn = buttons[buttons.length - 1]
      expect(nextBtn.attributes('disabled')).toBeDefined()
    })

    it('should enable prev button when not on first page', () => {
      const wrapper = mount(BasePagination, {
        props: { currentPage: 3, totalPages: 5 },
      })
      const desktopPag = wrapper.find('[data-testid="desktop-pagination"]')
      const prevBtn = desktopPag.findAll('button')[0]
      expect(prevBtn.attributes('disabled')).toBeUndefined()
    })

    it('should enable next button when not on last page', () => {
      const wrapper = mount(BasePagination, {
        props: { currentPage: 3, totalPages: 5 },
      })
      const desktopPag = wrapper.find('[data-testid="desktop-pagination"]')
      const buttons = desktopPag.findAll('button')
      const nextBtn = buttons[buttons.length - 1]
      expect(nextBtn.attributes('disabled')).toBeUndefined()
    })
  })

  describe('page change events', () => {
    it('should emit update:currentPage with previous page on prev click', async () => {
      const wrapper = mount(BasePagination, {
        props: { currentPage: 3, totalPages: 5 },
      })
      const desktopPag = wrapper.find('[data-testid="desktop-pagination"]')
      await desktopPag.findAll('button')[0].trigger('click')
      expect(wrapper.emitted('update:currentPage')).toBeTruthy()
      expect(wrapper.emitted('update:currentPage')![0]).toEqual([2])
    })

    it('should emit update:currentPage with next page on next click', async () => {
      const wrapper = mount(BasePagination, {
        props: { currentPage: 3, totalPages: 5 },
      })
      const desktopPag = wrapper.find('[data-testid="desktop-pagination"]')
      const buttons = desktopPag.findAll('button')
      await buttons[buttons.length - 1].trigger('click')
      expect(wrapper.emitted('update:currentPage')).toBeTruthy()
      expect(wrapper.emitted('update:currentPage')![0]).toEqual([4])
    })

    it('should emit update:currentPage with page number on page button click', async () => {
      const wrapper = mount(BasePagination, {
        props: { currentPage: 1, totalPages: 3 },
      })
      const desktopPag = wrapper.find('[data-testid="desktop-pagination"]')
      // Click page 2 (index 2)
      await desktopPag.findAll('button')[2].trigger('click')
      expect(wrapper.emitted('update:currentPage')).toBeTruthy()
      expect(wrapper.emitted('update:currentPage')![0]).toEqual([2])
    })
  })

  describe('maxVisible', () => {
    it('should limit visible pages based on maxVisible prop', () => {
      const wrapper = mount(BasePagination, {
        props: { currentPage: 5, totalPages: 10, maxVisible: 3 },
      })
      const desktopPag = wrapper.find('[data-testid="desktop-pagination"]')
      const buttons = desktopPag.findAll('button')
      // prev + 3 pages + next = 5
      expect(buttons.length).toBe(5)
    })

    it('should show correct page range centered around current page', () => {
      const wrapper = mount(BasePagination, {
        props: { currentPage: 5, totalPages: 10, maxVisible: 3 },
      })
      const desktopPag = wrapper.find('[data-testid="desktop-pagination"]')
      const buttons = desktopPag.findAll('button')
      expect(buttons[1].text()).toBe('4')
      expect(buttons[2].text()).toBe('5')
      expect(buttons[3].text()).toBe('6')
    })
  })

  describe('result count text', () => {
    it('should show "Showing X-Y of Z" when pageSize and total are provided', () => {
      const wrapper = mount(BasePagination, {
        props: { currentPage: 1, totalPages: 3, pageSize: 10, total: 25 },
      })
      const resultCount = wrapper.find('[data-testid="result-count"]')
      expect(resultCount.exists()).toBe(true)
      // Should contain the numbers 1, 10, 25 in the text
      expect(resultCount.text()).toContain('1')
      expect(resultCount.text()).toContain('10')
      expect(resultCount.text()).toContain('25')
    })

    it('should not show result count when pageSize is 0', () => {
      const wrapper = mount(BasePagination, {
        props: { currentPage: 1, totalPages: 3 },
      })
      expect(wrapper.find('[data-testid="result-count"]').exists()).toBe(false)
    })

    it('should not show result count when total is 0', () => {
      const wrapper = mount(BasePagination, {
        props: { currentPage: 1, totalPages: 3, pageSize: 10, total: 0 },
      })
      expect(wrapper.find('[data-testid="result-count"]').exists()).toBe(false)
    })

    it('should cap end at total on the last page', () => {
      const wrapper = mount(BasePagination, {
        props: { currentPage: 3, totalPages: 3, pageSize: 10, total: 25 },
      })
      const resultCount = wrapper.find('[data-testid="result-count"]')
      expect(resultCount.exists()).toBe(true)
      // Page 3: start=21, end=min(30,25)=25
      expect(resultCount.text()).toContain('21')
      expect(resultCount.text()).toContain('25')
    })

    it('should show correct range for page 1', () => {
      const wrapper = mount(BasePagination, {
        props: { currentPage: 1, totalPages: 2, pageSize: 20, total: 30 },
      })
      const resultCount = wrapper.find('[data-testid="result-count"]')
      // Page 1: start=1, end=20
      expect(resultCount.text()).toContain('1')
      expect(resultCount.text()).toContain('20')
      expect(resultCount.text()).toContain('30')
    })
  })

  describe('mobile pagination', () => {
    it('should render mobile pagination with prev/next and page info', () => {
      const wrapper = mount(BasePagination, {
        props: { currentPage: 2, totalPages: 5 },
      })
      const mobilePag = wrapper.find('[data-testid="mobile-pagination"]')
      expect(mobilePag.exists()).toBe(true)
      // Should show "Page 2 of 5" text
      expect(mobilePag.text()).toContain('2')
      expect(mobilePag.text()).toContain('5')
    })

    it('should have prev and next buttons in mobile view', () => {
      const wrapper = mount(BasePagination, {
        props: { currentPage: 2, totalPages: 5 },
      })
      const mobilePag = wrapper.find('[data-testid="mobile-pagination"]')
      const buttons = mobilePag.findAll('button')
      expect(buttons.length).toBe(2) // prev + next only
    })

    it('should disable prev on first page in mobile view', () => {
      const wrapper = mount(BasePagination, {
        props: { currentPage: 1, totalPages: 5 },
      })
      const mobilePag = wrapper.find('[data-testid="mobile-pagination"]')
      const prevBtn = mobilePag.findAll('button')[0]
      expect(prevBtn.attributes('disabled')).toBeDefined()
    })

    it('should disable next on last page in mobile view', () => {
      const wrapper = mount(BasePagination, {
        props: { currentPage: 5, totalPages: 5 },
      })
      const mobilePag = wrapper.find('[data-testid="mobile-pagination"]')
      const buttons = mobilePag.findAll('button')
      const nextBtn = buttons[buttons.length - 1]
      expect(nextBtn.attributes('disabled')).toBeDefined()
    })

    it('should emit page change from mobile prev button', async () => {
      const wrapper = mount(BasePagination, {
        props: { currentPage: 3, totalPages: 5 },
      })
      const mobilePag = wrapper.find('[data-testid="mobile-pagination"]')
      await mobilePag.findAll('button')[0].trigger('click')
      expect(wrapper.emitted('update:currentPage')![0]).toEqual([2])
    })

    it('should emit page change from mobile next button', async () => {
      const wrapper = mount(BasePagination, {
        props: { currentPage: 3, totalPages: 5 },
      })
      const mobilePag = wrapper.find('[data-testid="mobile-pagination"]')
      const buttons = mobilePag.findAll('button')
      await buttons[buttons.length - 1].trigger('click')
      expect(wrapper.emitted('update:currentPage')![0]).toEqual([4])
    })

    it('should not render page number buttons in mobile view', () => {
      const wrapper = mount(BasePagination, {
        props: { currentPage: 3, totalPages: 10 },
      })
      const mobilePag = wrapper.find('[data-testid="mobile-pagination"]')
      // Only prev + next, no numbered page buttons
      const buttons = mobilePag.findAll('button')
      expect(buttons.length).toBe(2)
    })
  })

  describe('touch targets', () => {
    it('should have py-2 class on desktop pagination buttons', () => {
      const wrapper = mount(BasePagination, {
        props: { currentPage: 2, totalPages: 5 },
      })
      const desktopPag = wrapper.find('[data-testid="desktop-pagination"]')
      const prevBtn = desktopPag.findAll('button')[0]
      expect(prevBtn.classes()).toContain('py-2')
    })

    it('should have py-2 class on mobile pagination buttons', () => {
      const wrapper = mount(BasePagination, {
        props: { currentPage: 2, totalPages: 5 },
      })
      const mobilePag = wrapper.find('[data-testid="mobile-pagination"]')
      const prevBtn = mobilePag.findAll('button')[0]
      expect(prevBtn.classes()).toContain('py-2')
    })
  })

  describe('disabled cursor style', () => {
    it('should have cursor-not-allowed on disabled desktop prev button', () => {
      const wrapper = mount(BasePagination, {
        props: { currentPage: 1, totalPages: 5 },
      })
      const desktopPag = wrapper.find('[data-testid="desktop-pagination"]')
      const prevBtn = desktopPag.findAll('button')[0]
      expect(prevBtn.classes()).toContain('disabled:cursor-not-allowed')
    })

    it('should have cursor-not-allowed on disabled desktop next button', () => {
      const wrapper = mount(BasePagination, {
        props: { currentPage: 5, totalPages: 5 },
      })
      const desktopPag = wrapper.find('[data-testid="desktop-pagination"]')
      const buttons = desktopPag.findAll('button')
      const nextBtn = buttons[buttons.length - 1]
      expect(nextBtn.classes()).toContain('disabled:cursor-not-allowed')
    })

    it('should have cursor-not-allowed on disabled mobile prev button', () => {
      const wrapper = mount(BasePagination, {
        props: { currentPage: 1, totalPages: 5 },
      })
      const mobilePag = wrapper.find('[data-testid="mobile-pagination"]')
      const prevBtn = mobilePag.findAll('button')[0]
      expect(prevBtn.classes()).toContain('disabled:cursor-not-allowed')
    })

    it('should have cursor-not-allowed on disabled mobile next button', () => {
      const wrapper = mount(BasePagination, {
        props: { currentPage: 5, totalPages: 5 },
      })
      const mobilePag = wrapper.find('[data-testid="mobile-pagination"]')
      const buttons = mobilePag.findAll('button')
      const nextBtn = buttons[buttons.length - 1]
      expect(nextBtn.classes()).toContain('disabled:cursor-not-allowed')
    })
  })

  describe('single page edge case', () => {
    it('should not render at all when only one page exists', () => {
      const wrapper = mount(BasePagination, {
        props: { currentPage: 1, totalPages: 1, pageSize: 20, total: 5 },
      })
      expect(wrapper.find('nav').exists()).toBe(false)
    })
  })
})

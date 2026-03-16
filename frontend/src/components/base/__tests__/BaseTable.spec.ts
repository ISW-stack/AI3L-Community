import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import BaseTable from '../BaseTable.vue'

const columns = [
  { key: 'name', label: 'Name' },
  { key: 'email', label: 'Email' },
  { key: 'role', label: 'Role', class: 'w-32' },
]

const rows = [
  { name: 'Alice', email: 'alice@example.com', role: 'Admin' },
  { name: 'Bob', email: 'bob@example.com', role: 'Member' },
]

describe('BaseTable', () => {
  describe('header rendering', () => {
    it('should render column headers', () => {
      const wrapper = mount(BaseTable, {
        props: { columns, rows },
      })
      const headers = wrapper.findAll('th')
      expect(headers.length).toBe(3)
      expect(headers[0].text()).toBe('Name')
      expect(headers[1].text()).toBe('Email')
      expect(headers[2].text()).toBe('Role')
    })

    it('should apply custom class to column header', () => {
      const wrapper = mount(BaseTable, {
        props: { columns, rows },
      })
      const headers = wrapper.findAll('th')
      expect(headers[2].classes()).toContain('w-32')
    })
  })

  describe('row rendering', () => {
    it('should render all rows', () => {
      const wrapper = mount(BaseTable, {
        props: { columns, rows },
      })
      const dataRows = wrapper.find('tbody').findAll('tr')
      expect(dataRows.length).toBe(2)
    })

    it('should render cell values', () => {
      const wrapper = mount(BaseTable, {
        props: { columns, rows },
      })
      const cells = wrapper.find('tbody').findAll('td')
      expect(cells[0].text()).toBe('Alice')
      expect(cells[1].text()).toBe('alice@example.com')
      expect(cells[2].text()).toBe('Admin')
      expect(cells[3].text()).toBe('Bob')
    })
  })

  describe('loading state', () => {
    it('should show loading text when loading is true', () => {
      const wrapper = mount(BaseTable, {
        props: { columns, rows: [], loading: true },
      })
      expect(wrapper.text()).toContain('Loading...')
    })

    it('should set correct colspan on loading row', () => {
      const wrapper = mount(BaseTable, {
        props: { columns, rows: [], loading: true },
      })
      const td = wrapper.find('tbody td')
      expect(td.attributes('colspan')).toBe('3')
    })
  })

  describe('empty state', () => {
    it('should show default empty text when rows is empty', () => {
      const wrapper = mount(BaseTable, {
        props: { columns, rows: [] },
      })
      expect(wrapper.text()).toContain('No data')
    })

    it('should show custom empty text when provided', () => {
      const wrapper = mount(BaseTable, {
        props: { columns, rows: [], emptyText: 'No users found' },
      })
      expect(wrapper.text()).toContain('No users found')
    })

    it('should not show empty text when rows exist', () => {
      const wrapper = mount(BaseTable, {
        props: { columns, rows },
      })
      expect(wrapper.text()).not.toContain('No data')
    })

    it('should not show empty text when loading', () => {
      const wrapper = mount(BaseTable, {
        props: { columns, rows: [], loading: true },
      })
      expect(wrapper.text()).not.toContain('No data')
    })
  })

  describe('scoped slots', () => {
    it('should allow custom cell rendering via scoped slot', () => {
      const wrapper = mount(BaseTable, {
        props: { columns, rows },
        slots: {
          name: '<template #name="{ row, value }"><strong>{{ value }}</strong></template>',
        },
      })
      const strong = wrapper.find('tbody strong')
      expect(strong.exists()).toBe(true)
      expect(strong.text()).toBe('Alice')
    })
  })

  describe('mobile scroll container', () => {
    it('should have a scroll container with overflow-x-auto', () => {
      const wrapper = mount(BaseTable, {
        props: { columns, rows },
      })
      const scrollContainer = wrapper.find('.table-scroll-container')
      expect(scrollContainer.exists()).toBe(true)
      expect(scrollContainer.classes()).toContain('overflow-x-auto')
    })

    it('should have touch scrolling style on scroll container', () => {
      const wrapper = mount(BaseTable, {
        props: { columns, rows },
      })
      const scrollContainer = wrapper.find('.table-scroll-container')
      expect(scrollContainer.attributes('style')).toContain('-webkit-overflow-scrolling: touch')
    })

    it('should have a scroll hint gradient element', () => {
      const wrapper = mount(BaseTable, {
        props: { columns, rows },
      })
      const scrollHint = wrapper.find('.scroll-hint')
      expect(scrollHint.exists()).toBe(true)
      expect(scrollHint.classes()).toContain('pointer-events-none')
      expect(scrollHint.classes()).toContain('md:hidden')
      expect(scrollHint.attributes('aria-hidden')).toBe('true')
    })

    it('should have a relative outer container for gradient positioning', () => {
      const wrapper = mount(BaseTable, {
        props: { columns, rows },
      })
      const outerDiv = wrapper.find('div')
      expect(outerDiv.classes()).toContain('relative')
    })
  })
})

import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import BaseTable from '../base/BaseTable.vue'

const defaultColumns = [
  { key: 'name', label: 'Name' },
  { key: 'email', label: 'Email' },
]

const defaultRows = [
  { name: 'Alice', email: 'alice@test.com' },
  { name: 'Bob', email: 'bob@test.com' },
]

function mountTable(props: Record<string, unknown> = {}) {
  return mount(BaseTable, {
    props: {
      columns: defaultColumns,
      rows: defaultRows,
      ...props,
    },
  })
}

describe('BaseTable', () => {
  it('renders column headers', () => {
    const wrapper = mountTable()
    const headers = wrapper.findAll('th')
    expect(headers).toHaveLength(2)
    expect(headers[0].text()).toBe('Name')
    expect(headers[1].text()).toBe('Email')
  })

  it('renders rows', () => {
    const wrapper = mountTable()
    const rows = wrapper.findAll('tbody tr')
    expect(rows).toHaveLength(2)
    expect(rows[0].text()).toContain('Alice')
    expect(rows[1].text()).toContain('Bob')
  })

  it('renders translated loading text via i18n when loading is true', () => {
    const wrapper = mountTable({ rows: [], loading: true })
    // The i18n key common.loading resolves to "Loading..." in the en locale
    expect(wrapper.text()).toContain('Loading...')
  })

  it('renders translated "No data" text via i18n when rows are empty and not loading', () => {
    const wrapper = mountTable({ rows: [], loading: false })
    // The i18n key common.noData resolves to "No data" in the en locale
    expect(wrapper.text()).toContain('No data')
  })

  it('renders custom emptyText when provided', () => {
    const wrapper = mountTable({ rows: [], loading: false, emptyText: 'Nothing here' })
    expect(wrapper.text()).toContain('Nothing here')
    expect(wrapper.text()).not.toContain('No data')
  })

  it('has a scrollable container with overflow-x-auto for mobile', () => {
    const wrapper = mountTable()
    const scrollContainer = wrapper.find('.table-scroll-container')
    expect(scrollContainer.exists()).toBe(true)
    expect(scrollContainer.classes()).toContain('overflow-x-auto')
  })

  it('has a scroll hint gradient visible on mobile', () => {
    const wrapper = mountTable()
    const scrollHint = wrapper.find('.scroll-hint')
    expect(scrollHint.exists()).toBe(true)
    expect(scrollHint.classes()).toContain('md:hidden')
  })
})

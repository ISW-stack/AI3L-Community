import { describe, it, expect, afterEach } from 'vitest'
import { mount } from '@vue/test-utils'
import BasePagination from '../BasePagination.vue'
import BaseModal from '../BaseModal.vue'

describe('BasePagination accessibility', () => {
  it('renders a nav element with aria-label="Pagination"', () => {
    const wrapper = mount(BasePagination, {
      props: { currentPage: 2, totalPages: 5 },
    })
    const nav = wrapper.find('nav')
    expect(nav.exists()).toBe(true)
    expect(nav.attributes('aria-label')).toBe('Pagination')
  })

  it('sets aria-current="page" on the active page button', () => {
    const wrapper = mount(BasePagination, {
      props: { currentPage: 3, totalPages: 5 },
    })
    const buttons = wrapper.findAll('[data-testid="desktop-pagination"] button')
    // buttons: prev, 1, 2, 3, 4, 5, next
    const page3Btn = buttons.find((b) => b.text() === '3')
    expect(page3Btn).toBeTruthy()
    expect(page3Btn!.attributes('aria-current')).toBe('page')
  })

  it('does not set aria-current on non-active page buttons', () => {
    const wrapper = mount(BasePagination, {
      props: { currentPage: 3, totalPages: 5 },
    })
    const buttons = wrapper.findAll('[data-testid="desktop-pagination"] button')
    const page1Btn = buttons.find((b) => b.text() === '1')
    expect(page1Btn).toBeTruthy()
    expect(page1Btn!.attributes('aria-current')).toBeUndefined()
  })
})

describe('BaseModal accessibility', () => {
  let wrapper: ReturnType<typeof mount> | null = null

  afterEach(() => {
    wrapper?.unmount()
    wrapper = null
    document.body.style.overflow = ''
    document.body.querySelectorAll('[role="dialog"]').forEach((el) => el.parentElement?.remove())
  })

  function getDialog() {
    return document.body.querySelector('[role="dialog"]')
  }

  it('sets aria-labelledby when title is provided', () => {
    wrapper = mount(BaseModal, {
      props: { modelValue: true, title: 'Test Title' },
      slots: { default: 'Content' },
      attachTo: document.body,
    })
    const dialog = getDialog()
    expect(dialog?.getAttribute('aria-labelledby')).toMatch(/^modal-title-/)
    expect(dialog?.getAttribute('aria-label')).toBeNull()
  })

  it('sets aria-label="Dialog" as fallback when no title is provided', () => {
    wrapper = mount(BaseModal, {
      props: { modelValue: true },
      slots: { default: 'Content' },
      attachTo: document.body,
    })
    const dialog = getDialog()
    expect(dialog?.getAttribute('aria-labelledby')).toBeNull()
    expect(dialog?.getAttribute('aria-label')).toBe('Dialog')
  })
})

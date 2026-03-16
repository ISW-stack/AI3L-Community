import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import BaseBreadcrumb from '../base/BaseBreadcrumb.vue'

function createTestRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: { template: '<div />' } },
      { path: '/admin', component: { template: '<div />' } },
      { path: '/admin/users', component: { template: '<div />' } },
    ],
  })
}

function mountBreadcrumb(items: Array<{ label: string; to?: string }>) {
  const router = createTestRouter()
  return mount(BaseBreadcrumb, {
    props: { items },
    global: {
      plugins: [router],
    },
  })
}

describe('BaseBreadcrumb', () => {
  describe('rendering items', () => {
    it('should render all item labels', () => {
      const wrapper = mountBreadcrumb([
        { label: 'Home', to: '/' },
        { label: 'Admin', to: '/admin' },
        { label: 'Users' },
      ])

      expect(wrapper.text()).toContain('Home')
      expect(wrapper.text()).toContain('Admin')
      expect(wrapper.text()).toContain('Users')
    })

    it('should render items with links as router-link elements', () => {
      const wrapper = mountBreadcrumb([
        { label: 'Home', to: '/' },
        { label: 'Admin', to: '/admin' },
        { label: 'Users' },
      ])

      const links = wrapper.findAll('a')
      expect(links.length).toBe(2)
      expect(links[0].text()).toBe('Home')
      expect(links[1].text()).toBe('Admin')
    })

    it('should render the last item as plain text, not a link', () => {
      const wrapper = mountBreadcrumb([{ label: 'Home', to: '/' }, { label: 'Users' }])

      const spans = wrapper.findAll('span')
      // The last item should be a span (plain text), not a link
      const lastItemSpan = spans.filter((s) => s.text() === 'Users')
      expect(lastItemSpan.length).toBeGreaterThan(0)

      // Verify it is not inside an <a> tag
      const links = wrapper.findAll('a')
      const usersLink = links.filter((l) => l.text() === 'Users')
      expect(usersLink.length).toBe(0)
    })

    it('should render the last item as span even when it has a to prop', () => {
      const wrapper = mountBreadcrumb([
        { label: 'Home', to: '/' },
        { label: 'Users', to: '/admin/users' },
      ])

      // Last item should still be plain text
      const links = wrapper.findAll('a')
      expect(links.length).toBe(1)
      expect(links[0].text()).toBe('Home')
    })
  })

  describe('separator icons', () => {
    it('should render separator icons between items', () => {
      const wrapper = mountBreadcrumb([
        { label: 'Home', to: '/' },
        { label: 'Admin', to: '/admin' },
        { label: 'Users' },
      ])

      const separators = wrapper.findAll('.lucide-chevron-right')
      // 3 items = 2 separators
      expect(separators.length).toBe(2)
    })

    it('should not render separator before the first item', () => {
      const wrapper = mountBreadcrumb([{ label: 'Home', to: '/' }])

      const separators = wrapper.findAll('.lucide-chevron-right')
      expect(separators.length).toBe(0)
    })

    it('should render one separator for two items', () => {
      const wrapper = mountBreadcrumb([{ label: 'Home', to: '/' }, { label: 'Users' }])

      const separators = wrapper.findAll('.lucide-chevron-right')
      expect(separators.length).toBe(1)
    })
  })

  describe('aria-current', () => {
    it('should have aria-current="page" on the last breadcrumb item', () => {
      const wrapper = mountBreadcrumb([
        { label: 'Home', to: '/' },
        { label: 'Admin', to: '/admin' },
        { label: 'Users' },
      ])

      const spans = wrapper.findAll('span')
      const lastSpan = spans.filter((s) => s.text() === 'Users')
      expect(lastSpan.length).toBeGreaterThan(0)
      expect(lastSpan[0].attributes('aria-current')).toBe('page')
    })

    it('should not have aria-current on non-last items', () => {
      const wrapper = mountBreadcrumb([{ label: 'Home', to: '/' }, { label: 'Users' }])

      const links = wrapper.findAll('a')
      for (const link of links) {
        expect(link.attributes('aria-current')).toBeUndefined()
      }
    })
  })

  describe('styling', () => {
    it('should have mb-4 class for bottom margin', () => {
      const wrapper = mountBreadcrumb([{ label: 'Home', to: '/' }])

      expect(wrapper.find('nav').classes()).toContain('mb-4')
    })

    it('should have text-sm class', () => {
      const wrapper = mountBreadcrumb([{ label: 'Home', to: '/' }])

      expect(wrapper.find('nav').classes()).toContain('text-sm')
    })

    it('should have breadcrumb aria label', () => {
      const wrapper = mountBreadcrumb([{ label: 'Home', to: '/' }])

      expect(wrapper.find('nav').attributes('aria-label')).toBe('Breadcrumb')
    })
  })
})

import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import AboutView from '../AboutView.vue'

function createTestRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/about', component: AboutView }],
  })
}

function mountAbout() {
  const router = createTestRouter()
  const wrapper = mount(AboutView, {
    global: { plugins: [router] },
  })
  return wrapper
}

describe('AboutView', () => {
  it('renders the Platform Contributors heading', () => {
    const wrapper = mountAbout()
    expect(wrapper.text()).toContain('Platform Contributors')
  })

  it('renders a card for each contributor', () => {
    const wrapper = mountAbout()
    const cards = wrapper.findAll('.bg-surface')
    expect(cards.length).toBe(2)
  })

  it('displays contributor names', () => {
    const wrapper = mountAbout()
    expect(wrapper.text()).toContain('Isaries')
    expect(wrapper.text()).toContain('SW9526')
  })

  it('displays contributor roles', () => {
    const wrapper = mountAbout()
    expect(wrapper.text()).toContain('Project Lead & Full-Stack Developer')
    expect(wrapper.text()).toContain('Frontend Contributor')
  })

  it('renders GitHub links with correct hrefs', () => {
    const wrapper = mountAbout()
    const links = wrapper.findAll('a[target="_blank"]')
    const hrefs = links.map((l) => l.attributes('href'))
    expect(hrefs).toContain('https://github.com/Isaries')
    expect(hrefs).toContain('https://github.com/SW9526')
  })

  it('renders the About this Project section', () => {
    const wrapper = mountAbout()
    expect(wrapper.text()).toContain('About this Project')
  })
})

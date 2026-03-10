import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import NotFoundView from '../NotFoundView.vue'

vi.mock('@/composables/api', () => ({
  default: { get: vi.fn(), post: vi.fn() },
}))

vi.mock('@/constants', () => ({
  HEARTBEAT_INTERVAL_MS: 30000,
}))

function createStubs() {
  return {
    BaseButton: {
      template: '<button><slot /></button>',
      props: ['size'],
    },
    FileQuestion: { template: '<span class="icon-file-question" />' },
  }
}

describe('NotFoundView', () => {
  it('renders 404 text', () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/', component: { template: '<div />' } },
        { path: '/:pathMatch(.*)*', component: NotFoundView },
      ],
    })

    const wrapper = mount(NotFoundView, {
      global: { plugins: [pinia, router], stubs: createStubs() },
    })

    expect(wrapper.text()).toContain('404')
  })

  it('renders "Page not found" message', () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: '/', component: { template: '<div />' } }],
    })

    const wrapper = mount(NotFoundView, {
      global: { plugins: [pinia, router], stubs: createStubs() },
    })

    expect(wrapper.text()).toContain('Page not found')
  })

  it('has a link back to home', () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: '/', component: { template: '<div />' } }],
    })

    const wrapper = mount(NotFoundView, {
      global: { plugins: [pinia, router], stubs: createStubs() },
    })

    const link = wrapper.find('a')
    expect(link.exists()).toBe(true)
    expect(link.attributes('href')).toBe('/')
  })

  it('has Back to Home button text', () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: '/', component: { template: '<div />' } }],
    })

    const wrapper = mount(NotFoundView, {
      global: { plugins: [pinia, router], stubs: createStubs() },
    })

    expect(wrapper.text()).toContain('Back to Home')
  })

  it('renders the page with centered layout', () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: '/', component: { template: '<div />' } }],
    })

    const wrapper = mount(NotFoundView, {
      global: { plugins: [pinia, router], stubs: createStubs() },
    })

    expect(wrapper.find('.text-center').exists()).toBe(true)
  })
})

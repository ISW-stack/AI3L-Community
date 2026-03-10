import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import EmptyState from '../EmptyState.vue'

vi.mock('lucide-vue-next', () => ({
  Inbox: { name: 'Inbox', template: '<svg data-testid="inbox-icon" />' },
}))

vi.mock('@/components/base/BaseButton.vue', () => ({
  default: { template: '<button><slot /></button>' },
}))

function createTestRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: { template: '<div />' } },
      { path: '/create', component: { template: '<div />' } },
    ],
  })
}

describe('EmptyState', () => {
  function mountEmptyState(props: Record<string, unknown>) {
    const router = createTestRouter()
    return mount(EmptyState, {
      props: { message: 'No items found', ...props },
      global: { plugins: [router] },
    })
  }

  describe('rendering', () => {
    it('should render the message', () => {
      const wrapper = mountEmptyState({})
      expect(wrapper.text()).toContain('No items found')
    })

    it('should render the Inbox icon', () => {
      const wrapper = mountEmptyState({})
      expect(wrapper.find('[data-testid="inbox-icon"]').exists()).toBe(true)
    })

    it('should render optional title when provided', () => {
      const wrapper = mountEmptyState({ title: 'Nothing here' })
      expect(wrapper.find('h3').exists()).toBe(true)
      expect(wrapper.text()).toContain('Nothing here')
    })

    it('should not render title when not provided', () => {
      const wrapper = mountEmptyState({})
      expect(wrapper.find('h3').exists()).toBe(false)
    })
  })

  describe('action button', () => {
    it('should render action button when actionLabel and actionTo are provided', () => {
      const wrapper = mountEmptyState({
        actionLabel: 'Create New',
        actionTo: '/create',
      })
      expect(wrapper.text()).toContain('Create New')
      expect(wrapper.find('a[href="/create"]').exists()).toBe(true)
    })

    it('should not render action button when actionLabel is not provided', () => {
      const wrapper = mountEmptyState({ actionTo: '/create' })
      expect(wrapper.find('a').exists()).toBe(false)
    })

    it('should not render action button when actionTo is not provided', () => {
      const wrapper = mountEmptyState({ actionLabel: 'Create' })
      expect(wrapper.find('a').exists()).toBe(false)
    })
  })
})

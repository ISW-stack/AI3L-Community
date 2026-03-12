import { describe, it, expect, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import ToastNotification from '../ToastNotification.vue'
import { useToastStore } from '@/stores/toast'

describe('ToastNotification', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  function mountToast() {
    return mount(ToastNotification)
  }

  describe('rendering', () => {
    it('should render the container with aria-live', () => {
      const wrapper = mountToast()
      expect(wrapper.find('[aria-live="assertive"]').exists()).toBe(true)
    })

    it('should render no toasts when store is empty', () => {
      const wrapper = mountToast()
      expect(wrapper.findAll('[role="alert"]').length).toBe(0)
    })

    it('should render toasts from the store', async () => {
      const store = useToastStore()
      store.show('Hello World', 'info')
      const wrapper = mountToast()
      expect(wrapper.findAll('[role="alert"]').length).toBe(1)
      expect(wrapper.text()).toContain('Hello World')
    })

    it('should render multiple toasts', () => {
      const store = useToastStore()
      store.show('First', 'info')
      store.show('Second', 'error')
      const wrapper = mountToast()
      expect(wrapper.findAll('[role="alert"]').length).toBe(2)
      expect(wrapper.text()).toContain('First')
      expect(wrapper.text()).toContain('Second')
    })
  })

  describe('type classes', () => {
    it('should apply info type classes', () => {
      const store = useToastStore()
      store.show('Info toast', 'info')
      const wrapper = mountToast()
      const toast = wrapper.find('[role="alert"]')
      expect(toast.classes()).toContain('bg-info-50')
      expect(toast.classes()).toContain('text-info-700')
    })

    it('should apply error type classes', () => {
      const store = useToastStore()
      store.show('Error toast', 'error')
      const wrapper = mountToast()
      const toast = wrapper.find('[role="alert"]')
      expect(toast.classes()).toContain('bg-danger-50')
      expect(toast.classes()).toContain('text-danger-700')
    })

    it('should apply success type classes', () => {
      const store = useToastStore()
      store.show('Success toast', 'success')
      const wrapper = mountToast()
      const toast = wrapper.find('[role="alert"]')
      expect(toast.classes()).toContain('bg-success-50')
      expect(toast.classes()).toContain('text-success-700')
    })

    it('should apply warning type classes', () => {
      const store = useToastStore()
      store.show('Warning toast', 'warning')
      const wrapper = mountToast()
      const toast = wrapper.find('[role="alert"]')
      expect(toast.classes()).toContain('bg-warning-50')
      expect(toast.classes()).toContain('text-warning-700')
    })
  })

  describe('mobile positioning', () => {
    it('should have bottom-4 class for mobile positioning', () => {
      const wrapper = mountToast()
      const container = wrapper.find('[aria-live="assertive"]')
      expect(container.classes()).toContain('bottom-4')
    })
  })

  describe('dismiss', () => {
    it('should render dismiss button for each toast', () => {
      const store = useToastStore()
      store.show('Test', 'info')
      const wrapper = mountToast()
      const dismissBtn = wrapper.find('button[aria-label="Dismiss notification"]')
      expect(dismissBtn.exists()).toBe(true)
    })

    it('should remove toast when dismiss button is clicked', async () => {
      const store = useToastStore()
      store.show('Dismissable', 'info')
      const wrapper = mountToast()

      expect(wrapper.findAll('[role="alert"]').length).toBe(1)
      await wrapper.find('button[aria-label="Dismiss notification"]').trigger('click')
      expect(wrapper.findAll('[role="alert"]').length).toBe(0)
    })
  })
})

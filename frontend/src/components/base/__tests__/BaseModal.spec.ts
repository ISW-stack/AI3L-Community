import { describe, it, expect, afterEach } from 'vitest'
import { mount } from '@vue/test-utils'
import BaseModal from '../BaseModal.vue'

describe('BaseModal', () => {
  let wrapper: ReturnType<typeof mount> | null = null

  afterEach(() => {
    wrapper?.unmount()
    wrapper = null
    document.body.style.overflow = ''
    // Clean up any leftover teleported content
    document.body.querySelectorAll('[role="dialog"]').forEach((el) => el.parentElement?.remove())
  })

  function mountModal(props: Record<string, unknown> = {}, slots: Record<string, string> = {}) {
    wrapper = mount(BaseModal, {
      props: { modelValue: true, ...props },
      slots: { default: 'Modal content', ...slots },
      attachTo: document.body,
    })
    return wrapper
  }

  function getDialog() {
    return document.body.querySelector('[role="dialog"]')
  }

  function getPanel() {
    return getDialog()?.querySelector('.bg-surface')
  }

  describe('visibility', () => {
    it('should render modal content when modelValue is true', () => {
      mountModal()
      expect(document.body.textContent).toContain('Modal content')
    })

    it('should not render modal content when modelValue is false', () => {
      wrapper = mount(BaseModal, {
        props: { modelValue: false },
        slots: { default: 'Hidden content' },
        attachTo: document.body,
      })
      expect(getDialog()).toBeNull()
    })
  })

  describe('title', () => {
    it('should render title when title prop is provided', () => {
      mountModal({ title: 'Confirm Action' })
      expect(document.body.textContent).toContain('Confirm Action')
    })

    it('should set aria-labelledby when title is provided', () => {
      mountModal({ title: 'Test Title' })
      expect(getDialog()?.getAttribute('aria-labelledby')).toMatch(/^modal-title-/)
    })

    it('should not set aria-labelledby when no title', () => {
      mountModal()
      expect(getDialog()?.getAttribute('aria-labelledby')).toBeNull()
    })
  })

  describe('close behavior', () => {
    it('should emit update:modelValue false when close button is clicked', async () => {
      const w = mountModal({ title: 'Test' })
      const closeBtn = document.body.querySelector('button[aria-label="Close"]') as HTMLElement
      expect(closeBtn).not.toBeNull()
      closeBtn.click()
      expect(w.emitted('update:modelValue')).toBeTruthy()
      expect(w.emitted('update:modelValue')![0]).toEqual([false])
    })

    it('should emit update:modelValue false when overlay is clicked', async () => {
      const w = mountModal()
      const overlay = getDialog() as HTMLElement
      overlay.click()
      expect(w.emitted('update:modelValue')).toBeTruthy()
      expect(w.emitted('update:modelValue')![0]).toEqual([false])
    })

    it('should emit update:modelValue false on Escape key', async () => {
      // Mount with false first, then switch to true so the watcher fires
      // and registers the keydown listener
      wrapper = mount(BaseModal, {
        props: { modelValue: false },
        slots: { default: 'Modal content' },
        attachTo: document.body,
      })
      await wrapper.setProps({ modelValue: true })
      await wrapper.vm.$nextTick()
      await wrapper.vm.$nextTick()
      document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
      expect(wrapper.emitted('update:modelValue')).toBeTruthy()
      expect(wrapper.emitted('update:modelValue')![0]).toEqual([false])
    })
  })

  describe('persistent mode', () => {
    it('should not show close button when persistent and no title', () => {
      mountModal({ persistent: true })
      // With persistent=true and no title, the header div is hidden
      const closeBtn = getPanel()?.querySelector('button[aria-label="Close"]')
      expect(closeBtn).toBeNull()
    })

    it('should not close on overlay click when persistent', async () => {
      const w = mountModal({ persistent: true })
      const overlay = getDialog() as HTMLElement
      overlay.click()
      expect(w.emitted('update:modelValue')).toBeFalsy()
    })

    it('should not close on Escape when persistent', async () => {
      const w = mountModal({ persistent: true })
      await w.vm.$nextTick()
      await w.vm.$nextTick()
      document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
      expect(w.emitted('update:modelValue')).toBeFalsy()
    })
  })

  describe('size prop', () => {
    it('should apply md size class by default', () => {
      mountModal()
      expect(getPanel()?.classList.contains('max-w-md')).toBe(true)
    })

    it('should apply sm size class', () => {
      mountModal({ size: 'sm' })
      expect(getPanel()?.classList.contains('max-w-sm')).toBe(true)
    })

    it('should apply lg size class', () => {
      mountModal({ size: 'lg' })
      expect(getPanel()?.classList.contains('max-w-lg')).toBe(true)
    })

    it('should apply xl size class', () => {
      mountModal({ size: 'xl' })
      expect(getPanel()?.classList.contains('max-w-2xl')).toBe(true)
    })
  })

  describe('slots', () => {
    it('should render default slot content', () => {
      mountModal({}, { default: '<p>Body text</p>' })
      expect(document.body.textContent).toContain('Body text')
    })

    it('should render footer slot when provided', () => {
      mountModal({}, { footer: '<button>Save</button>' })
      expect(document.body.textContent).toContain('Save')
    })
  })

  describe('accessibility', () => {
    it('should have aria-modal="true"', () => {
      mountModal()
      expect(getDialog()?.getAttribute('aria-modal')).toBe('true')
    })
  })

  describe('viewport-safe max-width', () => {
    it('should have max-w-[calc(100vw-2rem)] class on the modal panel', () => {
      mountModal()
      expect(getPanel()?.classList.contains('max-w-[calc(100vw-2rem)]')).toBe(true)
    })
  })

  describe('persistent backdrop click', () => {
    it('does not close on backdrop click when persistent is true', () => {
      const w = mountModal({ persistent: true })
      const overlay = getDialog() as HTMLElement
      overlay.click()
      expect(w.emitted('update:modelValue')).toBeFalsy()
    })
  })

  describe('mobile padding', () => {
    it('should have p-4 class for compact mobile padding', () => {
      mountModal()
      expect(getPanel()?.classList.contains('p-4')).toBe(true)
    })

    it('should have close button with adequate touch target padding', () => {
      mountModal({ title: 'Test' })
      const closeBtn = getPanel()?.querySelector('button[aria-label="Close"]')
      expect(closeBtn?.classList.contains('p-2.5')).toBe(true)
      expect(closeBtn?.classList.contains('min-w-[44px]')).toBe(true)
      expect(closeBtn?.classList.contains('min-h-[44px]')).toBe(true)
    })
  })
})

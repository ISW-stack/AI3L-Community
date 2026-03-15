import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import DangerZone from '../DangerZone.vue'

function createStubs() {
  return {
    BaseCard: { template: '<div class="base-card"><slot /></div>', props: ['padding'] },
    BaseButton: {
      template:
        '<button :disabled="$attrs.disabled" :type="$attrs.type || \'button\'" @click="$emit(\'click\')"><slot /></button>',
      props: ['loading', 'variant', 'size'],
    },
    BaseAlert: { template: '<div class="base-alert"><slot /></div>', props: ['type'] },
    BaseInput: {
      template:
        '<input class="base-input" :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
      props: ['modelValue', 'label', 'placeholder'],
      emits: ['update:modelValue'],
    },
    BaseModal: {
      template: '<div class="base-modal" v-if="modelValue"><slot /><slot name="footer" /></div>',
      props: ['modelValue', 'title', 'size'],
    },
  }
}

function mountDangerZone(props: Partial<Record<string, unknown>> = {}) {
  const pinia = createPinia()
  setActivePinia(pinia)
  return mount(DangerZone, {
    props: {
      deletingAccount: false,
      ...props,
    },
    global: { plugins: [pinia], stubs: createStubs() },
  })
}

describe('DangerZone', () => {
  describe('rendering', () => {
    it('renders danger zone title', () => {
      const wrapper = mountDangerZone()
      expect(wrapper.text()).toContain('Danger Zone')
    })

    it('renders warning alert', () => {
      const wrapper = mountDangerZone()
      expect(wrapper.find('.base-alert').exists()).toBe(true)
    })

    it('renders delete account button', () => {
      const wrapper = mountDangerZone()
      const btn = wrapper.findAll('button').find((b) => b.text().includes('Delete My Account'))
      expect(btn).toBeTruthy()
    })

    it('renders description text', () => {
      const wrapper = mountDangerZone()
      expect(wrapper.text()).toContain('Permanently delete your account')
    })
  })

  describe('confirmation flow', () => {
    it('shows confirmation modal when delete button clicked', async () => {
      const wrapper = mountDangerZone()
      const deleteBtn = wrapper
        .findAll('button')
        .find((b) => b.text().includes('Delete My Account'))
      await deleteBtn!.trigger('click')
      await nextTick()

      expect(wrapper.find('.base-modal').exists()).toBe(true)
    })

    it('disables confirm button until DELETE is typed', async () => {
      const wrapper = mountDangerZone()
      const vm = wrapper.vm as any

      // Open modal
      vm.showDeleteConfirm = true
      await nextTick()

      // Find the confirm delete button - it should be disabled
      const confirmBtn = wrapper.findAll('button').find((b) => b.text().includes('Delete Account'))
      expect(confirmBtn).toBeTruthy()
      expect(confirmBtn!.attributes('disabled')).toBeDefined()
    })

    it('enables confirm button when DELETE is typed', async () => {
      const wrapper = mountDangerZone()
      const vm = wrapper.vm as any

      vm.showDeleteConfirm = true
      vm.deleteConfirmText = 'DELETE'
      await nextTick()

      const confirmBtn = wrapper.findAll('button').find((b) => b.text().includes('Delete Account'))
      expect(confirmBtn).toBeTruthy()
      expect(confirmBtn!.attributes('disabled')).toBeUndefined()
    })

    it('emits delete-account when confirm button clicked', async () => {
      const wrapper = mountDangerZone()
      const vm = wrapper.vm as any

      vm.showDeleteConfirm = true
      vm.deleteConfirmText = 'DELETE'
      await nextTick()

      const confirmBtn = wrapper.findAll('button').find((b) => b.text().includes('Delete Account'))
      await confirmBtn!.trigger('click')
      expect(wrapper.emitted('delete-account')).toBeTruthy()
    })

    it('closes modal when cancel button clicked', async () => {
      const wrapper = mountDangerZone()
      const vm = wrapper.vm as any

      vm.showDeleteConfirm = true
      await nextTick()

      const cancelBtn = wrapper.findAll('button').find((b) => b.text().includes('Cancel'))
      expect(cancelBtn).toBeTruthy()
      await cancelBtn!.trigger('click')
      await nextTick()

      expect(vm.showDeleteConfirm).toBe(false)
    })

    it('clears deleteConfirmText when modal is closed', async () => {
      const wrapper = mountDangerZone()
      const vm = wrapper.vm as any

      // Open modal and type DELETE
      vm.showDeleteConfirm = true
      vm.deleteConfirmText = 'DELETE'
      await nextTick()

      // Close modal
      vm.showDeleteConfirm = false
      await nextTick()

      // Text should be cleared by watcher
      expect(vm.deleteConfirmText).toBe('')
    })
  })

  describe('expose', () => {
    it('exposes showDeleteConfirm and deleteConfirmText', () => {
      const wrapper = mountDangerZone()
      const vm = wrapper.vm as any

      expect(vm.showDeleteConfirm).toBeDefined()
      expect(vm.deleteConfirmText).toBeDefined()
      expect(vm.closeDeleteConfirm).toBeDefined()
    })
  })
})

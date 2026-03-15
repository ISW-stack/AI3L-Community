import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import PasswordChangeForm from '../PasswordChangeForm.vue'

vi.mock('lucide-vue-next', () => ({
  Eye: { template: '<span class="icon-eye" />' },
  EyeOff: { template: '<span class="icon-eye-off" />' },
  Copy: { template: '<span class="icon-copy" />' },
  Check: { template: '<span class="icon-check" />' },
}))

function createStubs() {
  return {
    BaseCard: { template: '<div class="base-card"><slot /></div>', props: ['padding'] },
    BaseButton: {
      template:
        '<button :disabled="$attrs.disabled" :type="$attrs.type || \'button\'" @click="$emit(\'click\')"><slot /></button>',
      props: ['loading', 'variant', 'size', 'type'],
    },
    BaseAlert: { template: '<div class="base-alert"><slot /></div>', props: ['type'] },
    BaseInput: {
      template:
        '<input class="base-input" :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
      props: ['modelValue', 'label', 'type', 'disabled'],
      emits: ['update:modelValue'],
    },
  }
}

function mountForm(props: Partial<Record<string, unknown>> = {}) {
  const pinia = createPinia()
  setActivePinia(pinia)
  return mount(PasswordChangeForm, {
    props: {
      currentPassword: '',
      newPassword: '',
      confirmPassword: '',
      passwordMessage: '',
      passwordError: false,
      changingPassword: false,
      generatedCode: '',
      generatingCode: false,
      codeCopied: false,
      'onUpdate:currentPassword': () => {},
      'onUpdate:newPassword': () => {},
      'onUpdate:confirmPassword': () => {},
      ...props,
    },
    global: { plugins: [pinia], stubs: createStubs() },
  })
}

describe('PasswordChangeForm', () => {
  describe('rendering', () => {
    it('renders change password title', () => {
      const wrapper = mountForm()
      expect(wrapper.text()).toContain('Change Password')
    })

    it('renders three password fields', () => {
      const wrapper = mountForm()
      const inputs = wrapper.findAll('.base-input')
      // current, new, confirm = 3
      expect(inputs.length).toBeGreaterThanOrEqual(3)
    })

    it('renders change password submit button', () => {
      const wrapper = mountForm()
      const btn = wrapper.findAll('button').find((b) => b.text().includes('Change Password'))
      expect(btn).toBeTruthy()
    })

    it('renders invite codes section', () => {
      const wrapper = mountForm()
      expect(wrapper.text()).toContain('Invite Codes')
      expect(wrapper.text()).toContain('Generate Invite Code')
    })
  })

  describe('password message', () => {
    it('shows success message when passwordMessage is set and passwordError is false', () => {
      const wrapper = mountForm({
        passwordMessage: 'Password changed!',
        passwordError: false,
      })
      expect(wrapper.text()).toContain('Password changed!')
      const alert = wrapper.find('.base-alert')
      expect(alert.exists()).toBe(true)
    })

    it('shows error message when passwordError is true', () => {
      const wrapper = mountForm({
        passwordMessage: 'Wrong password',
        passwordError: true,
      })
      expect(wrapper.text()).toContain('Wrong password')
    })

    it('does not show message when passwordMessage is empty', () => {
      const wrapper = mountForm({ passwordMessage: '' })
      const alerts = wrapper.findAll('.base-alert')
      expect(alerts.length).toBe(0)
    })
  })

  describe('submit button disabled state', () => {
    it('disables submit when all passwords are empty', () => {
      const wrapper = mountForm()
      const submitBtn = wrapper.findAll('button').find((b) => b.text().includes('Change Password'))
      expect(submitBtn!.attributes('disabled')).toBeDefined()
    })

    it('enables submit when all passwords are filled', () => {
      const wrapper = mountForm({
        currentPassword: 'old123',
        newPassword: 'new123',
        confirmPassword: 'new123',
      })
      const submitBtn = wrapper.findAll('button').find((b) => b.text().includes('Change Password'))
      expect(submitBtn!.attributes('disabled')).toBeUndefined()
    })
  })

  describe('emits', () => {
    it('emits change-password on form submit', async () => {
      const wrapper = mountForm({
        currentPassword: 'old',
        newPassword: 'new',
        confirmPassword: 'new',
      })
      const form = wrapper.find('form')
      await form.trigger('submit')
      expect(wrapper.emitted('change-password')).toBeTruthy()
    })

    it('emits generate-invite-code when generate button clicked', async () => {
      const wrapper = mountForm()
      const btn = wrapper.findAll('button').find((b) => b.text().includes('Generate Invite Code'))
      await btn!.trigger('click')
      expect(wrapper.emitted('generate-invite-code')).toBeTruthy()
    })

    it('emits copy-invite-code when copy button clicked', async () => {
      const wrapper = mountForm({ generatedCode: 'ABC123' })
      const btn = wrapper.findAll('button').find((b) => b.text().includes('Copy'))
      expect(btn).toBeTruthy()
      await btn!.trigger('click')
      expect(wrapper.emitted('copy-invite-code')).toBeTruthy()
    })
  })

  describe('password visibility toggle', () => {
    it('toggles current password visibility', async () => {
      const wrapper = mountForm()
      // Initially password type
      const toggleBtn = wrapper
        .findAll('button')
        .find((b) => b.attributes('aria-label') === 'Show password')
      expect(toggleBtn).toBeTruthy()
      await toggleBtn!.trigger('click')
      await nextTick()
      // After toggle, button should show "Hide password"
      const hideBtn = wrapper
        .findAll('button')
        .find((b) => b.attributes('aria-label') === 'Hide password')
      expect(hideBtn).toBeTruthy()
    })
  })

  describe('invite code display', () => {
    it('shows generated code input when code is available', () => {
      const wrapper = mountForm({ generatedCode: 'XYZ789' })
      // The copy button should appear when a code is generated
      const copyBtn = wrapper.findAll('button').find((b) => b.text().includes('Copy'))
      expect(copyBtn).toBeTruthy()
    })

    it('hides code input when no code generated', () => {
      const wrapper = mountForm({ generatedCode: '' })
      // Should not have the copy button
      const copyBtn = wrapper.findAll('button').find((b) => b.text().includes('Copy'))
      expect(copyBtn).toBeUndefined()
    })

    it('shows Copied text when codeCopied is true', () => {
      const wrapper = mountForm({ generatedCode: 'ABC', codeCopied: true })
      expect(wrapper.text()).toContain('Copied')
    })
  })
})

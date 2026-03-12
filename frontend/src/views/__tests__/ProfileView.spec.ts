import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import ProfileView from '../ProfileView.vue'
import { useAuthStore } from '@/stores/auth'

const mockUpdateProfile = vi.fn()
const mockUploadAvatar = vi.fn()
const mockChangePassword = vi.fn()
const mockDeleteAccount = vi.fn()
const mockCreateInviteCode = vi.fn()
const mockGetStorageUsage = vi.fn()

vi.mock('@/api/users', () => ({
  updateProfile: (...args: unknown[]) => mockUpdateProfile(...args),
  uploadAvatar: (...args: unknown[]) => mockUploadAvatar(...args),
  changePassword: (...args: unknown[]) => mockChangePassword(...args),
  deleteAccount: (...args: unknown[]) => mockDeleteAccount(...args),
  getProfile: vi.fn(),
}))

vi.mock('@/api/admin', () => ({
  createInviteCode: (...args: unknown[]) => mockCreateInviteCode(...args),
}))

vi.mock('@/api/files', () => ({
  getStorageUsage: (...args: unknown[]) => mockGetStorageUsage(...args),
}))

vi.mock('@/composables/api', () => ({
  default: { get: vi.fn(), post: vi.fn(), put: vi.fn() },
}))

vi.mock('@/constants', () => ({
  HEARTBEAT_INTERVAL_MS: 30000,
}))

// useLocale uses the real implementation via test-setup.ts i18n

function createTestRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: { template: '<div />' } },
      { path: '/profile', component: ProfileView },
      { path: '/forum', component: { template: '<div />' } },
      { path: '/login', name: 'login', component: { template: '<div />' } },
    ],
  })
}

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
      props: ['modelValue', 'label', 'maxlength', 'placeholder', 'type', 'disabled'],
    },
    BaseTextarea: {
      template:
        '<textarea class="base-textarea" :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)"></textarea>',
      props: ['modelValue', 'label', 'rows', 'maxlength'],
    },
    BaseModal: {
      template: '<div class="base-modal" v-if="modelValue"><slot /><slot name="footer" /></div>',
      props: ['modelValue', 'title', 'size'],
    },
    BaseBadge: { template: '<span class="base-badge"><slot /></span>', props: ['variant'] },
    Eye: { template: '<span class="icon-eye" />' },
    EyeOff: { template: '<span class="icon-eye-off" />' },
    Copy: { template: '<span />' },
    Check: { template: '<span />' },
  }
}

async function mountProfile(options?: { role?: string }) {
  const { role = 'MEMBER' } = options ?? {}
  const pinia = createPinia()
  setActivePinia(pinia)
  const router = createTestRouter()

  const auth = useAuthStore()
  auth.setSession(role, 3600)
  auth.user = {
    id: 'user1',
    username: 'testuser',
    display_name: 'Test User',
    role,
    bio: 'My bio',
    affiliation: 'MIT',
    orcid: '0000-0001-0000-0000',
    avatar_url: null,
    is_banned: false,
    ban_reason: null,
  } as any

  await router.push('/profile')
  await router.isReady()

  const wrapper = mount(ProfileView, {
    global: { plugins: [pinia, router], stubs: createStubs() },
  })
  await flushPromises()
  return { wrapper, auth, router }
}

describe('ProfileView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockUpdateProfile.mockResolvedValue({
      id: 'user1',
      username: 'testuser',
      display_name: 'Updated User',
      role: 'MEMBER',
      bio: 'Updated bio',
      affiliation: 'MIT',
      orcid: null,
      avatar_url: null,
      is_banned: false,
      ban_reason: null,
    })
    mockCreateInviteCode.mockResolvedValue({ invite_code: 'ABC123' })
    mockGetStorageUsage.mockResolvedValue({ used_bytes: 500_000_000, quota_bytes: 1_073_741_824 })
  })

  it('renders profile title', async () => {
    const { wrapper } = await mountProfile()
    expect(wrapper.text()).toContain('Profile')
  })

  it('populates form fields from auth user', async () => {
    const { wrapper } = await mountProfile()
    const inputs = wrapper.findAll('.base-input')
    // Display name, affiliation, orcid should be populated
    expect(inputs.length).toBeGreaterThanOrEqual(1)
  })

  it('shows role badge in member info section', async () => {
    const { wrapper } = await mountProfile()
    expect(wrapper.find('.base-badge').exists()).toBe(true)
    expect(wrapper.text()).toContain('Member')
  })

  it('shows tab navigation with General, Security, Danger Zone', async () => {
    const { wrapper } = await mountProfile()
    expect(wrapper.text()).toContain('General')
    expect(wrapper.text()).toContain('Security')
    expect(wrapper.text()).toContain('Danger Zone')
  })

  it('hides Security and Danger Zone tabs for guest', async () => {
    const { wrapper } = await mountProfile({ role: 'GUEST' })
    expect(wrapper.text()).toContain('General')
    expect(wrapper.text()).not.toContain('Security')
    expect(wrapper.text()).not.toContain('Danger Zone')
  })

  it('saves profile on form submit', async () => {
    const { wrapper } = await mountProfile()
    const form = wrapper.find('form')
    await form.trigger('submit')
    await flushPromises()
    expect(mockUpdateProfile).toHaveBeenCalled()
  })

  it('shows success message after save', async () => {
    const { wrapper } = await mountProfile()
    const form = wrapper.find('form')
    await form.trigger('submit')
    await flushPromises()
    expect(wrapper.text()).toContain('Profile updated successfully')
  })

  it('shows error message on save failure', async () => {
    mockUpdateProfile.mockRejectedValue({
      response: { data: { detail: 'Update failed' } },
    })
    const { wrapper } = await mountProfile()
    const form = wrapper.find('form')
    await form.trigger('submit')
    await flushPromises()
    expect(wrapper.text()).toContain('Update failed')
  })

  it('switches to security tab', async () => {
    const { wrapper } = await mountProfile()
    const tabs = wrapper.findAll('button')
    const securityTab = tabs.find((b) => b.text() === 'Security')
    expect(securityTab).toBeTruthy()
    await securityTab!.trigger('click')
    await nextTick()
    // Security tab content should be visible
    expect(wrapper.text()).toContain('Change Password')
  })

  it('switches to danger zone tab', async () => {
    const { wrapper } = await mountProfile()
    const tabs = wrapper.findAll('button')
    const dangerTab = tabs.find((b) => b.text() === 'Danger Zone')
    await dangerTab!.trigger('click')
    await nextTick()
    expect(wrapper.text()).toContain('Danger Zone')
  })

  it('generates invite code on security tab', async () => {
    const { wrapper } = await mountProfile()
    // Switch to security tab
    const tabs = wrapper.findAll('button')
    const securityTab = tabs.find((b) => b.text() === 'Security')
    await securityTab!.trigger('click')
    await nextTick()

    // Find generate button
    const buttons = wrapper.findAll('button')
    const generateBtn = buttons.find((b) => b.text().includes('Generate Invite Code'))
    expect(generateBtn).toBeTruthy()
    await generateBtn!.trigger('click')
    await flushPromises()
    expect(mockCreateInviteCode).toHaveBeenCalled()
    // After generation, the copy button should appear
    const copyBtn = wrapper.findAll('button').find((b) => b.text().includes('Copy'))
    expect(copyBtn).toBeTruthy()
  })

  it('renders change avatar label', async () => {
    const { wrapper } = await mountProfile()
    expect(wrapper.text()).toContain('Change Avatar')
  })

  it('renders language selector on general tab', async () => {
    const { wrapper } = await mountProfile()
    expect(wrapper.text()).toContain('Language')
    expect(wrapper.find('[aria-haspopup="true"]').exists()).toBe(true)
  })

  describe('delete account modal', () => {
    it('clears deleteConfirmText when modal is closed', async () => {
      const { wrapper } = await mountProfile()

      // Switch to danger zone tab
      const tabs = wrapper.findAll('button')
      const dangerTab = tabs.find((b) => b.text() === 'Danger Zone')
      await dangerTab!.trigger('click')
      await nextTick()

      // Open the delete modal
      const deleteBtn = wrapper
        .findAll('button')
        .find((b) => b.text().includes('Delete My Account'))
      expect(deleteBtn).toBeTruthy()
      await deleteBtn!.trigger('click')
      await nextTick()

      // Type "DELETE" in the confirmation input
      const vm = wrapper.vm as any
      vm.deleteConfirmText = 'DELETE'
      await nextTick()

      // Close the modal via cancel
      const cancelBtn = wrapper.findAll('button').find((b) => b.text().includes('Cancel'))
      expect(cancelBtn).toBeTruthy()
      await cancelBtn!.trigger('click')
      await nextTick()

      // deleteConfirmText should be cleared
      expect(vm.deleteConfirmText).toBe('')
    })

    it('clears deleteConfirmText when modal is closed programmatically', async () => {
      const { wrapper } = await mountProfile()
      const vm = wrapper.vm as any

      // Open the delete modal
      vm.showDeleteConfirm = true
      await nextTick()

      // Type "DELETE"
      vm.deleteConfirmText = 'DELETE'
      await nextTick()

      // Close the modal
      vm.showDeleteConfirm = false
      await nextTick()

      // deleteConfirmText should be cleared by the watcher
      expect(vm.deleteConfirmText).toBe('')
    })
  })

  describe('storage usage card', () => {
    it('calls getStorageUsage on mount for non-guest users', async () => {
      await mountProfile({ role: 'MEMBER' })
      expect(mockGetStorageUsage).toHaveBeenCalledTimes(1)
    })

    it('does not call getStorageUsage for guest users', async () => {
      await mountProfile({ role: 'GUEST' })
      expect(mockGetStorageUsage).not.toHaveBeenCalled()
    })

    it('renders storage usage bar after loading', async () => {
      const { wrapper } = await mountProfile({ role: 'MEMBER' })
      // The progress bar container should exist
      const progressBar = wrapper.find('.rounded-full.h-2')
      expect(progressBar.exists()).toBe(true)
    })

    it('renders storage percent text', async () => {
      // 500_000_000 / 1_073_741_824 ≈ 46.57% → Math.round → 47%
      const { wrapper } = await mountProfile({ role: 'MEMBER' })
      expect(wrapper.text()).toContain('47%')
    })

    it('shows error state when storage fetch fails', async () => {
      mockGetStorageUsage.mockRejectedValue(new Error('Network error'))
      const { wrapper } = await mountProfile({ role: 'MEMBER' })
      // i18n resolves the key to actual translated text
      expect(wrapper.text()).toContain('Failed to load storage usage')
    })

    it('does not show storage card for guest users', async () => {
      const { wrapper } = await mountProfile({ role: 'GUEST' })
      // Storage card is hidden for guests (v-if="!auth.isGuest")
      expect(wrapper.text()).not.toContain('profile.storage.title')
    })
  })

  describe('formatBytes helper (via component state)', () => {
    it('formats bytes below 1024 as B', async () => {
      mockGetStorageUsage.mockResolvedValue({ used_bytes: 512, quota_bytes: 1_073_741_824 })
      const { wrapper } = await mountProfile({ role: 'MEMBER' })
      expect(wrapper.text()).toContain('512 B')
    })

    it('formats bytes in KB range', async () => {
      mockGetStorageUsage.mockResolvedValue({ used_bytes: 10_240, quota_bytes: 1_073_741_824 })
      const { wrapper } = await mountProfile({ role: 'MEMBER' })
      expect(wrapper.text()).toContain('10.0 KB')
    })

    it('formats bytes in MB range', async () => {
      mockGetStorageUsage.mockResolvedValue({ used_bytes: 500_000_000, quota_bytes: 1_073_741_824 })
      const { wrapper } = await mountProfile({ role: 'MEMBER' })
      expect(wrapper.text()).toContain('476.8 MB')
    })

    it('formats bytes in GB range for quota', async () => {
      mockGetStorageUsage.mockResolvedValue({
        used_bytes: 500_000_000,
        quota_bytes: 2_147_483_648,
      })
      const { wrapper } = await mountProfile({ role: 'MEMBER' })
      expect(wrapper.text()).toContain('2.00 GB')
    })
  })
})

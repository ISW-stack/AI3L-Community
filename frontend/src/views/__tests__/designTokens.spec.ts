import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import ProfileView from '../ProfileView.vue'
import { useAuthStore } from '@/stores/auth'
import type { UserProfile } from '@/types/user'

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

function createTestRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: { template: '<div />' } },
      { path: '/profile', component: ProfileView },
      { path: '/login', name: 'login', component: { template: '<div />' } },
      { path: '/forum', component: { template: '<div />' } },
      { path: '/friends', component: { template: '<div />' } },
      { path: '/following', component: { template: '<div />' } },
      { path: '/blocked-users', component: { template: '<div />' } },
      { path: '/forum/:id', component: { template: '<div />' } },
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
    BaseAlert: {
      template: '<div class="base-alert" :data-type="type"><slot /></div>',
      props: ['type'],
    },
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

async function mountProfile() {
  const pinia = createPinia()
  setActivePinia(pinia)
  const router = createTestRouter()

  const auth = useAuthStore()
  auth.setSession('MEMBER', 3600)
  auth.user = {
    id: 'user1',
    username: 'testuser',
    display_name: 'Test User',
    role: 'MEMBER',
    bio: 'My bio',
    affiliation: 'MIT',
    orcid: '0000-0001-0000-0000',
    avatar_url: null,
    is_banned: false,
    ban_reason: null,
  } as unknown as UserProfile

  await router.push('/profile')
  await router.isReady()

  const wrapper = mount(ProfileView, {
    global: { plugins: [pinia, router], stubs: createStubs() },
  })
  await flushPromises()
  return { wrapper, auth, router }
}

describe('Design tokens and dynamic alert type', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockGetStorageUsage.mockResolvedValue({ used_bytes: 500_000_000, quota_bytes: 1_073_741_824 })
  })

  it('ProfileView alert type is dynamic based on save result (success)', async () => {
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
    const { wrapper } = await mountProfile()

    // Trigger save via form submit
    const form = wrapper.find('form')
    await form.trigger('submit')
    await flushPromises()

    // The alert should have type="success"
    const alert = wrapper.find('.base-alert')
    expect(alert.exists()).toBe(true)
    expect(alert.attributes('data-type')).toBe('success')
    expect(wrapper.text()).toContain('Profile updated successfully')
  })

  it('ProfileView alert type is dynamic based on save result (error)', async () => {
    mockUpdateProfile.mockRejectedValue({
      response: { data: { detail: 'Something went wrong' } },
    })
    const { wrapper } = await mountProfile()

    // Trigger save via form submit
    const form = wrapper.find('form')
    await form.trigger('submit')
    await flushPromises()

    // The alert should have type="error"
    const alert = wrapper.find('.base-alert')
    expect(alert.exists()).toBe(true)
    expect(alert.attributes('data-type')).toBe('error')
    expect(wrapper.text()).toContain('Something went wrong')
  })
})

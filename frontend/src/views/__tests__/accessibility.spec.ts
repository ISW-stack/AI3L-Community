import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { ref } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import ProfileView from '../ProfileView.vue'
import { useAuthStore } from '@/stores/auth'

// ── ProfileView mocks ──

vi.mock('@/api/users', () => ({
  updateProfile: vi.fn().mockResolvedValue({}),
  uploadAvatar: vi.fn().mockResolvedValue({}),
  changePassword: vi.fn().mockResolvedValue({}),
  deleteAccount: vi.fn().mockResolvedValue({}),
  getProfile: vi.fn(),
}))

vi.mock('@/api/admin', () => ({
  createInviteCode: vi.fn().mockResolvedValue({ invite_code: 'ABC123' }),
}))

vi.mock('@/api/files', () => ({
  getStorageUsage: vi.fn().mockResolvedValue({ used_bytes: 0, quota_bytes: 1_073_741_824 }),
}))

vi.mock('@/api/coauthors', () => ({
  listMyInvitations: vi.fn().mockResolvedValue({ invitations: [] }),
  acceptInvitation: vi.fn().mockResolvedValue({}),
  rejectInvitation: vi.fn().mockResolvedValue({}),
}))

vi.mock('@/composables/api', () => ({
  default: { get: vi.fn(), post: vi.fn(), put: vi.fn(), delete: vi.fn() },
}))

vi.mock('@/constants', () => ({
  HEARTBEAT_INTERVAL_MS: 30000,
}))

// ── LanguageSwitcher mocks ──

const mockSetLocale = vi.fn()
const mockT = vi.fn((key: string) => key)
const mockCurrentLocale = ref('en')

vi.mock('@/composables/useLocale', () => ({
  useLocale: () => ({
    t: mockT,
    currentLocale: mockCurrentLocale,
    setLocale: mockSetLocale,
    localeOptions: [
      { value: 'en', label: 'English' },
      { value: 'fr', label: 'Fran\u00e7ais' },
    ],
  }),
}))

vi.mock('@/locales', () => ({
  LOCALE_GROUPS: [{ id: 'europe', labelKey: 'language.region.europe', locales: ['fr'] }],
  LOCALE_OPTIONS: [
    { value: 'en', label: 'English' },
    { value: 'fr', label: 'Fran\u00e7ais' },
  ],
}))

function createProfileStubs() {
  return {
    BaseCard: { template: '<div class="base-card"><slot /></div>', props: ['padding'] },
    BaseButton: {
      template:
        '<button :disabled="$attrs.disabled" :type="$attrs.type || \'button\'" @click="$emit(\'click\')"><slot /></button>',
      props: ['loading', 'variant', 'size', 'type'],
    },
    BaseAlert: { template: '<div class="base-alert"><slot /></div>', props: ['type'] },
    BaseInput: {
      template: '<input class="base-input" />',
      props: ['modelValue', 'label', 'maxlength', 'placeholder', 'type', 'disabled'],
    },
    BaseBreadcrumb: { template: '<nav />', props: ['items'] },
    ProfileEditForm: {
      template: '<div class="profile-edit-form" />',
      props: {
        displayName: String,
        bio: String,
        affiliation: String,
        orcid: String,
        username: String,
        avatarUrl: [String, null],
        role: String,
        storageUsed: Number,
        storageQuota: Number,
        storagePercent: Number,
        storageLoading: Boolean,
        storageError: Boolean,
        isGuest: Boolean,
        saving: Boolean,
        displayNameInitial: String,
      },
    },
    PasswordChangeForm: {
      template: '<div />',
      props: {
        currentPassword: String,
        newPassword: String,
        confirmPassword: String,
        passwordMessage: String,
        passwordError: Boolean,
        changingPassword: Boolean,
        generatedCode: String,
        generatingCode: Boolean,
        codeCopied: Boolean,
      },
    },
    DangerZone: { template: '<div />', props: { deletingAccount: Boolean } },
  }
}

function createTestRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: { template: '<div />' } },
      { path: '/profile', component: ProfileView },
      { path: '/login', name: 'login', component: { template: '<div />' } },
      { path: '/friends', component: { template: '<div />' } },
      { path: '/following', component: { template: '<div />' } },
      { path: '/blocked-users', component: { template: '<div />' } },
    ],
  })
}

async function mountProfileView() {
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
    bio: '',
    affiliation: '',
    orcid: '',
    avatar_url: null,
    is_banned: false,
    ban_reason: null,
  } as any

  await router.push('/profile')
  await router.isReady()

  const wrapper = mount(ProfileView, {
    global: { plugins: [pinia, router], stubs: createProfileStubs() },
  })
  await flushPromises()
  return wrapper
}

describe('ProfileView tab ARIA attributes', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockT.mockImplementation((key: string) => key)
    mockCurrentLocale.value = 'en'
  })

  it('has role="tablist" on the tab container', async () => {
    const wrapper = await mountProfileView()
    const tablist = wrapper.find('[role="tablist"]')
    expect(tablist.exists()).toBe(true)
  })

  it('has role="tab" on each tab button', async () => {
    const wrapper = await mountProfileView()
    const tabs = wrapper.findAll('[role="tab"]')
    // MEMBER sees all 4 tabs: general, social, security, danger zone
    expect(tabs.length).toBe(4)
  })

  it('has aria-selected="true" on the active (general) tab by default', async () => {
    const wrapper = await mountProfileView()
    const tabs = wrapper.findAll('[role="tab"]')
    const generalTab = tabs[0]
    expect(generalTab.attributes('aria-selected')).toBe('true')
  })

  it('has aria-selected="false" on inactive tabs', async () => {
    const wrapper = await mountProfileView()
    const tabs = wrapper.findAll('[role="tab"]')
    // All tabs except the first should be inactive
    for (let i = 1; i < tabs.length; i++) {
      expect(tabs[i].attributes('aria-selected')).toBe('false')
    }
  })

  it('updates aria-selected when switching tabs', async () => {
    const wrapper = await mountProfileView()
    const tabs = wrapper.findAll('[role="tab"]')

    // Click the second tab (social)
    await tabs[1].trigger('click')
    await wrapper.vm.$nextTick()

    const updatedTabs = wrapper.findAll('[role="tab"]')
    expect(updatedTabs[0].attributes('aria-selected')).toBe('false')
    expect(updatedTabs[1].attributes('aria-selected')).toBe('true')
  })
})

describe('LanguageSwitcher aria-label', () => {
  beforeEach(() => {
    mockT.mockImplementation((key: string) => key)
    mockCurrentLocale.value = 'en'
  })

  it('has aria-label="Select language" on the trigger button', async () => {
    const { default: LanguageSwitcher } = await import('@/components/LanguageSwitcher.vue')
    const wrapper = mount(LanguageSwitcher, {
      global: {
        stubs: {
          Globe: { template: '<span />' },
          ChevronDown: { template: '<span />' },
          ChevronRight: { template: '<span />' },
          Check: { template: '<span />' },
        },
      },
    })

    const button = wrapper.find('button')
    expect(button.attributes('aria-label')).toBe('Select language')
  })
})

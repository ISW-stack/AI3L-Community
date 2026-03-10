import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import PrivacyConsentModal from '../PrivacyConsentModal.vue'
import { acceptConsent } from '@/api/users'

vi.mock('@/api/users', () => ({
  acceptConsent: vi.fn(),
}))

vi.mock('@/composables/api', () => ({
  default: {
    post: vi.fn(),
    get: vi.fn(),
  },
}))

vi.mock('@/constants', () => ({
  HEARTBEAT_INTERVAL_MS: 30000,
}))

vi.mock('@/components/base/BaseButton.vue', () => ({
  default: {
    props: ['size', 'loading'],
    template: '<button :disabled="loading" @click="$emit(\'click\')"><slot /></button>',
  },
}))

// Mock the notifications store to avoid $reset error on setup syntax stores
vi.mock('@/stores/notifications', () => ({
  useNotificationStore: () => ({
    $reset: vi.fn(),
    unreadCount: 0,
    fetchUnreadCount: vi.fn(),
  }),
}))

const mockedAcceptConsent = vi.mocked(acceptConsent)

function createTestRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: { template: '<div />' } },
      { path: '/login', name: 'login', component: { template: '<div />' } },
    ],
  })
}

describe('PrivacyConsentModal', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.restoreAllMocks()
  })

  function mountModal() {
    const router = createTestRouter()
    return { wrapper: mount(PrivacyConsentModal, { global: { plugins: [router] } }), router }
  }

  describe('rendering', () => {
    it('should render the consent dialog', () => {
      const { wrapper } = mountModal()
      expect(wrapper.find('[role="alertdialog"]').exists()).toBe(true)
    })

    it('should have aria-modal="true"', () => {
      const { wrapper } = mountModal()
      expect(wrapper.find('[role="alertdialog"]').attributes('aria-modal')).toBe('true')
    })

    it('should render consent title and description', () => {
      const { wrapper } = mountModal()
      expect(wrapper.find('#consent-title').exists()).toBe(true)
      expect(wrapper.find('#consent-desc').exists()).toBe(true)
    })

    it('should render accept and reject buttons', () => {
      const { wrapper } = mountModal()
      const buttons = wrapper.findAll('button')
      expect(buttons.length).toBeGreaterThanOrEqual(2)
    })
  })

  describe('accept consent flow', () => {
    it('should call acceptConsent API and emit accepted on success', async () => {
      mockedAcceptConsent.mockResolvedValue(undefined as any)

      const { wrapper } = mountModal()
      const acceptBtn = wrapper.findAll('button')[0]
      await acceptBtn.trigger('click')
      await flushPromises()

      expect(mockedAcceptConsent).toHaveBeenCalled()
      expect(wrapper.emitted('accepted')).toBeTruthy()
    })

    it('should show error message when accept fails', async () => {
      mockedAcceptConsent.mockRejectedValue(new Error('Server error'))

      const { wrapper } = mountModal()
      const acceptBtn = wrapper.findAll('button')[0]
      await acceptBtn.trigger('click')
      await flushPromises()

      expect(wrapper.find('.text-danger-600').exists()).toBe(true)
    })

    it('should not show error initially', () => {
      const { wrapper } = mountModal()
      expect(wrapper.find('.text-danger-600').exists()).toBe(false)
    })
  })

  describe('reject (logout) flow', () => {
    it('should redirect to login on reject', async () => {
      const { wrapper, router } = mountModal()

      const rejectBtn = wrapper.find('button.underline')
      expect(rejectBtn.exists()).toBe(true)

      await rejectBtn.trigger('click')
      await flushPromises()

      expect(router.currentRoute.value.path).toBe('/login')
    })
  })
})

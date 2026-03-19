import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises, VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory, type Router } from 'vue-router'
import GuestLoginView from '../GuestLoginView.vue'

// ── Mocks ──

const mockGetCaptcha = vi.fn()
vi.mock('@/api/auth', () => ({
  getCaptcha: (...args: unknown[]) => mockGetCaptcha(...args),
}))

const mockGuestLogin = vi.fn()
vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({
    guestLogin: mockGuestLogin,
  }),
}))

vi.mock('@/utils/error', () => ({
  getErrorMessage: (
    e: unknown,
    tOrFallback?: ((key: string) => string) | string,
    fallbackKey?: string,
  ) => {
    if (e && typeof e === 'object' && 'response' in e) {
      const err = e as { response?: { data?: { detail?: string } } }
      if (typeof err.response?.data?.detail === 'string') return err.response.data.detail
    }
    if (typeof tOrFallback === 'function') {
      return tOrFallback(fallbackKey ?? 'errors.unknown')
    }
    return fallbackKey ?? (tOrFallback as string) ?? 'Login failed'
  },
}))

// ── Helpers ──

const CAPTCHA_RESPONSE = {
  captcha_id: 'cap-guest-1',
  image_base64: 'data:image/png;base64,GUEST1',
}

function createTestRouter(): Router {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/guest', component: GuestLoginView },
      { path: '/', component: { template: '<div>Home</div>' } },
      { path: '/register', component: { template: '<div>Register</div>' } },
      { path: '/login', component: { template: '<div>Login</div>' } },
    ],
  })
}

async function mountGuest(): Promise<{ wrapper: VueWrapper; router: Router }> {
  const pinia = createPinia()
  setActivePinia(pinia)
  const router = createTestRouter()
  await router.push('/guest')
  await router.isReady()

  const wrapper = mount(GuestLoginView, {
    global: { plugins: [pinia, router] },
  })
  await flushPromises()
  return { wrapper, router }
}

async function fillValidForm(wrapper: VueWrapper) {
  await wrapper.find('#input-invite-code').setValue('GUEST-CODE')
  await wrapper.find('#input-display-name').setValue('Guest User')
  await wrapper.find('input[maxlength="4"]').setValue('1234')
}

// ── Tests ──

describe('GuestLoginView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockGetCaptcha.mockResolvedValue(CAPTCHA_RESPONSE)
    mockGuestLogin.mockResolvedValue(undefined)
  })

  // ── Rendering ──

  describe('rendering', () => {
    it('renders the guest access title', async () => {
      const { wrapper } = await mountGuest()
      expect(wrapper.text()).toContain('Guest Access')
    })

    it('renders the guest subtitle about session limits', async () => {
      const { wrapper } = await mountGuest()
      expect(wrapper.text()).toContain('Sessions last 45 minutes')
    })

    it('renders invite code input', async () => {
      const { wrapper } = await mountGuest()
      expect(wrapper.find('#input-invite-code').exists()).toBe(true)
    })

    it('renders display name input', async () => {
      const { wrapper } = await mountGuest()
      expect(wrapper.find('#input-display-name').exists()).toBe(true)
    })

    it('renders captcha input', async () => {
      const { wrapper } = await mountGuest()
      expect(wrapper.text()).toContain('Captcha')
      expect(wrapper.find('input[maxlength="4"]').exists()).toBe(true)
    })

    it('renders submit button with guest text', async () => {
      const { wrapper } = await mountGuest()
      const btn = wrapper.find('button[type="submit"]')
      expect(btn.exists()).toBe(true)
      expect(btn.text()).toContain('Enter as Guest')
    })

    it('renders link to register page', async () => {
      const { wrapper } = await mountGuest()
      const link = wrapper.find('a[href="/register"]')
      expect(link.exists()).toBe(true)
      expect(link.text()).toContain('Sign Up')
    })

    it('renders link to login page', async () => {
      const { wrapper } = await mountGuest()
      const link = wrapper.find('a[href="/login"]')
      expect(link.exists()).toBe(true)
      expect(link.text()).toContain('Log In')
    })

    it('renders locale selector', async () => {
      const { wrapper } = await mountGuest()
      expect(wrapper.find('select').exists()).toBe(true)
    })

    it('does not render password fields', async () => {
      const { wrapper } = await mountGuest()
      const passwordInputs = wrapper.findAll('input[type="password"]')
      expect(passwordInputs.length).toBe(0)
    })
  })

  // ── Captcha ──

  describe('captcha', () => {
    it('loads captcha on mount', async () => {
      await mountGuest()
      expect(mockGetCaptcha).toHaveBeenCalledOnce()
    })

    it('displays captcha image', async () => {
      const { wrapper } = await mountGuest()
      const img = wrapper.find('img[alt="captcha"]')
      expect(img.exists()).toBe(true)
      expect(img.attributes('src')).toBe('data:image/png;base64,GUEST1')
    })

    it('refreshes captcha when image clicked', async () => {
      const { wrapper } = await mountGuest()
      mockGetCaptcha.mockResolvedValue({
        captcha_id: 'cap-guest-2',
        image_base64: 'data:image/png;base64,GUEST2',
      })

      await wrapper.find('img[alt="captcha"]').trigger('click')
      await flushPromises()

      expect(mockGetCaptcha).toHaveBeenCalledTimes(2)
      expect(wrapper.find('img[alt="captcha"]').attributes('src')).toBe(
        'data:image/png;base64,GUEST2',
      )
    })
  })

  // ── Guest Login Success ──

  describe('successful guest login', () => {
    it('calls auth.guestLogin with correct parameters', async () => {
      const { wrapper } = await mountGuest()
      await fillValidForm(wrapper)

      await wrapper.find('form').trigger('submit')
      await flushPromises()

      expect(mockGuestLogin).toHaveBeenCalledWith('GUEST-CODE', 'Guest User', 'cap-guest-1', '1234')
    })

    it('navigates to home after successful guest login', async () => {
      const { wrapper, router } = await mountGuest()
      await fillValidForm(wrapper)

      await wrapper.find('form').trigger('submit')
      await flushPromises()

      expect(router.currentRoute.value.path).toBe('/')
    })
  })

  // ── Guest Login Error ──

  describe('error handling', () => {
    it('displays API error detail', async () => {
      mockGuestLogin.mockRejectedValue({
        response: { data: { detail: 'Invalid invite code' } },
      })

      const { wrapper } = await mountGuest()
      await fillValidForm(wrapper)

      await wrapper.find('form').trigger('submit')
      await flushPromises()

      expect(wrapper.text()).toContain('Invalid invite code')
    })

    it('displays fallback error when API returns no detail', async () => {
      mockGuestLogin.mockRejectedValue(new Error('Network'))

      const { wrapper } = await mountGuest()
      await fillValidForm(wrapper)

      await wrapper.find('form').trigger('submit')
      await flushPromises()

      expect(wrapper.text()).toContain('Guest login failed. Please try again.')
    })

    it('refreshes captcha after guest login failure', async () => {
      mockGuestLogin.mockRejectedValue(new Error('fail'))

      const { wrapper } = await mountGuest()
      await fillValidForm(wrapper)

      await wrapper.find('form').trigger('submit')
      await flushPromises()

      expect(mockGetCaptcha).toHaveBeenCalledTimes(2)
    })

    it('clears error on new successful submit', async () => {
      mockGuestLogin.mockRejectedValueOnce(new Error('fail'))

      const { wrapper } = await mountGuest()
      await fillValidForm(wrapper)

      await wrapper.find('form').trigger('submit')
      await flushPromises()
      expect(wrapper.text()).toContain('Guest login failed')

      mockGuestLogin.mockResolvedValueOnce(undefined)
      await wrapper.find('form').trigger('submit')
      await flushPromises()
      expect(wrapper.text()).not.toContain('Guest login failed')
    })

    it('displays error when max concurrent guests reached', async () => {
      mockGuestLogin.mockRejectedValue({
        response: { data: { detail: 'Maximum concurrent guest sessions reached' } },
      })

      const { wrapper } = await mountGuest()
      await fillValidForm(wrapper)

      await wrapper.find('form').trigger('submit')
      await flushPromises()

      expect(wrapper.text()).toContain('Maximum concurrent guest sessions reached')
    })
  })

  // ── Loading State ──

  describe('loading state', () => {
    it('shows loading text while guest login is in progress', async () => {
      mockGuestLogin.mockReturnValue(new Promise(() => {}))

      const { wrapper } = await mountGuest()
      await fillValidForm(wrapper)

      await wrapper.find('form').trigger('submit')
      await wrapper.vm.$nextTick()

      const btn = wrapper.find('button[type="submit"]')
      expect(btn.text()).toContain('Entering...')
      expect(btn.attributes('disabled')).toBeDefined()
    })

    it('re-enables button after guest login completes', async () => {
      const { wrapper } = await mountGuest()
      await fillValidForm(wrapper)

      await wrapper.find('form').trigger('submit')
      await flushPromises()

      const btn = wrapper.find('button[type="submit"]')
      expect(btn.text()).toContain('Enter as Guest')
    })

    it('re-enables button after guest login failure', async () => {
      mockGuestLogin.mockRejectedValue(new Error('fail'))
      const { wrapper } = await mountGuest()
      await fillValidForm(wrapper)

      await wrapper.find('form').trigger('submit')
      await flushPromises()

      const btn = wrapper.find('button[type="submit"]')
      expect(btn.text()).toContain('Enter as Guest')
    })
  })
})

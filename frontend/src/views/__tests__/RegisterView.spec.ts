import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises, VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory, type Router } from 'vue-router'
import RegisterView from '../RegisterView.vue'

// ── Mocks ──

const mockGetCaptcha = vi.fn()
vi.mock('@/api/auth', () => ({
  getCaptcha: (...args: unknown[]) => mockGetCaptcha(...args),
}))

const mockRegister = vi.fn()
vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({
    register: mockRegister,
  }),
}))

vi.mock('@/utils/error', () => ({
  getErrorMessage: (e: unknown, tOrFallback?: ((key: string) => string) | string, fallbackKey?: string) => {
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
  captcha_id: 'cap-reg-1',
  image_base64: 'data:image/png;base64,REG1',
}

function createTestRouter(): Router {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/register', component: RegisterView },
      { path: '/', component: { template: '<div>Home</div>' } },
      { path: '/login', component: { template: '<div>Login</div>' } },
    ],
  })
}

async function mountRegister(): Promise<{ wrapper: VueWrapper; router: Router }> {
  const pinia = createPinia()
  setActivePinia(pinia)
  const router = createTestRouter()
  await router.push('/register')
  await router.isReady()

  const wrapper = mount(RegisterView, {
    global: { plugins: [pinia, router] },
  })
  await flushPromises()
  return { wrapper, router }
}

/** Fill all required fields with valid data. */
async function fillValidForm(wrapper: VueWrapper) {
  await wrapper.find('#input-username').setValue('newuser')
  await wrapper.find('#input-display-name').setValue('New User')
  await wrapper.find('#input-invite-code').setValue('INV-CODE')
  // Password that passes all checks
  const passwordInputs = wrapper.findAll('input[type="password"]')
  await passwordInputs[0].setValue('StrongP1')
  await passwordInputs[1].setValue('StrongP1')
  await wrapper.find('input[maxlength="4"]').setValue('ABCD')
}

// ── Tests ──

describe('RegisterView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockGetCaptcha.mockResolvedValue(CAPTCHA_RESPONSE)
    mockRegister.mockResolvedValue(undefined)
  })

  // ── Rendering ──

  describe('rendering', () => {
    it('renders the register title', async () => {
      const { wrapper } = await mountRegister()
      expect(wrapper.text()).toContain('Create an Account')
    })

    it('renders username input', async () => {
      const { wrapper } = await mountRegister()
      expect(wrapper.find('#input-username').exists()).toBe(true)
    })

    it('renders display name input', async () => {
      const { wrapper } = await mountRegister()
      expect(wrapper.find('#input-display-name').exists()).toBe(true)
    })

    it('renders invite code input', async () => {
      const { wrapper } = await mountRegister()
      expect(wrapper.find('#input-invite-code').exists()).toBe(true)
    })

    it('renders password and confirm password fields', async () => {
      const { wrapper } = await mountRegister()
      const passwordInputs = wrapper.findAll('input[type="password"]')
      expect(passwordInputs.length).toBe(2)
    })

    it('renders captcha input', async () => {
      const { wrapper } = await mountRegister()
      expect(wrapper.text()).toContain('Captcha')
      expect(wrapper.find('input[maxlength="4"]').exists()).toBe(true)
    })

    it('renders submit button', async () => {
      const { wrapper } = await mountRegister()
      const btn = wrapper.find('button[type="submit"]')
      expect(btn.exists()).toBe(true)
      expect(btn.text()).toContain('Sign Up')
    })

    it('renders link to login page', async () => {
      const { wrapper } = await mountRegister()
      const link = wrapper.find('a[href="/login"]')
      expect(link.exists()).toBe(true)
      expect(link.text()).toContain('Log In')
    })

    it('renders locale selector', async () => {
      const { wrapper } = await mountRegister()
      expect(wrapper.find('select').exists()).toBe(true)
    })

    it('renders password validation checklist', async () => {
      const { wrapper } = await mountRegister()
      expect(wrapper.text()).toContain('At least 8 characters')
      expect(wrapper.text()).toContain('Contains an uppercase letter')
      expect(wrapper.text()).toContain('Contains a lowercase letter')
      expect(wrapper.text()).toContain('Contains a digit')
    })
  })

  // ── Captcha ──

  describe('captcha', () => {
    it('loads captcha on mount', async () => {
      await mountRegister()
      expect(mockGetCaptcha).toHaveBeenCalledOnce()
    })

    it('displays captcha image', async () => {
      const { wrapper } = await mountRegister()
      const img = wrapper.find('img[alt="captcha"]')
      expect(img.exists()).toBe(true)
      expect(img.attributes('src')).toBe('data:image/png;base64,REG1')
    })

    it('refreshes captcha when image clicked', async () => {
      const { wrapper } = await mountRegister()
      mockGetCaptcha.mockResolvedValue({
        captcha_id: 'cap-reg-2',
        image_base64: 'data:image/png;base64,REG2',
      })

      await wrapper.find('img[alt="captcha"]').trigger('click')
      await flushPromises()

      expect(mockGetCaptcha).toHaveBeenCalledTimes(2)
      expect(wrapper.find('img[alt="captcha"]').attributes('src')).toBe(
        'data:image/png;base64,REG2',
      )
    })
  })

  // ── Password Validation ──

  describe('password validation', () => {
    it('submit button is disabled when password is too short', async () => {
      const { wrapper } = await mountRegister()
      const passwordInputs = wrapper.findAll('input[type="password"]')
      await passwordInputs[0].setValue('Aa1') // too short
      await passwordInputs[1].setValue('Aa1')

      const btn = wrapper.find('button[type="submit"]')
      expect(btn.attributes('disabled')).toBeDefined()
    })

    it('submit button is disabled when password lacks uppercase', async () => {
      const { wrapper } = await mountRegister()
      const passwordInputs = wrapper.findAll('input[type="password"]')
      await passwordInputs[0].setValue('lowercase1') // no uppercase
      await passwordInputs[1].setValue('lowercase1')

      const btn = wrapper.find('button[type="submit"]')
      expect(btn.attributes('disabled')).toBeDefined()
    })

    it('submit button is disabled when password lacks lowercase', async () => {
      const { wrapper } = await mountRegister()
      const passwordInputs = wrapper.findAll('input[type="password"]')
      await passwordInputs[0].setValue('UPPERCASE1') // no lowercase
      await passwordInputs[1].setValue('UPPERCASE1')

      const btn = wrapper.find('button[type="submit"]')
      expect(btn.attributes('disabled')).toBeDefined()
    })

    it('submit button is disabled when password lacks digit', async () => {
      const { wrapper } = await mountRegister()
      const passwordInputs = wrapper.findAll('input[type="password"]')
      await passwordInputs[0].setValue('NoDigitHere') // no digit
      await passwordInputs[1].setValue('NoDigitHere')

      const btn = wrapper.find('button[type="submit"]')
      expect(btn.attributes('disabled')).toBeDefined()
    })

    it('submit button is enabled when all password requirements met and passwords match', async () => {
      const { wrapper } = await mountRegister()
      await fillValidForm(wrapper)

      const btn = wrapper.find('button[type="submit"]')
      expect(btn.attributes('disabled')).toBeUndefined()
    })

    it('shows password mismatch warning when confirm password differs', async () => {
      const { wrapper } = await mountRegister()
      const passwordInputs = wrapper.findAll('input[type="password"]')
      await passwordInputs[0].setValue('StrongP1')
      await passwordInputs[1].setValue('DifferentP1')

      expect(wrapper.text()).toContain('Passwords do not match')
    })

    it('submit button is disabled when passwords do not match', async () => {
      const { wrapper } = await mountRegister()
      const passwordInputs = wrapper.findAll('input[type="password"]')
      await passwordInputs[0].setValue('StrongP1')
      await passwordInputs[1].setValue('Mismatch1')

      const btn = wrapper.find('button[type="submit"]')
      expect(btn.attributes('disabled')).toBeDefined()
    })

    it('shows error and does not call register when password is invalid on submit', async () => {
      const { wrapper } = await mountRegister()

      await wrapper.find('#input-username').setValue('user')
      await wrapper.find('#input-display-name').setValue('User')
      await wrapper.find('#input-invite-code').setValue('CODE')
      // Set weak password — force submit via form trigger
      const passwordInputs = wrapper.findAll('input[type="password"]')
      await passwordInputs[0].setValue('weak')
      await passwordInputs[1].setValue('weak')
      await wrapper.find('input[maxlength="4"]').setValue('1234')

      // Button is disabled, but trigger submit on form directly
      await wrapper.find('form').trigger('submit')
      await flushPromises()

      expect(wrapper.text()).toContain('Password does not meet the security requirements')
      expect(mockRegister).not.toHaveBeenCalled()
    })

    it('shows error when passwords do not match on submit', async () => {
      const { wrapper } = await mountRegister()

      await wrapper.find('#input-username').setValue('user')
      await wrapper.find('#input-display-name').setValue('User')
      await wrapper.find('#input-invite-code').setValue('CODE')
      const passwordInputs = wrapper.findAll('input[type="password"]')
      await passwordInputs[0].setValue('StrongP1')
      await passwordInputs[1].setValue('StrongP2')
      await wrapper.find('input[maxlength="4"]').setValue('1234')

      await wrapper.find('form').trigger('submit')
      await flushPromises()

      expect(wrapper.text()).toContain('Passwords do not match')
      expect(mockRegister).not.toHaveBeenCalled()
    })
  })

  // ── Password Toggle ──

  describe('password toggle', () => {
    it('toggles password field visibility', async () => {
      const { wrapper } = await mountRegister()
      const toggleBtns = wrapper.findAll('button[type="button"]')
      // First toggle button is for password, second for confirm password
      const pwToggle = toggleBtns[0]

      expect(pwToggle.attributes('aria-label')).toContain('Show password')
      await pwToggle.trigger('click')
      expect(pwToggle.attributes('aria-label')).toContain('Hide password')
    })

    it('toggles confirm password field visibility', async () => {
      const { wrapper } = await mountRegister()
      const toggleBtns = wrapper.findAll('button[type="button"]')
      const confirmToggle = toggleBtns[1]

      expect(confirmToggle.attributes('aria-label')).toContain('Show password')
      await confirmToggle.trigger('click')
      expect(confirmToggle.attributes('aria-label')).toContain('Hide password')
    })
  })

  // ── Registration Success ──

  describe('successful registration', () => {
    it('calls auth.register with correct parameters', async () => {
      const { wrapper } = await mountRegister()
      await fillValidForm(wrapper)

      await wrapper.find('form').trigger('submit')
      await flushPromises()

      expect(mockRegister).toHaveBeenCalledWith(
        'newuser',
        'StrongP1',
        'New User',
        'INV-CODE',
        'cap-reg-1',
        'ABCD',
      )
    })

    it('navigates to home after successful registration', async () => {
      const { wrapper, router } = await mountRegister()
      await fillValidForm(wrapper)

      await wrapper.find('form').trigger('submit')
      await flushPromises()

      expect(router.currentRoute.value.path).toBe('/')
    })
  })

  // ── Registration Error ──

  describe('error handling', () => {
    it('displays API error detail', async () => {
      mockRegister.mockRejectedValue({
        response: { data: { detail: 'Username already taken' } },
      })

      const { wrapper } = await mountRegister()
      await fillValidForm(wrapper)

      await wrapper.find('form').trigger('submit')
      await flushPromises()

      expect(wrapper.text()).toContain('Username already taken')
    })

    it('displays fallback error when API returns no detail', async () => {
      mockRegister.mockRejectedValue(new Error('Server error'))

      const { wrapper } = await mountRegister()
      await fillValidForm(wrapper)

      await wrapper.find('form').trigger('submit')
      await flushPromises()

      expect(wrapper.text()).toContain('Registration failed. Please try again.')
    })

    it('refreshes captcha after registration failure', async () => {
      mockRegister.mockRejectedValue(new Error('fail'))

      const { wrapper } = await mountRegister()
      await fillValidForm(wrapper)

      await wrapper.find('form').trigger('submit')
      await flushPromises()

      // 1 on mount + 1 on error
      expect(mockGetCaptcha).toHaveBeenCalledTimes(2)
    })

    it('clears error on new successful submit', async () => {
      mockRegister.mockRejectedValueOnce(new Error('fail'))

      const { wrapper } = await mountRegister()
      await fillValidForm(wrapper)

      await wrapper.find('form').trigger('submit')
      await flushPromises()
      expect(wrapper.text()).toContain('Registration failed')

      mockRegister.mockResolvedValueOnce(undefined)
      await wrapper.find('form').trigger('submit')
      await flushPromises()
      expect(wrapper.text()).not.toContain('Registration failed')
    })
  })

  // ── Loading State ──

  describe('loading state', () => {
    it('shows loading text while registration is in progress', async () => {
      mockRegister.mockReturnValue(new Promise(() => {}))

      const { wrapper } = await mountRegister()
      await fillValidForm(wrapper)

      await wrapper.find('form').trigger('submit')
      await wrapper.vm.$nextTick()

      const btn = wrapper.find('button[type="submit"]')
      expect(btn.text()).toContain('Signing up...')
      expect(btn.attributes('disabled')).toBeDefined()
    })

    it('re-enables button after registration completes', async () => {
      const { wrapper } = await mountRegister()
      await fillValidForm(wrapper)

      await wrapper.find('form').trigger('submit')
      await flushPromises()

      const btn = wrapper.find('button[type="submit"]')
      expect(btn.text()).toContain('Sign Up')
    })

    it('re-enables button after registration failure', async () => {
      mockRegister.mockRejectedValue(new Error('fail'))
      const { wrapper } = await mountRegister()
      await fillValidForm(wrapper)

      await wrapper.find('form').trigger('submit')
      await flushPromises()

      const btn = wrapper.find('button[type="submit"]')
      expect(btn.text()).toContain('Sign Up')
    })
  })
})

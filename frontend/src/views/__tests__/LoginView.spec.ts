import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises, VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory, type Router } from 'vue-router'
import LoginView from '../LoginView.vue'

// ── Mocks ──

const mockGetCaptcha = vi.fn()
vi.mock('@/api/auth', () => ({
  getCaptcha: (...args: unknown[]) => mockGetCaptcha(...args),
}))

const mockLogin = vi.fn()
vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({
    login: mockLogin,
  }),
}))

vi.mock('@/utils/error', () => ({
  getErrorMessage: (e: unknown, fallback: string) => {
    if (e && typeof e === 'object' && 'response' in e) {
      const err = e as { response?: { data?: { detail?: string } } }
      if (typeof err.response?.data?.detail === 'string') return err.response.data.detail
    }
    return fallback
  },
}))

// ── Helpers ──

const CAPTCHA_RESPONSE = {
  captcha_id: 'cap-123',
  image_base64: 'data:image/png;base64,AAAA',
}

function createTestRouter(): Router {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/login', component: LoginView },
      { path: '/', component: { template: '<div>Home</div>' } },
      { path: '/register', component: { template: '<div>Register</div>' } },
      { path: '/guest', component: { template: '<div>Guest</div>' } },
      { path: '/dashboard', component: { template: '<div>Dashboard</div>' } },
      { path: '/posts', component: { template: '<div>Posts</div>' } },
    ],
  })
}

async function mountLogin(routePath = '/login'): Promise<{ wrapper: VueWrapper; router: Router }> {
  const pinia = createPinia()
  setActivePinia(pinia)
  const router = createTestRouter()
  await router.push(routePath)
  await router.isReady()

  const wrapper = mount(LoginView, {
    global: { plugins: [pinia, router] },
  })
  await flushPromises()
  return { wrapper, router }
}

// ── Tests ──

describe('LoginView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockGetCaptcha.mockResolvedValue(CAPTCHA_RESPONSE)
    mockLogin.mockResolvedValue(undefined)
  })

  // ── Rendering ──

  describe('rendering', () => {
    it('renders the login title', async () => {
      const { wrapper } = await mountLogin()
      expect(wrapper.text()).toContain('Log In to AI3L Community')
    })

    it('renders username input field', async () => {
      const { wrapper } = await mountLogin()
      const labels = wrapper.findAll('label')
      const usernameLabel = labels.find((l) => l.text().includes('Username'))
      expect(usernameLabel).toBeTruthy()
    })

    it('renders password input field', async () => {
      const { wrapper } = await mountLogin()
      expect(wrapper.text()).toContain('Password')
    })

    it('renders captcha input field', async () => {
      const { wrapper } = await mountLogin()
      expect(wrapper.text()).toContain('Captcha')
    })

    it('renders login button', async () => {
      const { wrapper } = await mountLogin()
      const btn = wrapper.find('button[type="submit"]')
      expect(btn.exists()).toBe(true)
      expect(btn.text()).toContain('Log In')
    })

    it('renders link to register page', async () => {
      const { wrapper } = await mountLogin()
      const link = wrapper.find('a[href="/register"]')
      expect(link.exists()).toBe(true)
      expect(link.text()).toContain('Sign Up')
    })

    it('renders link to guest login page', async () => {
      const { wrapper } = await mountLogin()
      const link = wrapper.find('a[href="/guest"]')
      expect(link.exists()).toBe(true)
      expect(link.text()).toContain('Guest')
    })

    it('renders branding panel text', async () => {
      const { wrapper } = await mountLogin()
      expect(wrapper.text()).toContain('AI3L Community')
    })

    it('renders locale selector', async () => {
      const { wrapper } = await mountLogin()
      const select = wrapper.find('select')
      expect(select.exists()).toBe(true)
    })
  })

  // ── Captcha ──

  describe('captcha', () => {
    it('loads captcha on mount', async () => {
      await mountLogin()
      expect(mockGetCaptcha).toHaveBeenCalledOnce()
    })

    it('displays captcha image after loading', async () => {
      const { wrapper } = await mountLogin()
      const img = wrapper.find('img[alt="captcha"]')
      expect(img.exists()).toBe(true)
      expect(img.attributes('src')).toBe('data:image/png;base64,AAAA')
    })

    it('refreshes captcha when image is clicked', async () => {
      const { wrapper } = await mountLogin()
      mockGetCaptcha.mockResolvedValue({
        captcha_id: 'cap-456',
        image_base64: 'data:image/png;base64,BBBB',
      })

      const img = wrapper.find('img[alt="captcha"]')
      await img.trigger('click')
      await flushPromises()

      expect(mockGetCaptcha).toHaveBeenCalledTimes(2)
      expect(wrapper.find('img[alt="captcha"]').attributes('src')).toBe(
        'data:image/png;base64,BBBB',
      )
    })

    it('does not render captcha image when captchaImage is empty', async () => {
      mockGetCaptcha.mockResolvedValue({ captcha_id: 'x', image_base64: '' })
      const { wrapper } = await mountLogin()
      const img = wrapper.find('img[alt="captcha"]')
      expect(img.exists()).toBe(false)
    })
  })

  // ── Password Toggle ──

  describe('password toggle', () => {
    it('password field is initially of type password', async () => {
      const { wrapper } = await mountLogin()
      const input = wrapper.find('input[type="password"]')
      expect(input.exists()).toBe(true)
    })

    it('toggles password visibility when eye button is clicked', async () => {
      const { wrapper } = await mountLogin()
      const toggleBtn = wrapper.find('button[type="button"]')
      expect(toggleBtn.exists()).toBe(true)

      await toggleBtn.trigger('click')
      // After toggle, password input should become text — count text inputs
      const textInputs = wrapper.findAll('input').filter((i) => i.attributes('type') === 'text')
      // Should have captcha text input + the toggled password input
      expect(textInputs.length).toBeGreaterThanOrEqual(2)

      // Toggle back
      await toggleBtn.trigger('click')
      const pwInput = wrapper.find('input[type="password"]')
      expect(pwInput.exists()).toBe(true)
    })

    it('toggles aria-label on password button', async () => {
      const { wrapper } = await mountLogin()
      const toggleBtn = wrapper.find('button[type="button"]')
      expect(toggleBtn.attributes('aria-label')).toContain('Show password')

      await toggleBtn.trigger('click')
      expect(toggleBtn.attributes('aria-label')).toContain('Hide password')
    })
  })

  // ── Login Success ──

  describe('successful login', () => {
    it('calls auth.login with correct parameters', async () => {
      const { wrapper } = await mountLogin()

      await wrapper.find('#input-username').setValue('testuser')
      await wrapper.find('input[type="password"]').setValue('Pass1234')
      await wrapper.find('input[maxlength="4"]').setValue('ABCD')

      await wrapper.find('form').trigger('submit')
      await flushPromises()

      expect(mockLogin).toHaveBeenCalledWith('testuser', 'Pass1234', 'cap-123', 'ABCD')
    })

    it('navigates to home page after successful login', async () => {
      const { wrapper, router } = await mountLogin()

      await wrapper.find('#input-username').setValue('user1')
      await wrapper.find('input[type="password"]').setValue('pass')
      await wrapper.find('input[maxlength="4"]').setValue('1234')

      await wrapper.find('form').trigger('submit')
      await flushPromises()

      expect(router.currentRoute.value.path).toBe('/')
    })

    it('navigates to redirect query param after successful login', async () => {
      const { wrapper, router } = await mountLogin('/login?redirect=/dashboard')

      await wrapper.find('#input-username').setValue('user1')
      await wrapper.find('input[type="password"]').setValue('pass')
      await wrapper.find('input[maxlength="4"]').setValue('1234')

      await wrapper.find('form').trigger('submit')
      await flushPromises()

      expect(router.currentRoute.value.path).toBe('/dashboard')
    })

    it('sanitizes absolute URL redirect to / (open redirect prevention)', async () => {
      const { wrapper, router } = await mountLogin('/login?redirect=https://evil.com')

      await wrapper.find('#input-username').setValue('user1')
      await wrapper.find('input[type="password"]').setValue('pass')
      await wrapper.find('input[maxlength="4"]').setValue('1234')

      await wrapper.find('form').trigger('submit')
      await flushPromises()

      expect(router.currentRoute.value.path).toBe('/')
    })

    it('sanitizes protocol-relative URL redirect to / (open redirect prevention)', async () => {
      const { wrapper, router } = await mountLogin('/login?redirect=//evil.com')

      await wrapper.find('#input-username').setValue('user1')
      await wrapper.find('input[type="password"]').setValue('pass')
      await wrapper.find('input[maxlength="4"]').setValue('1234')

      await wrapper.find('form').trigger('submit')
      await flushPromises()

      expect(router.currentRoute.value.path).toBe('/')
    })

    it('allows valid internal redirect path', async () => {
      const { wrapper, router } = await mountLogin('/login?redirect=/dashboard')

      await wrapper.find('#input-username').setValue('user1')
      await wrapper.find('input[type="password"]').setValue('pass')
      await wrapper.find('input[maxlength="4"]').setValue('1234')

      await wrapper.find('form').trigger('submit')
      await flushPromises()

      expect(router.currentRoute.value.path).toBe('/dashboard')
    })

    it('blocks triple-slash redirect ///attacker.com → stays on same origin', async () => {
      const { wrapper, router } = await mountLogin('/login?redirect=///attacker.com')

      await wrapper.find('#input-username').setValue('user1')
      await wrapper.find('input[type="password"]').setValue('pass')
      await wrapper.find('input[maxlength="4"]').setValue('1234')

      await wrapper.find('form').trigger('submit')
      await flushPromises()

      // ///attacker.com resolves to same-origin path /attacker.com via URL constructor
      // This is safe — no open redirect to an external site
      expect(router.currentRoute.value.path).not.toContain('//')
    })

    it('allows redirect with query params /posts?page=2', async () => {
      const { wrapper, router } = await mountLogin(
        '/login?redirect=' + encodeURIComponent('/posts?page=2'),
      )

      await wrapper.find('#input-username').setValue('user1')
      await wrapper.find('input[type="password"]').setValue('pass')
      await wrapper.find('input[maxlength="4"]').setValue('1234')

      await wrapper.find('form').trigger('submit')
      await flushPromises()

      expect(router.currentRoute.value.path).toBe('/posts')
      expect(router.currentRoute.value.query.page).toBe('2')
    })
  })

  // ── Login Error ──

  describe('error handling', () => {
    it('displays error message from API response', async () => {
      mockLogin.mockRejectedValue({
        response: { data: { detail: 'Invalid credentials' } },
      })

      const { wrapper } = await mountLogin()

      await wrapper.find('#input-username').setValue('user1')
      await wrapper.find('input[type="password"]').setValue('wrong')
      await wrapper.find('input[maxlength="4"]').setValue('1234')

      await wrapper.find('form').trigger('submit')
      await flushPromises()

      expect(wrapper.text()).toContain('Invalid credentials')
    })

    it('displays fallback error message when API returns no detail', async () => {
      mockLogin.mockRejectedValue(new Error('Network error'))

      const { wrapper } = await mountLogin()

      await wrapper.find('#input-username').setValue('user1')
      await wrapper.find('input[type="password"]').setValue('wrong')
      await wrapper.find('input[maxlength="4"]').setValue('1234')

      await wrapper.find('form').trigger('submit')
      await flushPromises()

      expect(wrapper.text()).toContain('Login failed. Please try again.')
    })

    it('refreshes captcha after login failure', async () => {
      mockLogin.mockRejectedValue(new Error('fail'))

      const { wrapper } = await mountLogin()

      await wrapper.find('#input-username').setValue('user1')
      await wrapper.find('input[type="password"]').setValue('wrong')
      await wrapper.find('input[maxlength="4"]').setValue('1234')

      await wrapper.find('form').trigger('submit')
      await flushPromises()

      // loadCaptcha called once on mount + once on error
      expect(mockGetCaptcha).toHaveBeenCalledTimes(2)
    })

    it('clears previous error on new submit attempt', async () => {
      mockLogin.mockRejectedValueOnce(new Error('fail'))

      const { wrapper } = await mountLogin()

      await wrapper.find('#input-username').setValue('user1')
      await wrapper.find('input[type="password"]').setValue('wrong')
      await wrapper.find('input[maxlength="4"]').setValue('1234')
      await wrapper.find('form').trigger('submit')
      await flushPromises()

      expect(wrapper.text()).toContain('Login failed')

      // On second submit, login succeeds
      mockLogin.mockResolvedValueOnce(undefined)
      await wrapper.find('form').trigger('submit')
      await flushPromises()

      expect(wrapper.text()).not.toContain('Login failed')
    })
  })

  // ── Loading State ──

  describe('loading state', () => {
    it('shows loading text while login is in progress', async () => {
      mockLogin.mockReturnValue(new Promise(() => {}))

      const { wrapper } = await mountLogin()

      await wrapper.find('#input-username').setValue('user1')
      await wrapper.find('input[type="password"]').setValue('pass')
      await wrapper.find('input[maxlength="4"]').setValue('1234')

      await wrapper.find('form').trigger('submit')
      await wrapper.vm.$nextTick()

      const btn = wrapper.find('button[type="submit"]')
      expect(btn.text()).toContain('Logging in...')
      expect(btn.attributes('disabled')).toBeDefined()
    })

    it('re-enables button after login completes', async () => {
      const { wrapper } = await mountLogin()

      await wrapper.find('#input-username').setValue('user1')
      await wrapper.find('input[type="password"]').setValue('pass')
      await wrapper.find('input[maxlength="4"]').setValue('1234')

      await wrapper.find('form').trigger('submit')
      await flushPromises()

      const btn = wrapper.find('button[type="submit"]')
      expect(btn.text()).toContain('Log In')
    })

    it('re-enables button after login failure', async () => {
      mockLogin.mockRejectedValue(new Error('fail'))
      const { wrapper } = await mountLogin()

      await wrapper.find('#input-username').setValue('user1')
      await wrapper.find('input[type="password"]').setValue('pass')
      await wrapper.find('input[maxlength="4"]').setValue('1234')

      await wrapper.find('form').trigger('submit')
      await flushPromises()

      const btn = wrapper.find('button[type="submit"]')
      expect(btn.text()).toContain('Log In')
    })
  })
})

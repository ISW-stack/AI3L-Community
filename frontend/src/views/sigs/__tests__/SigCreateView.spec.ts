import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import SigCreateView from '../SigCreateView.vue'

const mockCreateSig = vi.fn()

vi.mock('@/api/sigs', () => ({
  createSig: (...args: unknown[]) => mockCreateSig(...args),
}))

vi.mock('@/composables/api', () => ({
  default: { get: vi.fn(), post: vi.fn() },
}))

vi.mock('@/constants', () => ({
  HEARTBEAT_INTERVAL_MS: 30000,
}))

function createTestRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/sigs/create', component: SigCreateView },
      { path: '/sigs', component: { template: '<div />' } },
      { path: '/sigs/:id', component: { template: '<div />' } },
    ],
  })
}

function createStubs() {
  return {
    BaseInput: {
      template:
        '<input class="base-input" :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
      props: ['modelValue', 'label', 'placeholder', 'required', 'maxlength'],
    },
    BaseTextarea: {
      template:
        '<textarea class="base-textarea" :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)"></textarea>',
      props: ['modelValue', 'label', 'placeholder', 'rows'],
    },
    BaseButton: {
      template:
        '<button :disabled="$attrs.disabled" :type="$attrs.type || \'button\'" @click="$emit(\'click\')"><slot /></button>',
      props: ['loading', 'variant', 'size', 'type'],
    },
    BaseAlert: { template: '<div class="base-alert"><slot /></div>', props: ['type'] },
  }
}

async function mountSigCreate() {
  const pinia = createPinia()
  setActivePinia(pinia)
  const router = createTestRouter()

  await router.push('/sigs/create')
  await router.isReady()

  const wrapper = mount(SigCreateView, {
    global: { plugins: [pinia, router], stubs: createStubs() },
  })
  await flushPromises()
  return { wrapper, router }
}

describe('SigCreateView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockCreateSig.mockResolvedValue({ id: 'new-sig-1' })
  })

  it('renders create SIG title', async () => {
    const { wrapper } = await mountSigCreate()
    expect(wrapper.text()).toContain('Create SIG')
  })

  it('renders name input', async () => {
    const { wrapper } = await mountSigCreate()
    const inputs = wrapper.findAll('.base-input')
    expect(inputs.length).toBeGreaterThanOrEqual(1)
  })

  it('renders description textarea', async () => {
    const { wrapper } = await mountSigCreate()
    expect(wrapper.find('.base-textarea').exists()).toBe(true)
  })

  it('renders create and cancel buttons', async () => {
    const { wrapper } = await mountSigCreate()
    expect(wrapper.text()).toContain('Create SIG')
    expect(wrapper.text()).toContain('Cancel')
  })

  it('shows cancel link to SIG directory', async () => {
    const { wrapper } = await mountSigCreate()
    const links = wrapper.findAll('a')
    const cancelLink = links.find((l) => l.attributes('href')?.includes('/sigs'))
    expect(cancelLink).toBeTruthy()
  })

  it('shows error when name is empty on submit', async () => {
    const { wrapper } = await mountSigCreate()
    const form = wrapper.find('form')
    await form.trigger('submit')
    await flushPromises()

    expect(wrapper.text()).toContain('Name is required.')
    expect(mockCreateSig).not.toHaveBeenCalled()
  })

  it('creates SIG and navigates on success', async () => {
    const { wrapper, router } = await mountSigCreate()
    const pushSpy = vi.spyOn(router, 'push')

    const nameInput = wrapper.find('.base-input')
    await nameInput.setValue('My New SIG')

    const form = wrapper.find('form')
    await form.trigger('submit')
    await flushPromises()

    expect(mockCreateSig).toHaveBeenCalledWith({
      name: 'My New SIG',
      description: null,
    })
    expect(pushSpy).toHaveBeenCalledWith('/sigs/new-sig-1')
  })

  it('creates SIG with description', async () => {
    const { wrapper } = await mountSigCreate()

    const nameInput = wrapper.find('.base-input')
    await nameInput.setValue('Research SIG')
    const descTextarea = wrapper.find('.base-textarea')
    await descTextarea.setValue('A group for research')

    const form = wrapper.find('form')
    await form.trigger('submit')
    await flushPromises()

    expect(mockCreateSig).toHaveBeenCalledWith({
      name: 'Research SIG',
      description: 'A group for research',
    })
  })

  it('shows API error message on failure', async () => {
    mockCreateSig.mockRejectedValue({
      response: { data: { detail: 'Name already taken' } },
    })
    const { wrapper } = await mountSigCreate()

    const nameInput = wrapper.find('.base-input')
    await nameInput.setValue('Duplicate SIG')

    const form = wrapper.find('form')
    await form.trigger('submit')
    await flushPromises()

    expect(wrapper.text()).toContain('Name already taken')
  })

  it('shows generic error when no detail in response', async () => {
    mockCreateSig.mockRejectedValue(new Error('Network error'))
    const { wrapper } = await mountSigCreate()

    const nameInput = wrapper.find('.base-input')
    await nameInput.setValue('New SIG')

    const form = wrapper.find('form')
    await form.trigger('submit')
    await flushPromises()

    expect(wrapper.text()).toContain('Failed to create SIG.')
  })

  it('does not show error alert initially', async () => {
    const { wrapper } = await mountSigCreate()
    expect(wrapper.find('.base-alert').exists()).toBe(false)
  })
})

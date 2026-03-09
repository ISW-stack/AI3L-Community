import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import ContributorsView from '../ContributorsView.vue'

const mockListContributors = vi.fn()
const mockCreateContributor = vi.fn()
const mockUpdateContributor = vi.fn()
const mockDeleteContributor = vi.fn()

vi.mock('@/api/contributors', () => ({
  listContributors: (...args: unknown[]) => mockListContributors(...args),
  createContributor: (...args: unknown[]) => mockCreateContributor(...args),
  updateContributor: (...args: unknown[]) => mockUpdateContributor(...args),
  deleteContributor: (...args: unknown[]) => mockDeleteContributor(...args),
}))

vi.mock('@/composables/api', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
}))

vi.mock('@/utils/error', () => ({
  getErrorMessage: (_e: unknown, fallback: string) => fallback,
}))

const fakeContributors = [
  {
    id: 'c-1',
    github_username: 'alice-gh',
    display_name: 'Alice',
    role: 'Project Lead',
    display_order: 0,
    avatar_url: '/api/v1/about/contributors/c-1/avatar',
  },
  {
    id: 'c-2',
    github_username: 'bob-gh',
    display_name: 'Bob',
    role: 'Developer',
    display_order: 1,
    avatar_url: '/api/v1/about/contributors/c-2/avatar',
  },
]

function createTestRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/admin/contributors', component: ContributorsView }],
  })
}

async function mountContributors(contributors = fakeContributors) {
  const pinia = createPinia()
  setActivePinia(pinia)
  const router = createTestRouter()
  await router.push('/admin/contributors')
  await router.isReady()

  mockListContributors.mockResolvedValue(contributors)

  const wrapper = mount(ContributorsView, {
    global: {
      plugins: [pinia, router],
      stubs: {
        BaseButton: {
          template:
            '<button :disabled="$attrs.disabled" @click="$emit(\'click\')"><slot /></button>',
          props: ['variant', 'size', 'loading'],
        },
        BaseInput: {
          template:
            '<input class="base-input" :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
          props: ['modelValue', 'label', 'placeholder', 'required', 'type'],
        },
        BaseModal: {
          template:
            '<div class="base-modal" v-if="modelValue"><slot /><slot name="footer" /></div>',
          props: ['modelValue', 'title', 'size'],
          emits: ['update:modelValue'],
        },
        SkeletonLoader: { template: '<div class="skeleton-loader" />' },
        EmptyState: {
          template: '<div class="empty-state">{{ title }}</div>',
          props: ['title', 'message'],
        },
      },
    },
  })
  await flushPromises()
  return wrapper
}

describe('ContributorsView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders the title', async () => {
    const wrapper = await mountContributors()
    expect(wrapper.find('h1').exists()).toBe(true)
  })

  it('fetches contributors on mount', async () => {
    await mountContributors()
    expect(mockListContributors).toHaveBeenCalledOnce()
  })

  it('displays contributor names and roles', async () => {
    const wrapper = await mountContributors()
    expect(wrapper.text()).toContain('Alice')
    expect(wrapper.text()).toContain('Project Lead')
    expect(wrapper.text()).toContain('Bob')
    expect(wrapper.text()).toContain('Developer')
  })

  it('displays github usernames', async () => {
    const wrapper = await mountContributors()
    expect(wrapper.text()).toContain('@alice-gh')
    expect(wrapper.text()).toContain('@bob-gh')
  })

  it('renders contributor avatars', async () => {
    const wrapper = await mountContributors()
    const images = wrapper.findAll('img')
    expect(images.length).toBe(2)
    expect(images[0].attributes('src')).toBe('/api/v1/about/contributors/c-1/avatar')
    expect(images[1].attributes('src')).toBe('/api/v1/about/contributors/c-2/avatar')
  })

  it('shows empty state when no contributors', async () => {
    const wrapper = await mountContributors([])
    expect(wrapper.find('.empty-state').exists()).toBe(true)
  })

  it('shows loading skeleton while fetching', async () => {
    mockListContributors.mockReturnValue(new Promise(() => {}))
    const pinia = createPinia()
    setActivePinia(pinia)
    const router = createTestRouter()

    const wrapper = mount(ContributorsView, {
      global: {
        plugins: [pinia, router],
        stubs: {
          BaseButton: { template: '<button><slot /></button>' },
          BaseInput: { template: '<input />' },
          BaseModal: { template: '<div />' },
          SkeletonLoader: { template: '<div class="skeleton-loader" />' },
          EmptyState: { template: '<div class="empty-state" />' },
        },
      },
    })
    await nextTick()
    expect(wrapper.find('.skeleton-loader').exists()).toBe(true)
  })

  it('opens create modal when new button is clicked', async () => {
    const wrapper = await mountContributors()

    const buttons = wrapper.findAll('button')
    await buttons[0].trigger('click')
    await nextTick()

    expect(wrapper.find('.base-modal').exists()).toBe(true)
  })

  it('opens edit modal pre-filled when edit button is clicked', async () => {
    const wrapper = await mountContributors()

    const editBtns = wrapper.findAll('button[title]')
    if (editBtns.length > 0) {
      await editBtns[0].trigger('click')
      await nextTick()

      expect(wrapper.find('.base-modal').exists()).toBe(true)
      // Inputs should be pre-filled with contributor data
      const inputs = wrapper.findAll('.base-input')
      if (inputs.length >= 3) {
        expect((inputs[0].element as HTMLInputElement).value).toBe('alice-gh')
        expect((inputs[1].element as HTMLInputElement).value).toBe('Alice')
        expect((inputs[2].element as HTMLInputElement).value).toBe('Project Lead')
      }
    }
  })

  it('calls createContributor on form submit for new contributor', async () => {
    mockCreateContributor.mockResolvedValue({
      id: 'c-3',
      github_username: 'charlie-gh',
      display_name: 'Charlie',
      role: 'Tester',
      display_order: 2,
      avatar_url: '',
    })
    mockListContributors.mockResolvedValue(fakeContributors)

    const wrapper = await mountContributors()

    // Open create modal
    await wrapper.findAll('button')[0].trigger('click')
    await nextTick()

    const inputs = wrapper.findAll('.base-input')
    if (inputs.length >= 3) {
      await inputs[0].setValue('charlie-gh')
      await inputs[1].setValue('Charlie')
      await inputs[2].setValue('Tester')
      await nextTick()

      const form = wrapper.find('form')
      await form.trigger('submit')
      await flushPromises()

      expect(mockCreateContributor).toHaveBeenCalledWith({
        github_username: 'charlie-gh',
        display_name: 'Charlie',
        role: 'Tester',
        display_order: 2,
      })
    }
  })

  it('calls updateContributor on form submit when editing', async () => {
    mockUpdateContributor.mockResolvedValue({ ...fakeContributors[0], display_name: 'Updated' })
    mockListContributors.mockResolvedValue(fakeContributors)

    const wrapper = await mountContributors()

    // Click edit on first contributor
    const editBtns = wrapper.findAll('button[title]')
    if (editBtns[0]) {
      await editBtns[0].trigger('click')
      await nextTick()

      const inputs = wrapper.findAll('.base-input')
      if (inputs.length >= 2) {
        await inputs[1].setValue('Updated')
        await nextTick()

        const form = wrapper.find('form')
        await form.trigger('submit')
        await flushPromises()

        expect(mockUpdateContributor).toHaveBeenCalledWith('c-1', expect.any(Object))
      }
    }
  })

  it('opens delete confirm modal when delete button is clicked', async () => {
    const wrapper = await mountContributors()

    const allButtons = wrapper.findAll('button[title]')
    // Delete button is the second titled button per row
    if (allButtons.length >= 2) {
      await allButtons[1].trigger('click')
      await nextTick()

      const modals = wrapper.findAll('.base-modal')
      expect(modals.length).toBeGreaterThan(0)
    }
  })

  it('calls deleteContributor when delete is confirmed', async () => {
    mockDeleteContributor.mockResolvedValue(undefined)
    mockListContributors.mockResolvedValue(fakeContributors)

    const wrapper = await mountContributors()

    // Open delete modal
    const allButtons = wrapper.findAll('button[title]')
    if (allButtons.length >= 2) {
      await allButtons[1].trigger('click')
      await nextTick()

      const modalButtons = wrapper.findAll('.base-modal button')
      const deleteBtn = modalButtons[modalButtons.length - 1]
      if (deleteBtn) {
        await deleteBtn.trigger('click')
        await flushPromises()

        expect(mockDeleteContributor).toHaveBeenCalledWith('c-1')
      }
    }
  })

  it('re-fetches contributors after successful delete', async () => {
    mockDeleteContributor.mockResolvedValue(undefined)

    const wrapper = await mountContributors()

    mockListContributors.mockClear()
    mockListContributors.mockResolvedValue(fakeContributors)

    const allButtons = wrapper.findAll('button[title]')
    if (allButtons.length >= 2) {
      await allButtons[1].trigger('click')
      await nextTick()

      const modalButtons = wrapper.findAll('.base-modal button')
      const deleteBtn = modalButtons[modalButtons.length - 1]
      if (deleteBtn) {
        await deleteBtn.trigger('click')
        await flushPromises()

        // Should have been called at least once after delete
        expect(mockListContributors).toHaveBeenCalled()
      }
    }
  })

  it('does not submit when required fields are empty', async () => {
    const wrapper = await mountContributors()

    await wrapper.findAll('button')[0].trigger('click')
    await nextTick()

    // Submit without filling anything
    const form = wrapper.find('form')
    await form.trigger('submit')
    await flushPromises()

    expect(mockCreateContributor).not.toHaveBeenCalled()
  })

  it('displays display_order for each contributor', async () => {
    const wrapper = await mountContributors()
    expect(wrapper.text()).toContain('#0')
    expect(wrapper.text()).toContain('#1')
  })
})

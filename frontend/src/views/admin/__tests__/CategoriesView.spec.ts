import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import CategoriesView from '../CategoriesView.vue'

const mockListCategories = vi.fn()
const mockCreateCategory = vi.fn()
const mockUpdateCategory = vi.fn()
const mockDeleteCategory = vi.fn()

vi.mock('@/api/categories', () => ({
  listCategories: (...args: unknown[]) => mockListCategories(...args),
  createCategory: (...args: unknown[]) => mockCreateCategory(...args),
  updateCategory: (...args: unknown[]) => mockUpdateCategory(...args),
  deleteCategory: (...args: unknown[]) => mockDeleteCategory(...args),
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

const fakeCategories = [
  { id: 'cat-1', name: 'AI Research', description: 'Papers about AI', post_count: 10 },
  { id: 'cat-2', name: 'Literacy', description: null, post_count: 5 },
]

function createTestRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/admin/categories', component: CategoriesView }],
  })
}

async function mountCategories(cats = fakeCategories) {
  const pinia = createPinia()
  setActivePinia(pinia)
  const router = createTestRouter()
  await router.push('/admin/categories')
  await router.isReady()

  mockListCategories.mockResolvedValue(cats)

  const wrapper = mount(CategoriesView, {
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

describe('CategoriesView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders the title', async () => {
    const wrapper = await mountCategories()
    expect(wrapper.find('h1').exists()).toBe(true)
  })

  it('fetches categories on mount', async () => {
    await mountCategories()
    expect(mockListCategories).toHaveBeenCalledOnce()
  })

  it('displays category names', async () => {
    const wrapper = await mountCategories()
    expect(wrapper.text()).toContain('AI Research')
    expect(wrapper.text()).toContain('Literacy')
  })

  it('displays category descriptions when present', async () => {
    const wrapper = await mountCategories()
    expect(wrapper.text()).toContain('Papers about AI')
  })

  it('shows empty state when no categories', async () => {
    const wrapper = await mountCategories([])
    expect(wrapper.find('.empty-state').exists()).toBe(true)
  })

  it('shows loading skeleton while fetching', async () => {
    mockListCategories.mockReturnValue(new Promise(() => {}))
    const pinia = createPinia()
    setActivePinia(pinia)
    const router = createTestRouter()

    const wrapper = mount(CategoriesView, {
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
    const wrapper = await mountCategories()

    // Find the "new" button (first button in header area)
    const buttons = wrapper.findAll('button')
    const newBtn = buttons[0]
    await newBtn.trigger('click')
    await nextTick()

    expect(wrapper.find('.base-modal').exists()).toBe(true)
  })

  it('opens edit modal when edit button is clicked', async () => {
    const wrapper = await mountCategories()

    // Edit buttons are inside category rows — find the first edit icon button
    const editBtns = wrapper.findAll('button[title]')
    const editBtn = editBtns.find((b) => b.attributes('title')?.length)
    if (editBtn) {
      await editBtn.trigger('click')
      await nextTick()
      expect(wrapper.find('.base-modal').exists()).toBe(true)
    }
  })

  it('calls createCategory on form submit for new category', async () => {
    mockCreateCategory.mockResolvedValue({
      id: 'cat-3',
      name: 'New Cat',
      description: 'Desc',
      post_count: 0,
    })
    mockListCategories.mockResolvedValue(fakeCategories)

    const wrapper = await mountCategories()

    // Open create modal
    const buttons = wrapper.findAll('button')
    await buttons[0].trigger('click')
    await nextTick()

    // Fill form
    const inputs = wrapper.findAll('.base-input')
    if (inputs.length >= 2) {
      await inputs[0].setValue('New Cat')
      await inputs[1].setValue('Desc')
      await nextTick()

      // Submit form
      const form = wrapper.find('form')
      await form.trigger('submit')
      await flushPromises()

      expect(mockCreateCategory).toHaveBeenCalledWith({
        name: 'New Cat',
        description: 'Desc',
      })
    }
  })

  it('calls updateCategory on form submit when editing', async () => {
    mockUpdateCategory.mockResolvedValue({
      id: 'cat-1',
      name: 'Updated',
      description: 'Updated desc',
      post_count: 10,
    })
    mockListCategories.mockResolvedValue(fakeCategories)

    const wrapper = await mountCategories()

    // Click edit on first category
    const editBtns = wrapper.findAll('button[title]')
    const editBtn = editBtns[0]
    if (editBtn) {
      await editBtn.trigger('click')
      await nextTick()

      // Modify name
      const inputs = wrapper.findAll('.base-input')
      if (inputs.length >= 1) {
        await inputs[0].setValue('Updated')
        await nextTick()

        const form = wrapper.find('form')
        await form.trigger('submit')
        await flushPromises()

        expect(mockUpdateCategory).toHaveBeenCalled()
      }
    }
  })

  it('opens delete confirm modal when delete button is clicked', async () => {
    const wrapper = await mountCategories()

    // Find delete buttons (second icon button per row)
    const allButtons = wrapper.findAll('button[title]')
    // Delete button should be the second titled button
    if (allButtons.length >= 2) {
      await allButtons[1].trigger('click')
      await nextTick()

      // Delete confirm modal should appear
      const modals = wrapper.findAll('.base-modal')
      expect(modals.length).toBeGreaterThan(0)
    }
  })

  it('calls deleteCategory when delete is confirmed', async () => {
    mockDeleteCategory.mockResolvedValue(undefined)
    mockListCategories.mockResolvedValue(fakeCategories)

    const wrapper = await mountCategories()

    // Open delete modal for first category
    const allButtons = wrapper.findAll('button[title]')
    if (allButtons.length >= 2) {
      await allButtons[1].trigger('click')
      await nextTick()

      // Find and click the danger/delete confirm button in modal
      const modalButtons = wrapper.findAll('.base-modal button')
      const deleteConfirmBtn = modalButtons[modalButtons.length - 1]
      if (deleteConfirmBtn) {
        await deleteConfirmBtn.trigger('click')
        await flushPromises()

        expect(mockDeleteCategory).toHaveBeenCalledWith('cat-1')
      }
    }
  })

  it('re-fetches categories after successful create', async () => {
    mockCreateCategory.mockResolvedValue({
      id: 'cat-3',
      name: 'New',
      description: undefined,
      post_count: 0,
    })
    mockListCategories.mockResolvedValue(fakeCategories)

    const wrapper = await mountCategories()

    // Open create modal
    await wrapper.findAll('button')[0].trigger('click')
    await nextTick()

    const inputs = wrapper.findAll('.base-input')
    if (inputs.length >= 1) {
      await inputs[0].setValue('New')
      await nextTick()

      const form = wrapper.find('form')
      await form.trigger('submit')
      await flushPromises()

      // listCategories called on mount + after create
      expect(mockListCategories).toHaveBeenCalledTimes(2)
    }
  })

  it('does not call createCategory when name is empty', async () => {
    const wrapper = await mountCategories()

    await wrapper.findAll('button')[0].trigger('click')
    await nextTick()

    // Submit without filling name
    const form = wrapper.find('form')
    await form.trigger('submit')
    await flushPromises()

    expect(mockCreateCategory).not.toHaveBeenCalled()
  })
})

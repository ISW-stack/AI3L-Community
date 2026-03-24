import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import FormShareCard from '../FormShareCard.vue'
import { getForm } from '@/api/forms'
import type { FormData } from '@/types'

vi.mock('@/api/forms', () => ({
  getForm: vi.fn(),
}))

vi.mock('@/components/base/BaseCard.vue', () => ({
  default: { template: '<div class="base-card"><slot /></div>' },
}))

vi.mock('@/components/base/BaseBadge.vue', () => ({
  default: {
    props: ['variant'],
    template: '<span class="base-badge"><slot /></span>',
  },
}))

vi.mock('@/components/SkeletonLoader.vue', () => ({
  default: {
    props: ['lines', 'variant'],
    template: '<div class="skeleton" />',
  },
}))

function createTestRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: { template: '<div />' } },
      { path: '/forms/:id', component: { template: '<div />' } },
    ],
  })
}

const mockedGetForm = vi.mocked(getForm)

describe('FormShareCard', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('should show skeleton while loading', () => {
    mockedGetForm.mockReturnValue(new Promise(() => {})) // never resolves
    const router = createTestRouter()
    const wrapper = mount(FormShareCard, {
      props: { formId: 'form-1' },
      global: { plugins: [router] },
    })
    expect(wrapper.find('.skeleton').exists()).toBe(true)
  })

  it('should render form data after loading', async () => {
    mockedGetForm.mockResolvedValue({
      id: 'form-1',
      title: 'Survey A',
      description: 'A test survey',
      is_active: true,
      response_count: 5,
      deadline: '2026-12-31T00:00:00Z',
      created_by_name: 'Alice',
    } as unknown as FormData)

    const router = createTestRouter()
    const wrapper = mount(FormShareCard, {
      props: { formId: 'form-1' },
      global: { plugins: [router] },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('Survey A')
    expect(wrapper.text()).toContain('A test survey')
    expect(wrapper.text()).toContain('5 response(s)')
    expect(wrapper.text()).toContain('Alice')
    expect(wrapper.text()).toContain('Active')
    expect(wrapper.find('a[href="/forms/form-1"]').exists()).toBe(true)
  })

  it('should show Closed badge for inactive form', async () => {
    mockedGetForm.mockResolvedValue({
      id: 'form-2',
      title: 'Old Form',
      description: null,
      is_active: false,
      response_count: 0,
      deadline: null,
      created_by_name: 'Bob',
    } as unknown as FormData)

    const router = createTestRouter()
    const wrapper = mount(FormShareCard, {
      props: { formId: 'form-2' },
      global: { plugins: [router] },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('Closed')
  })

  it('should show error state when API fails', async () => {
    mockedGetForm.mockRejectedValue(new Error('Not found'))

    const router = createTestRouter()
    const wrapper = mount(FormShareCard, {
      props: { formId: 'form-bad' },
      global: { plugins: [router] },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('[Form not found]')
  })

  it('should not show description when null', async () => {
    mockedGetForm.mockResolvedValue({
      id: 'form-3',
      title: 'No Desc',
      description: null,
      is_active: true,
      response_count: 0,
      deadline: null,
      created_by_name: 'Carol',
    } as unknown as FormData)

    const router = createTestRouter()
    const wrapper = mount(FormShareCard, {
      props: { formId: 'form-3' },
      global: { plugins: [router] },
    })
    await flushPromises()

    const descP = wrapper.findAll('p').filter((p) => p.classes().includes('line-clamp-2'))
    expect(descP.length).toBe(0)
  })
})

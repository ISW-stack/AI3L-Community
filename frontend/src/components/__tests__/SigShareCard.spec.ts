import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import SigShareCard from '../SigShareCard.vue'
import { getSig } from '@/api/sigs'

vi.mock('@/api/sigs', () => ({
  getSig: vi.fn(),
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
      { path: '/sigs/:id', component: { template: '<div />' } },
    ],
  })
}

const mockedGetSig = vi.mocked(getSig)

describe('SigShareCard', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('should show skeleton while loading', () => {
    mockedGetSig.mockReturnValue(new Promise(() => {}))
    const router = createTestRouter()
    const wrapper = mount(SigShareCard, {
      props: { sigId: 'sig-1' },
      global: { plugins: [router] },
    })
    expect(wrapper.find('.skeleton').exists()).toBe(true)
  })

  it('should render SIG data after loading', async () => {
    mockedGetSig.mockResolvedValue({
      id: 'sig-1',
      name: 'NLP Research',
      description: 'A group for NLP researchers',
      member_count: 15,
      creator_display_name: 'Alice',
    } as any)

    const router = createTestRouter()
    const wrapper = mount(SigShareCard, {
      props: { sigId: 'sig-1' },
      global: { plugins: [router] },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('NLP Research')
    expect(wrapper.text()).toContain('A group for NLP researchers')
    expect(wrapper.text()).toContain('15 member(s)')
    expect(wrapper.text()).toContain('Alice')
    expect(wrapper.find('a[href="/sigs/sig-1"]').exists()).toBe(true)
  })

  it('should show error state when API fails', async () => {
    mockedGetSig.mockRejectedValue(new Error('Not found'))

    const router = createTestRouter()
    const wrapper = mount(SigShareCard, {
      props: { sigId: 'sig-bad' },
      global: { plugins: [router] },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('[SIG not found]')
  })

  it('should show "Unknown" when creator_display_name is null', async () => {
    mockedGetSig.mockResolvedValue({
      id: 'sig-2',
      name: 'Test SIG',
      description: null,
      member_count: 1,
      creator_display_name: null,
    } as any)

    const router = createTestRouter()
    const wrapper = mount(SigShareCard, {
      props: { sigId: 'sig-2' },
      global: { plugins: [router] },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('Unknown')
  })

  it('should not show description when null', async () => {
    mockedGetSig.mockResolvedValue({
      id: 'sig-3',
      name: 'No Desc SIG',
      description: null,
      member_count: 3,
      creator_display_name: 'Bob',
    } as any)

    const router = createTestRouter()
    const wrapper = mount(SigShareCard, {
      props: { sigId: 'sig-3' },
      global: { plugins: [router] },
    })
    await flushPromises()

    const descP = wrapper.findAll('p').filter((p) => p.classes().includes('line-clamp-2'))
    expect(descP.length).toBe(0)
  })
})

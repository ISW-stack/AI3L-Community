import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import CitationSearchDialog from '../CitationSearchDialog.vue'

vi.mock('@/api/citations', () => ({
  searchForCitation: vi.fn().mockResolvedValue({ data: [] }),
}))

vi.mock('@/utils/error', () => ({
  getErrorMessage: (_e: unknown, fallback: string) => fallback,
}))

vi.mock('@/components/base/BaseModal.vue', () => ({
  default: {
    props: ['modelValue', 'title', 'size'],
    template: '<div><slot /></div>',
  },
}))

vi.mock('lucide-vue-next', () => ({
  Search: { template: '<span />' },
}))

describe('CitationSearchDialog — timer cleanup', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('clears debounce timer on unmount', async () => {
    const clearTimeoutSpy = vi.spyOn(globalThis, 'clearTimeout')

    const wrapper = mount(CitationSearchDialog, {
      props: { modelValue: true },
    })

    // Type into the search input to start a debounce timer
    const input = wrapper.find('input')
    await input.setValue('test query')
    await input.trigger('input')

    // Unmount before the debounce timer fires (300ms)
    wrapper.unmount()

    // clearTimeout should have been called during unmount
    expect(clearTimeoutSpy).toHaveBeenCalled()

    clearTimeoutSpy.mockRestore()
  })

  it('does not error on unmount when no timer is active', () => {
    const wrapper = mount(CitationSearchDialog, {
      props: { modelValue: true },
    })

    // Unmount without any search input — no timer should be active
    expect(() => wrapper.unmount()).not.toThrow()
  })

  it('debounce timer fires normally when component is not unmounted', async () => {
    const { searchForCitation } = await import('@/api/citations')
    const mockSearch = searchForCitation as ReturnType<typeof vi.fn>
    mockSearch.mockResolvedValue({ data: [{ id: '1', title: 'Post 1', author_name: 'Alice', created_at: '2026-01-01' }] })

    const wrapper = mount(CitationSearchDialog, {
      props: { modelValue: true },
    })

    const input = wrapper.find('input')
    await input.setValue('test')
    await input.trigger('input')

    // Advance past the debounce delay
    vi.advanceTimersByTime(300)
    await flushPromises()

    expect(mockSearch).toHaveBeenCalledWith('test')
  })
})

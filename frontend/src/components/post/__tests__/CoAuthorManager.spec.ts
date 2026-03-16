import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import CoAuthorManager from '../CoAuthorManager.vue'

vi.mock('@/api/coauthors', () => ({
  listCoAuthors: vi.fn().mockResolvedValue({ data: { co_authors: [] } }),
  inviteCoAuthor: vi.fn(),
  addExternalCoAuthor: vi.fn(),
  removeCoAuthor: vi.fn(),
  searchUsers: vi.fn().mockResolvedValue({ data: [] }),
}))

vi.mock('@/utils/error', () => ({
  getErrorMessage: (_e: unknown, fallback: string) => fallback,
}))

vi.mock('@/stores/toast', () => ({
  useToastStore: () => ({
    show: vi.fn(),
  }),
}))

vi.mock('@/components/base/BaseButton.vue', () => ({
  default: {
    props: ['loading', 'size', 'disabled'],
    template: '<button @click="$emit(\'click\')"><slot /></button>',
  },
}))

vi.mock('@/components/base/BaseInput.vue', () => ({
  default: {
    props: ['modelValue', 'label', 'placeholder', 'required'],
    template:
      '<input :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
  },
}))

vi.mock('@/components/base/BaseBadge.vue', () => ({
  default: {
    props: ['variant'],
    template: '<span><slot /></span>',
  },
}))

vi.mock('@/components/base/BaseAvatar.vue', () => ({
  default: {
    props: ['src', 'name', 'size'],
    template: '<img :alt="name" />',
  },
}))

vi.mock('@/components/base/BaseAlert.vue', () => ({
  default: {
    props: ['type'],
    template: '<div><slot /></div>',
  },
}))

vi.mock('lucide-vue-next', () => ({
  UserPlus: { template: '<span />' },
  X: { template: '<span />' },
  Users: { template: '<span />' },
}))

describe('CoAuthorManager — timer cleanup', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('clears search debounce timer on unmount', async () => {
    const clearTimeoutSpy = vi.spyOn(globalThis, 'clearTimeout')

    const wrapper = mount(CoAuthorManager, {
      props: { postId: 'post-1' },
    })
    await flushPromises()

    // Type into the search input to start a debounce timer
    const inputs = wrapper.findAll('input')
    const searchInput = inputs.find((i) => i.attributes('placeholder')?.includes('Search'))
    expect(searchInput).toBeTruthy()

    await searchInput!.setValue('alice')
    await searchInput!.trigger('input')

    // Unmount before the debounce timer fires (300ms)
    wrapper.unmount()

    // clearTimeout should have been called during unmount
    expect(clearTimeoutSpy).toHaveBeenCalled()

    clearTimeoutSpy.mockRestore()
  })

  it('does not error on unmount when no search timer is active', async () => {
    const wrapper = mount(CoAuthorManager, {
      props: { postId: 'post-1' },
    })
    await flushPromises()

    // Unmount without triggering search — no timer should be active
    expect(() => wrapper.unmount()).not.toThrow()
  })

  it('search debounce fires normally when component is not unmounted', async () => {
    const { searchUsers } = await import('@/api/coauthors')
    const mockSearchUsers = searchUsers as ReturnType<typeof vi.fn>
    mockSearchUsers.mockResolvedValue({
      data: [{ id: 'u1', display_name: 'Alice', avatar_url: null }],
    })

    const wrapper = mount(CoAuthorManager, {
      props: { postId: 'post-1' },
    })
    await flushPromises()

    const inputs = wrapper.findAll('input')
    const searchInput = inputs.find((i) => i.attributes('placeholder')?.includes('Search'))

    await searchInput!.setValue('alice')
    await searchInput!.trigger('input')

    // Advance past the debounce delay
    vi.advanceTimersByTime(300)
    await flushPromises()

    expect(mockSearchUsers).toHaveBeenCalledWith('alice')
  })
})

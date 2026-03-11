import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { defineComponent, ref, nextTick } from 'vue'
import { mount } from '@vue/test-utils'
import { useInfiniteScroll } from '../useInfiniteScroll'

// ---------------------------------------------------------------------------
// IntersectionObserver mock
// ---------------------------------------------------------------------------

type IOCallback = (entries: IntersectionObserverEntry[]) => void

let capturedCallback: IOCallback | null = null
let capturedElement: Element | null = null
const mockDisconnect = vi.fn()
const mockObserve = vi.fn((el: Element) => {
  capturedElement = el
})
const mockUnobserve = vi.fn()

class MockIntersectionObserver {
  constructor(callback: IOCallback) {
    capturedCallback = callback
  }
  observe = mockObserve
  unobserve = mockUnobserve
  disconnect = mockDisconnect
}

beforeEach(() => {
  capturedCallback = null
  capturedElement = null
  mockDisconnect.mockClear()
  mockObserve.mockClear()
  mockUnobserve.mockClear()
  vi.stubGlobal('IntersectionObserver', MockIntersectionObserver)
})

afterEach(() => {
  vi.unstubAllGlobals()
})

// ---------------------------------------------------------------------------
// Helper: mount a component that uses the composable
// ---------------------------------------------------------------------------

function makeComponent(onLoadMore: () => void) {
  return defineComponent({
    setup() {
      const sentinel = ref<HTMLElement | null>(null)
      useInfiniteScroll(sentinel, onLoadMore)
      return { sentinel }
    },
    template: '<div ref="sentinel" class="sentinel"></div>',
  })
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('useInfiniteScroll', () => {
  it('creates an IntersectionObserver on mount', async () => {
    const onLoadMore = vi.fn()
    const wrapper = mount(makeComponent(onLoadMore))
    await nextTick()
    expect(capturedCallback).not.toBeNull()
    wrapper.unmount()
  })

  it('observes the sentinel element on mount', async () => {
    const onLoadMore = vi.fn()
    const wrapper = mount(makeComponent(onLoadMore))
    await nextTick()
    expect(mockObserve).toHaveBeenCalledTimes(1)
    expect(capturedElement).toBe(wrapper.element)
    wrapper.unmount()
  })

  it('calls onLoadMore when the sentinel intersects', async () => {
    const onLoadMore = vi.fn()
    const wrapper = mount(makeComponent(onLoadMore))
    await nextTick()

    // Simulate intersection
    capturedCallback!([{ isIntersecting: true } as IntersectionObserverEntry])

    expect(onLoadMore).toHaveBeenCalledTimes(1)
    wrapper.unmount()
  })

  it('does NOT call onLoadMore when isIntersecting is false', async () => {
    const onLoadMore = vi.fn()
    const wrapper = mount(makeComponent(onLoadMore))
    await nextTick()

    capturedCallback!([{ isIntersecting: false } as IntersectionObserverEntry])

    expect(onLoadMore).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('calls onLoadMore on each intersection event', async () => {
    const onLoadMore = vi.fn()
    const wrapper = mount(makeComponent(onLoadMore))
    await nextTick()

    capturedCallback!([{ isIntersecting: true } as IntersectionObserverEntry])
    capturedCallback!([{ isIntersecting: true } as IntersectionObserverEntry])
    capturedCallback!([{ isIntersecting: true } as IntersectionObserverEntry])

    expect(onLoadMore).toHaveBeenCalledTimes(3)
    wrapper.unmount()
  })

  it('disconnects the observer on unmount', async () => {
    const onLoadMore = vi.fn()
    const wrapper = mount(makeComponent(onLoadMore))
    await nextTick()

    wrapper.unmount()

    expect(mockDisconnect).toHaveBeenCalledTimes(1)
  })

  it('does not throw when sentinel ref is null on mount', async () => {
    // Component that never sets the sentinel ref
    const comp = defineComponent({
      setup() {
        const sentinel = ref<HTMLElement | null>(null)
        // Don't assign to template ref — sentinel stays null
        useInfiniteScroll(sentinel, vi.fn())
        return {}
      },
      template: '<div></div>',
    })
    expect(() => mount(comp)).not.toThrow()
  })

  it('uses custom threshold option', async () => {
    const OriginalMockIO = MockIntersectionObserver
    let receivedOptions: IntersectionObserverInit | undefined

    class CapturingObserver {
      constructor(_cb: IOCallback, opts?: IntersectionObserverInit) {
        receivedOptions = opts
      }
      observe = vi.fn()
      disconnect = vi.fn()
    }

    vi.stubGlobal('IntersectionObserver', CapturingObserver)

    const comp = defineComponent({
      setup() {
        const sentinel = ref<HTMLElement | null>(null)
        useInfiniteScroll(sentinel, vi.fn(), { threshold: 0.5 })
        return { sentinel }
      },
      template: '<div ref="sentinel"></div>',
    })

    const wrapper = mount(comp)
    await nextTick()

    expect(receivedOptions?.threshold).toBe(0.5)
    wrapper.unmount()

    // Restore
    vi.stubGlobal('IntersectionObserver', OriginalMockIO)
  })
})

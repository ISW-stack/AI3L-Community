import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useToastStore } from '../toast'

describe('Toast Store Timer Cleanup', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    setActivePinia(createPinia())
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('dismiss clears the auto-dismiss timer', () => {
    const store = useToastStore()
    store.show('test', 'info')
    expect(store.toasts).toHaveLength(1)

    const id = store.toasts[0].id
    store.dismiss(id)
    expect(store.toasts).toHaveLength(0)

    // Advance timers past the auto-dismiss duration — should not cause errors
    vi.advanceTimersByTime(6000)
    expect(store.toasts).toHaveLength(0)
  })

  it('dismiss prevents double-removal from auto-dismiss timer', () => {
    const store = useToastStore()
    store.show('first', 'info')
    store.show('second', 'warning')

    const firstId = store.toasts[0].id
    store.dismiss(firstId)
    expect(store.toasts).toHaveLength(1)
    expect(store.toasts[0].message).toBe('second')

    // When the original timer fires, it should be a no-op (already cleared)
    vi.advanceTimersByTime(5000)
    // 'second' should be dismissed by its own timer, but 'first' should not cause issues
    expect(store.toasts).toHaveLength(0)
  })

  it('clearAll removes all toasts and timers', () => {
    const store = useToastStore()
    store.show('msg1', 'info')
    store.show('msg2', 'error')
    store.show('msg3', 'warning')
    expect(store.toasts).toHaveLength(3)

    store.clearAll()
    expect(store.toasts).toHaveLength(0)

    // Advance past all auto-dismiss timers — should not cause errors or re-add toasts
    vi.advanceTimersByTime(6000)
    expect(store.toasts).toHaveLength(0)
  })

  it('clearAll followed by new show works correctly', () => {
    const store = useToastStore()
    store.show('old1', 'info')
    store.show('old2', 'error')
    store.clearAll()

    store.show('new1', 'success')
    expect(store.toasts).toHaveLength(1)
    expect(store.toasts[0].message).toBe('new1')

    // Old timers should not interfere
    vi.advanceTimersByTime(5000)
    // new1 auto-dismissed by its own timer
    expect(store.toasts).toHaveLength(0)
  })

  it('auto-dismiss fires after TOAST_DURATION_MS (5000ms)', () => {
    const store = useToastStore()
    store.show('auto', 'info')
    expect(store.toasts).toHaveLength(1)

    vi.advanceTimersByTime(4999)
    expect(store.toasts).toHaveLength(1)

    vi.advanceTimersByTime(1)
    expect(store.toasts).toHaveLength(0)
  })

  it('multiple dismiss calls for the same id are safe', () => {
    const store = useToastStore()
    store.show('test', 'info')
    const id = store.toasts[0].id

    store.dismiss(id)
    store.dismiss(id)
    expect(store.toasts).toHaveLength(0)
  })
})

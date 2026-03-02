import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useToastStore } from '../toast'

describe('useToastStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  describe('show', () => {
    it('should add a toast with correct message and type', () => {
      const store = useToastStore()
      store.show('Hello World', 'info')

      expect(store.toasts).toHaveLength(1)
      expect(store.toasts[0].message).toBe('Hello World')
      expect(store.toasts[0].type).toBe('info')
    })

    it('should default type to info', () => {
      const store = useToastStore()
      store.show('Default type')

      expect(store.toasts[0].type).toBe('info')
    })

    it('should support all toast types', () => {
      const store = useToastStore()
      store.show('Info', 'info')
      store.show('Warning', 'warning')
      store.show('Error', 'error')
      store.show('Success', 'success')

      expect(store.toasts).toHaveLength(4)
      expect(store.toasts[0].type).toBe('info')
      expect(store.toasts[1].type).toBe('warning')
      expect(store.toasts[2].type).toBe('error')
      expect(store.toasts[3].type).toBe('success')
    })

    it('should auto-dismiss a toast after 5000ms', () => {
      const store = useToastStore()
      store.show('Temporary', 'info')

      expect(store.toasts).toHaveLength(1)

      vi.advanceTimersByTime(4999)
      expect(store.toasts).toHaveLength(1)

      vi.advanceTimersByTime(1)
      expect(store.toasts).toHaveLength(0)
    })

    it('should assign incrementing IDs to toasts', () => {
      const store = useToastStore()
      store.show('First', 'info')
      store.show('Second', 'warning')

      expect(store.toasts[0].id).toBeLessThan(store.toasts[1].id)
    })

    it('should handle multiple toasts with independent timers', () => {
      const store = useToastStore()
      store.show('First', 'info')

      vi.advanceTimersByTime(2000)
      store.show('Second', 'warning')

      expect(store.toasts).toHaveLength(2)

      // 3000ms after first toast (5000ms total) — first should dismiss
      vi.advanceTimersByTime(3000)
      expect(store.toasts).toHaveLength(1)
      expect(store.toasts[0].message).toBe('Second')

      // 2000ms more — second should dismiss
      vi.advanceTimersByTime(2000)
      expect(store.toasts).toHaveLength(0)
    })
  })

  describe('dismiss', () => {
    it('should dismiss a specific toast by id', () => {
      const store = useToastStore()
      store.show('A', 'info')
      store.show('B', 'error')

      const idA = store.toasts[0].id
      store.dismiss(idA)

      expect(store.toasts).toHaveLength(1)
      expect(store.toasts[0].message).toBe('B')
    })

    it('should be a no-op if id does not exist', () => {
      const store = useToastStore()
      store.show('A', 'info')

      store.dismiss(999)
      expect(store.toasts).toHaveLength(1)
    })

    it('should not affect other toasts when dismissing one', () => {
      const store = useToastStore()
      store.show('A', 'info')
      store.show('B', 'warning')
      store.show('C', 'error')

      const idB = store.toasts[1].id
      store.dismiss(idB)

      expect(store.toasts).toHaveLength(2)
      expect(store.toasts[0].message).toBe('A')
      expect(store.toasts[1].message).toBe('C')
    })
  })
})

import { defineStore } from 'pinia'
import { ref } from 'vue'

export type ToastType = 'info' | 'warning' | 'error' | 'success'

export interface Toast {
  id: number
  message: string
  type: ToastType
}

const TOAST_DURATION_MS = 5000

export const useToastStore = defineStore('toast', () => {
  const toasts = ref<Toast[]>([])
  let nextId = 0
  const timers = new Map<number, ReturnType<typeof setTimeout>>()

  function show(message: string, type: ToastType = 'info') {
    const id = nextId++
    toasts.value.push({ id, message, type })
    const timer = setTimeout(() => {
      dismiss(id)
    }, TOAST_DURATION_MS)
    timers.set(id, timer)
  }

  function dismiss(id: number) {
    const timer = timers.get(id)
    if (timer) {
      clearTimeout(timer)
      timers.delete(id)
    }
    toasts.value = toasts.value.filter((t) => t.id !== id)
  }

  function clearAll() {
    timers.forEach((timer) => clearTimeout(timer))
    timers.clear()
    toasts.value = []
  }

  return { toasts, show, dismiss, clearAll }
})

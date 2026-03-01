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

  function show(message: string, type: ToastType = 'info') {
    const id = nextId++
    toasts.value.push({ id, message, type })
    setTimeout(() => {
      dismiss(id)
    }, TOAST_DURATION_MS)
  }

  function dismiss(id: number) {
    toasts.value = toasts.value.filter((t) => t.id !== id)
  }

  return { toasts, show, dismiss }
})

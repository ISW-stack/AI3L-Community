<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'

interface Toast {
  id: number
  message: string
  type: 'info' | 'warning' | 'error' | 'success'
}

const toasts = ref<Toast[]>([])
let nextId = 0

function addToast(message: string, type: Toast['type'] = 'info') {
  const id = nextId++
  toasts.value.push({ id, message, type })
  setTimeout(() => {
    toasts.value = toasts.value.filter((t) => t.id !== id)
  }, 5000)
}

function handleCustomEvent(e: Event) {
  const detail = (e as CustomEvent).detail
  addToast(detail.message, detail.type || 'info')
}

onMounted(() => {
  window.addEventListener('app:toast', handleCustomEvent)
})

onUnmounted(() => {
  window.removeEventListener('app:toast', handleCustomEvent)
})

const typeClasses: Record<string, string> = {
  info: 'bg-blue-50 border-blue-200 text-blue-700',
  warning: 'bg-yellow-50 border-yellow-200 text-yellow-700',
  error: 'bg-red-50 border-red-200 text-red-700',
  success: 'bg-green-50 border-green-200 text-green-700',
}
</script>

<template>
  <div class="fixed top-4 right-4 z-[100] space-y-2">
    <transition-group name="toast">
      <div
        v-for="toast in toasts"
        :key="toast.id"
        class="px-4 py-3 rounded-lg border shadow-sm text-sm max-w-sm"
        :class="typeClasses[toast.type]"
      >
        {{ toast.message }}
      </div>
    </transition-group>
  </div>
</template>

<style scoped>
.toast-enter-active,
.toast-leave-active {
  transition: all 0.3s ease;
}
.toast-enter-from {
  opacity: 0;
  transform: translateX(30px);
}
.toast-leave-to {
  opacity: 0;
  transform: translateX(30px);
}
</style>

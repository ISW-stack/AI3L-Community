<script setup lang="ts">
import { useToastStore } from '@/stores/toast'

const toastStore = useToastStore()

const typeClasses: Record<string, string> = {
  info: 'bg-info-50 border-info-100 text-info-700',
  warning: 'bg-warning-50 border-warning-100 text-warning-700',
  error: 'bg-danger-50 border-danger-100 text-danger-700',
  success: 'bg-success-50 border-success-100 text-success-700',
}
</script>

<template>
  <div class="fixed top-4 right-4 z-[100] space-y-2" aria-live="assertive">
    <transition-group name="toast">
      <div
        v-for="toast in toastStore.toasts"
        :key="toast.id"
        class="px-4 py-3 rounded-lg border shadow-sm text-sm max-w-sm"
        :class="typeClasses[toast.type]"
        role="alert"
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

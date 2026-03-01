<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(defineProps<{
  type?: 'error' | 'success' | 'warning' | 'info'
  dismissible?: boolean
}>(), {
  type: 'info',
  dismissible: false,
})

const emit = defineEmits<{ dismiss: [] }>()

const typeClass = computed(() => {
  const map: Record<string, string> = {
    error:   'bg-danger-50 border-danger-100 text-danger-700',
    success: 'bg-success-50 border-success-100 text-success-700',
    warning: 'bg-warning-50 border-warning-100 text-warning-700',
    info:    'bg-info-50 border-info-100 text-info-700',
  }
  return map[props.type]
})
</script>

<template>
  <div
    :class="['rounded-lg border p-3 text-sm', typeClass]"
    role="alert"
  >
    <div class="flex items-start justify-between gap-2">
      <div class="flex-1"><slot /></div>
      <button
        v-if="dismissible"
        class="shrink-0 opacity-60 hover:opacity-100 transition"
        aria-label="Dismiss"
        @click="emit('dismiss')"
      >
        &times;
      </button>
    </div>
  </div>
</template>

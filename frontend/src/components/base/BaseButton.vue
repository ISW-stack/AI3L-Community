<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(
  defineProps<{
    variant?:
      | 'primary'
      | 'secondary'
      | 'danger'
      | 'success'
      | 'ghost'
      | 'soft-danger'
      | 'soft-success'
    size?: 'sm' | 'md' | 'lg' | 'full'
    disabled?: boolean
    loading?: boolean
  }>(),
  {
    variant: 'primary',
    size: 'md',
    disabled: false,
    loading: false,
  },
)

const variantClass = computed(() => {
  const map: Record<string, string> = {
    primary: 'bg-brand-600 text-white hover:bg-brand-700',
    secondary: 'bg-surface-alt text-muted border border-border hover:bg-gray-100',
    danger: 'bg-danger-600 text-white hover:bg-danger-700',
    success: 'bg-success-600 text-white hover:bg-success-700',
    ghost: 'text-brand-600 hover:underline',
    'soft-danger': 'bg-danger-50 text-danger-600 hover:bg-danger-100',
    'soft-success': 'bg-success-50 text-success-600 hover:bg-success-100',
  }
  return map[props.variant]
})

const sizeClass = computed(() => {
  const map: Record<string, string> = {
    sm: 'px-3 py-1.5 text-xs rounded-md',
    md: 'px-4 py-2 text-sm rounded-lg',
    lg: 'px-6 py-2.5 text-sm rounded-lg',
    full: 'w-full py-2.5 text-sm rounded-lg font-medium',
  }
  return map[props.size]
})
</script>

<template>
  <button
    :class="[
      'inline-flex items-center justify-center font-medium transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2',
      variantClass,
      sizeClass,
      (disabled || loading) && 'opacity-50 cursor-not-allowed',
    ]"
    :disabled="disabled || loading"
  >
    <svg
      v-if="loading"
      class="animate-spin -ml-1 mr-2 h-4 w-4"
      xmlns="http://www.w3.org/2000/svg"
      fill="none"
      viewBox="0 0 24 24"
    >
      <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
      <path
        class="opacity-75"
        fill="currentColor"
        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
      />
    </svg>
    <slot />
  </button>
</template>

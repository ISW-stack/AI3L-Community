<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(
  defineProps<{
    variant?: 'brand' | 'success' | 'warning' | 'danger' | 'neutral' | 'orange' | 'purple'
    size?: 'sm' | 'md'
  }>(),
  {
    variant: 'brand',
    size: 'sm',
  },
)

const variantClass = computed(() => {
  const map: Record<string, string> = {
    brand: 'bg-brand-100 text-brand-700',
    success: 'bg-success-100 text-success-700',
    warning: 'bg-warning-100 text-warning-700',
    danger: 'bg-danger-100 text-danger-700',
    neutral: 'bg-gray-100 text-gray-600',
    orange: 'bg-orange-100 text-orange-700',
    purple: 'bg-purple-100 text-purple-700',
  }
  return map[props.variant]
})

const sizeClass = computed(() => {
  return props.size === 'sm' ? 'text-xs px-2 py-0.5' : 'text-xs px-2.5 py-1'
})
</script>

<template>
  <span :class="['inline-flex items-center font-medium rounded-full', variantClass, sizeClass]">
    <slot />
  </span>
</template>

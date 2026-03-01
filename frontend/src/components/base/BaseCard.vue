<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(
  defineProps<{
    hoverable?: boolean
    padding?: 'none' | 'sm' | 'md' | 'lg'
  }>(),
  {
    hoverable: false,
    padding: 'md',
  },
)

const paddingClass = computed(() => {
  const map: Record<string, string> = {
    none: '',
    sm: 'p-4',
    md: 'p-5',
    lg: 'p-6',
  }
  return map[props.padding]
})
</script>

<template>
  <div
    :class="[
      'bg-surface rounded-lg shadow',
      paddingClass,
      hoverable && 'hover:shadow-md transition',
    ]"
  >
    <slot />
  </div>
</template>

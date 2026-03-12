<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(
  defineProps<{
    src?: string | null
    name: string
    size?: 'sm' | 'md' | 'lg'
    loading?: 'lazy' | 'eager'
  }>(),
  { src: null, size: 'sm', loading: 'lazy' },
)

const sizeClass = computed(() => {
  switch (props.size) {
    case 'sm':
      return 'w-8 h-8 text-xs'
    case 'md':
      return 'w-10 h-10 text-sm'
    case 'lg':
      return 'w-20 h-20 text-2xl'
    default:
      return 'w-8 h-8 text-xs'
  }
})

const sizeDimensions = computed(() => {
  switch (props.size) {
    case 'sm':
      return { width: 32, height: 32 }
    case 'md':
      return { width: 40, height: 40 }
    case 'lg':
      return { width: 80, height: 80 }
    default:
      return { width: 32, height: 32 }
  }
})

const initial = computed(() => (props.name ? props.name.charAt(0).toUpperCase() : '?'))
</script>

<template>
  <div
    :class="[
      sizeClass,
      'rounded-full bg-brand-100 text-brand-700 flex items-center justify-center overflow-hidden shrink-0 font-semibold',
    ]"
  >
    <img
      v-if="src"
      :src="src"
      :alt="name"
      :loading="loading"
      :width="sizeDimensions.width"
      :height="sizeDimensions.height"
      @error="(e: Event) => ((e.target as HTMLImageElement).src = '/fallback-avatar.svg')"
      class="w-full h-full object-cover"
    />
    <span v-else>{{ initial }}</span>
  </div>
</template>

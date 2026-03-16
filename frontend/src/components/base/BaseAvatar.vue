<script setup lang="ts">
import { computed, ref, watch } from 'vue'

const props = withDefaults(
  defineProps<{
    src?: string | null
    name: string
    size?: 'xs' | 'sm' | 'md' | 'lg'
  }>(),
  { src: null, size: 'sm' },
)

const imgFailed = ref(false)
watch(
  () => props.src,
  () => {
    imgFailed.value = false
  },
)

const sizeClass = computed(() => {
  switch (props.size) {
    case 'xs':
      return 'w-5 h-5 text-[10px]'
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

const sizePx = computed(() => {
  const map: Record<string, number> = { xs: 20, sm: 32, md: 40, lg: 80 }
  return map[props.size ?? 'sm'] ?? 32
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
      v-if="src && !imgFailed"
      :src="src"
      :alt="`${name}'s avatar`"
      loading="lazy"
      :width="sizePx"
      :height="sizePx"
      class="w-full h-full object-cover"
      @error="imgFailed = true"
    />
    <span v-else>{{ initial }}</span>
  </div>
</template>

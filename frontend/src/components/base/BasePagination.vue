<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(
  defineProps<{
    currentPage: number
    totalPages: number
    maxVisible?: number
  }>(),
  {
    maxVisible: 5,
  },
)

const emit = defineEmits<{
  'update:currentPage': [page: number]
}>()

const pages = computed(() => {
  const total = props.totalPages
  const current = props.currentPage
  const max = props.maxVisible

  if (total <= max) {
    return Array.from({ length: total }, (_, i) => i + 1)
  }

  const half = Math.floor(max / 2)
  let start = Math.max(1, current - half)
  const end = Math.min(total, start + max - 1)

  if (end - start + 1 < max) {
    start = Math.max(1, end - max + 1)
  }

  return Array.from({ length: end - start + 1 }, (_, i) => start + i)
})
</script>

<template>
  <div v-if="totalPages > 1" class="flex items-center justify-center gap-1 flex-wrap">
    <button
      :disabled="currentPage <= 1"
      class="px-3 py-1 text-sm rounded-lg border border-border text-muted hover:bg-surface-alt disabled:opacity-30 transition"
      @click="emit('update:currentPage', currentPage - 1)"
    >
      Prev
    </button>
    <button
      v-for="page in pages"
      :key="page"
      :class="[
        'px-3 py-1 text-sm rounded-lg border transition',
        page === currentPage
          ? 'bg-brand-600 text-white border-brand-600'
          : 'bg-surface text-muted border-border hover:bg-surface-alt',
      ]"
      @click="emit('update:currentPage', page)"
    >
      {{ page }}
    </button>
    <button
      :disabled="currentPage >= totalPages"
      class="px-3 py-1 text-sm rounded-lg border border-border text-muted hover:bg-surface-alt disabled:opacity-30 transition"
      @click="emit('update:currentPage', currentPage + 1)"
    >
      Next
    </button>
  </div>
</template>

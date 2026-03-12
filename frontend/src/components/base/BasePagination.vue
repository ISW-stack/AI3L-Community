<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

const props = withDefaults(
  defineProps<{
    currentPage: number
    totalPages: number
    maxVisible?: number
    pageSize?: number
    total?: number
  }>(),
  {
    maxVisible: 5,
    pageSize: 0,
    total: 0,
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

const showingStart = computed(() => {
  if (!props.pageSize || !props.total) return 0
  return (props.currentPage - 1) * props.pageSize + 1
})

const showingEnd = computed(() => {
  if (!props.pageSize || !props.total) return 0
  return Math.min(props.currentPage * props.pageSize, props.total)
})

const showResultCount = computed(() => props.pageSize > 0 && props.total > 0)
</script>

<template>
  <nav v-if="totalPages > 1" :aria-label="t('accessibility.pagination')" class="space-y-2">
    <!-- Result count text -->
    <p v-if="showResultCount" class="text-sm text-muted text-center" data-testid="result-count">
      {{ t('pagination.showing', { start: showingStart, end: showingEnd, total }) }}
    </p>

    <!-- Desktop pagination (sm+) -->
    <div
      class="hidden sm:flex items-center justify-center gap-1 flex-wrap"
      data-testid="desktop-pagination"
    >
      <button
        :disabled="currentPage <= 1"
        class="px-3 py-2 sm:py-1 text-sm rounded-lg border border-border text-muted hover:bg-surface-alt disabled:opacity-30 transition"
        @click="emit('update:currentPage', currentPage - 1)"
      >
        {{ t('common.prev') }}
      </button>
      <button
        v-for="page in pages"
        :key="page"
        :aria-current="page === currentPage ? 'page' : undefined"
        :class="[
          'px-3 py-2 sm:py-1 text-sm rounded-lg border transition',
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
        class="px-3 py-2 sm:py-1 text-sm rounded-lg border border-border text-muted hover:bg-surface-alt disabled:opacity-30 transition"
        @click="emit('update:currentPage', currentPage + 1)"
      >
        {{ t('common.next') }}
      </button>
    </div>

    <!-- Mobile pagination (<sm) -->
    <div class="flex sm:hidden items-center justify-center gap-3" data-testid="mobile-pagination">
      <button
        :disabled="currentPage <= 1"
        class="px-3 py-2 sm:py-1 text-sm rounded-lg border border-border text-muted hover:bg-surface-alt disabled:opacity-30 transition"
        @click="emit('update:currentPage', currentPage - 1)"
      >
        {{ t('common.prev') }}
      </button>
      <span class="text-sm text-muted">
        {{ t('pagination.pageOf', { current: currentPage, total: totalPages }) }}
      </span>
      <button
        :disabled="currentPage >= totalPages"
        class="px-3 py-2 sm:py-1 text-sm rounded-lg border border-border text-muted hover:bg-surface-alt disabled:opacity-30 transition"
        @click="emit('update:currentPage', currentPage + 1)"
      >
        {{ t('common.next') }}
      </button>
    </div>
  </nav>
</template>

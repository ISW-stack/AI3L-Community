<script setup lang="ts">
import { useI18n } from 'vue-i18n'

const props = defineProps<{
  currentSort: string
  options: Array<{ value: string; label: string }>
  activeCategoryName?: string | null
}>()

const emit = defineEmits<{
  select: [sort: string]
}>()

const { t } = useI18n()

function buttonClass(index: number) {
  const isFirst = index === 0
  const isLast = index === props.options.length - 1
  const rounded = isFirst ? 'rounded-l-lg' : isLast ? 'rounded-r-lg' : ''
  const border = isFirst || isLast ? 'border' : 'border-y'
  return `${rounded} ${border}`
}
</script>

<template>
  <div class="flex items-center gap-1 mb-4">
    <span class="text-sm text-muted mr-2">{{ t('common.sortLabel') }}</span>
    <button
      v-for="(opt, idx) in props.options"
      :key="opt.value"
      class="px-3 py-1.5 text-sm font-medium transition"
      :class="[
        buttonClass(idx),
        props.currentSort === opt.value
          ? 'bg-brand-600 text-white border-brand-600'
          : 'bg-surface text-foreground border-border hover:bg-surface-alt',
      ]"
      @click="emit('select', opt.value)"
    >
      {{ opt.label }}
    </button>
    <span v-if="props.activeCategoryName" class="ml-3 text-sm text-muted">
      {{ t('common.in') }}
      <span class="font-medium text-foreground">{{ props.activeCategoryName }}</span>
    </span>
  </div>
</template>

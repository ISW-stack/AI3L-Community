<script setup lang="ts">
import { Check } from 'lucide-vue-next'
import { useLocale } from '@/composables/useLocale'

const { t } = useLocale()

defineProps<{
  isOwner: boolean
  isBest: boolean
}>()

const emit = defineEmits<{
  mark: []
  unmark: []
}>()

function handleMark() {
  emit('mark')
}

function handleUnmark() {
  emit('unmark')
}
</script>

<template>
  <div class="inline-flex items-center gap-1">
    <span
      v-if="isBest"
      class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-green-100 text-green-700 text-xs font-medium"
    >
      <Check class="w-3.5 h-3.5" />
      {{ t('qa.bestAnswer') }}
    </span>
    <button
      v-if="isOwner && isBest"
      type="button"
      class="text-xs text-muted hover:text-danger-600 hover:underline ml-1"
      @click="handleUnmark"
    >
      {{ t('qa.unmarkBest') }}
    </button>
    <button
      v-if="isOwner && !isBest"
      type="button"
      class="text-xs text-muted hover:text-green-600 hover:underline opacity-0 group-hover:opacity-100 transition-opacity"
      @click="handleMark"
    >
      {{ t('qa.markBest') }}
    </button>
  </div>
</template>

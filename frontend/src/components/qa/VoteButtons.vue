<script setup lang="ts">
import { ChevronUp, ChevronDown } from 'lucide-vue-next'

const props = defineProps<{
  commentId: string
  score: number
  userVote: -1 | 0 | 1
  disabled: boolean
}>()

const emit = defineEmits<{
  vote: [value: -1 | 0 | 1]
}>()

function handleUpVote() {
  if (props.disabled) return
  emit('vote', props.userVote === 1 ? 0 : 1)
}

function handleDownVote() {
  if (props.disabled) return
  emit('vote', props.userVote === -1 ? 0 : -1)
}
</script>

<template>
  <div class="flex flex-col items-center gap-0.5">
    <button
      type="button"
      :disabled="disabled"
      :class="[
        'p-1 rounded transition',
        userVote === 1
          ? 'text-brand-600 bg-brand-50'
          : 'text-muted hover:text-brand-600 hover:bg-brand-50',
        disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer',
      ]"
      :aria-label="'Vote up'"
      @click="handleUpVote"
    >
      <ChevronUp class="w-5 h-5" />
    </button>
    <span
      class="text-sm font-semibold tabular-nums"
      :class="score > 0 ? 'text-brand-600' : score < 0 ? 'text-danger-600' : 'text-muted'"
    >
      {{ score }}
    </span>
    <button
      type="button"
      :disabled="disabled"
      :class="[
        'p-1 rounded transition',
        userVote === -1
          ? 'text-danger-600 bg-danger-50'
          : 'text-muted hover:text-danger-600 hover:bg-danger-50',
        disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer',
      ]"
      :aria-label="'Vote down'"
      @click="handleDownVote"
    >
      <ChevronDown class="w-5 h-5" />
    </button>
  </div>
</template>

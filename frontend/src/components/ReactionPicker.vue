<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { Smile } from 'lucide-vue-next'
import { REACTIONS } from '@/constants'

const EMOJI_MAP: Record<string, string> = {
  LIKE: '\uD83D\uDC4D',
  SMILE: '\uD83D\uDE0A',
  CRY: '\uD83D\uDE22',
}

const props = withDefaults(
  defineProps<{
    reactionCounts: Record<string, number> | null
    userReactions: string[] | null
    readonly?: boolean
  }>(),
  { readonly: false },
)

const emit = defineEmits<{
  (e: 'toggle', reaction: string): void
}>()

const pickerOpen = ref(false)

function getCount(r: string): number {
  return props.reactionCounts?.[r] ?? 0
}

function hasReacted(r: string): boolean {
  return props.userReactions?.includes(r) ?? false
}

const visibleReactions = computed(() => REACTIONS.filter((r) => getCount(r) > 0))

function togglePicker() {
  pickerOpen.value = !pickerOpen.value
}

function handleReaction(r: string) {
  emit('toggle', r)
  pickerOpen.value = false
}

function handleClickOutside(e: MouseEvent) {
  const target = e.target as HTMLElement
  if (!target.closest('.reaction-picker-wrapper')) {
    pickerOpen.value = false
  }
}

onMounted(() => document.addEventListener('click', handleClickOutside))
onUnmounted(() => document.removeEventListener('click', handleClickOutside))
</script>

<template>
  <div class="reaction-picker-wrapper flex items-center gap-1 flex-wrap">
    <!-- Reaction chips: only reactions that have at least 1 count -->
    <template v-if="readonly">
      <span
        v-for="r in visibleReactions"
        :key="r"
        class="text-xs px-2 py-0.5 rounded-full bg-surface-alt text-muted inline-flex items-center gap-1"
      >
        {{ EMOJI_MAP[r] }}
        <span>{{ getCount(r) }}</span>
      </span>
    </template>
    <template v-else>
      <button
        v-for="r in visibleReactions"
        :key="r"
        type="button"
        :aria-label="`React with ${r}`"
        :aria-pressed="hasReacted(r)"
        class="text-xs px-2 py-0.5 rounded-full transition-colors inline-flex items-center gap-1 cursor-pointer"
        :class="
          hasReacted(r)
            ? 'bg-brand-100 text-brand-700'
            : 'bg-surface-alt text-muted hover:bg-gray-100'
        "
        @click.stop="handleReaction(r)"
      >
        {{ EMOJI_MAP[r] }}
        <span>{{ getCount(r) }}</span>
      </button>

      <!-- Picker trigger -->
      <div class="relative">
        <button
          type="button"
          aria-label="Add reaction"
          class="text-xs px-1.5 py-0.5 rounded-full bg-surface-alt text-muted hover:bg-gray-100 transition-colors inline-flex items-center gap-0.5"
          @click.stop="togglePicker"
        >
          <Smile class="w-3.5 h-3.5" aria-hidden="true" />
          <span class="font-bold leading-none">+</span>
        </button>

        <!-- Picker popup -->
        <Transition name="picker">
          <div
            v-if="pickerOpen"
            class="absolute bottom-full right-0 sm:right-auto sm:left-0 mb-1.5 bg-surface border border-border rounded-xl shadow-lg px-2 py-1.5 flex items-center gap-0.5 z-50 max-w-[calc(100vw-2rem)]"
          >
            <button
              v-for="r in REACTIONS"
              :key="r"
              type="button"
              :aria-label="`React with ${r}`"
              :title="r.charAt(0) + r.slice(1).toLowerCase()"
              class="text-xl p-1.5 rounded-lg transition-colors hover:bg-surface-alt"
              :class="hasReacted(r) ? 'bg-brand-100' : ''"
              @click.stop="handleReaction(r)"
            >
              {{ EMOJI_MAP[r] }}
            </button>
          </div>
        </Transition>
      </div>
    </template>
  </div>
</template>

<style scoped>
.picker-enter-active,
.picker-leave-active {
  transition: all 0.15s ease;
}
.picker-enter-from,
.picker-leave-to {
  opacity: 0;
  transform: translateY(4px) scale(0.95);
}
</style>

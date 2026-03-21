<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import type { Category } from '@/types'

const props = withDefaults(
  defineProps<{
    categories: Category[]
    activeCategory: string | null
    mode: 'pills' | 'list'
    allLabel?: string
  }>(),
  { allLabel: undefined },
)

const emit = defineEmits<{
  select: [categoryId: string | null]
}>()

const { t } = useI18n()
</script>

<template>
  <!-- Pills mode (mobile) -->
  <div v-if="props.mode === 'pills'" class="relative">
    <div class="overflow-x-auto no-scrollbar">
      <div class="flex gap-2 pb-2">
        <button
          class="shrink-0 px-3 py-1.5 rounded-full text-sm font-medium transition"
          :class="
            !props.activeCategory
              ? 'bg-brand-600 text-white'
              : 'bg-surface-alt text-muted hover:bg-surface-alt'
          "
          @click="emit('select', null)"
        >
          {{ props.allLabel ?? t('common.all') }}
        </button>
        <button
          v-for="cat in props.categories"
          :key="cat.id"
          class="shrink-0 px-3 py-1.5 rounded-full text-sm font-medium transition"
          :class="
            props.activeCategory === cat.id
              ? 'bg-brand-600 text-white'
              : 'bg-surface-alt text-muted hover:bg-surface-alt'
          "
          @click="emit('select', cat.id)"
        >
          {{ cat.name }} ({{ cat.post_count }})
        </button>
      </div>
    </div>
    <div
      class="absolute right-0 top-0 bottom-2 w-8 bg-gradient-to-l from-surface to-transparent pointer-events-none"
    ></div>
  </div>

  <!-- List mode (sidebar) -->
  <ul v-else class="space-y-1">
    <li>
      <button
        class="w-full text-left px-3 py-2 rounded-lg text-sm transition"
        :class="
          !props.activeCategory
            ? 'bg-brand-50 text-brand-700 font-medium'
            : 'text-foreground hover:bg-surface-alt'
        "
        @click="emit('select', null)"
      >
        {{ props.allLabel ?? t('common.all') }}
      </button>
    </li>
    <li v-for="cat in props.categories" :key="cat.id">
      <button
        class="w-full text-left px-3 py-2 rounded-lg text-sm transition flex justify-between items-center"
        :class="
          props.activeCategory === cat.id
            ? 'bg-brand-50 text-brand-700 font-medium'
            : 'text-foreground hover:bg-surface-alt'
        "
        @click="emit('select', cat.id)"
      >
        <span>{{ cat.name }}</span>
        <span class="text-xs text-muted">{{ cat.post_count }}</span>
      </button>
    </li>
  </ul>
</template>

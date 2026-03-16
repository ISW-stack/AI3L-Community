<script setup lang="ts">
import type { CoAuthor } from '@/types/coauthor'
import BaseAvatar from '@/components/base/BaseAvatar.vue'

const props = defineProps<{
  coAuthors: CoAuthor[]
}>()

const MAX_VISIBLE = 3

const visibleAuthors = props.coAuthors.slice(0, MAX_VISIBLE)
const remaining = props.coAuthors.length - MAX_VISIBLE
</script>

<template>
  <div v-if="coAuthors.length > 0" class="flex items-center gap-1 flex-wrap">
    <span class="text-xs text-muted mr-0.5">with</span>
    <div
      v-for="ca in visibleAuthors"
      :key="ca.id"
      class="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full bg-surface-alt text-xs text-foreground"
    >
      <BaseAvatar :src="ca.avatar_url" :name="ca.display_name" size="xs" />
      <span class="max-w-[80px] truncate">{{ ca.display_name }}</span>
    </div>
    <span v-if="remaining > 0" class="text-xs text-muted"> and {{ remaining }} more </span>
  </div>
</template>

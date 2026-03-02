<script setup lang="ts">
import type { Post } from '@/types'
import BaseCard from '@/components/base/BaseCard.vue'
import BaseBadge from '@/components/base/BaseBadge.vue'
import BaseAvatar from '@/components/base/BaseAvatar.vue'

const props = withDefaults(
  defineProps<{
    post: Post
    formatTime?: (dateStr: string) => string
    contentClamp?: 3 | 6
  }>(),
  {
    formatTime: undefined,
    contentClamp: 6,
  },
)

function defaultFormatTime(dateStr: string): string {
  const now = Date.now()
  const diff = now - new Date(dateStr).getTime()
  const seconds = Math.floor(diff / 1000)
  if (seconds < 60) return 'just now'
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  if (days < 7) return `${days}d ago`
  return new Date(dateStr).toLocaleDateString()
}

function displayTime(dateStr: string): string {
  return props.formatTime ? props.formatTime(dateStr) : defaultFormatTime(dateStr)
}

function stripHtml(html: string): string {
  const div = document.createElement('div')
  div.innerHTML = html
  return div.textContent || ''
}
</script>

<template>
  <BaseCard hoverable class="!p-0">
    <!-- Post Header — avatar + name link to profile -->
    <div class="flex items-center gap-3 px-4 pt-4 pb-2">
      <router-link :to="`/users/${post.author.id}`">
        <BaseAvatar :src="post.author.avatar_url" :name="post.author.display_name" size="sm" />
      </router-link>
      <div class="flex-1 min-w-0">
        <router-link
          :to="`/users/${post.author.id}`"
          class="text-sm font-semibold text-foreground hover:text-brand-600 hover:underline"
        >
          {{ post.author.display_name }}
        </router-link>
        <div class="flex items-center gap-2 text-xs text-muted">
          <span>{{ displayTime(post.created_at) }}</span>
          <BaseBadge v-if="post.category_name" class="!text-[10px] !px-1.5 !py-0">{{
            post.category_name
          }}</BaseBadge>
        </div>
      </div>
    </div>

    <!-- Post Title & Content — link to post -->
    <router-link :to="`/forum/${post.id}`" class="block px-4 pb-3">
      <h2 class="text-base font-bold text-foreground mb-1">{{ post.title }}</h2>
      <p class="text-sm text-muted" :class="contentClamp === 3 ? 'line-clamp-3' : 'line-clamp-6'">
        {{ stripHtml(post.content) }}
      </p>
    </router-link>

    <!-- Keywords -->
    <div v-if="post.keywords?.length" class="px-4 pb-3 flex gap-1 flex-wrap">
      <BaseBadge v-for="kw in post.keywords.slice(0, 5)" :key="kw" variant="neutral">{{
        kw
      }}</BaseBadge>
    </div>

    <!-- Action Bar -->
    <div class="border-t border-border px-4 py-2.5 flex items-center">
      <span class="text-sm text-muted">
        {{ post.comment_count }} comment{{ post.comment_count !== 1 ? 's' : '' }}
      </span>
    </div>
  </BaseCard>
</template>

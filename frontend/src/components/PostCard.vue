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
        <div class="flex items-center gap-2">
          <router-link
            :to="`/users/${post.author.id}`"
            class="text-sm font-semibold text-foreground hover:text-brand-600 hover:underline"
          >
            {{ post.author.display_name }}
          </router-link>
          <span
            v-if="post.is_pinned"
            class="inline-flex items-center gap-1 text-xs font-medium text-amber-600"
          >
            <svg
              class="w-3 h-3"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
              stroke-linejoin="round"
            >
              <path d="M12 17v5" />
              <path
                d="M9 10.76a2 2 0 0 1-1.11 1.79l-1.78.9A2 2 0 0 0 5 15.24V16a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-.76a2 2 0 0 0-1.11-1.79l-1.78-.9A2 2 0 0 1 15 10.76V7a1 1 0 0 1 1-1 1 1 0 0 0 1-1V4a2 2 0 0 0-2-2H9a2 2 0 0 0-2 2v1a1 1 0 0 0 1 1 1 1 0 0 1 1 1z"
              />
            </svg>
            Pinned
          </span>
        </div>
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
    <div class="border-t border-border px-4 py-2.5 flex items-center gap-4">
      <span class="text-sm text-muted">
        {{ post.comment_count }} comment{{ post.comment_count !== 1 ? 's' : '' }}
      </span>
      <span class="text-sm text-muted flex items-center gap-1">
        <svg
          class="w-3.5 h-3.5"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          stroke-linecap="round"
          stroke-linejoin="round"
        >
          <path
            d="M2.062 12.348a1 1 0 0 1 0-.696 10.75 10.75 0 0 1 19.876 0 1 1 0 0 1 0 .696 10.75 10.75 0 0 1-19.876 0"
          />
          <circle cx="12" cy="12" r="3" />
        </svg>
        {{ post.view_count }}
      </span>
      <span v-if="post.last_comment_at" class="text-xs text-muted ml-auto">
        Last reply {{ displayTime(post.last_comment_at) }}
      </span>
    </div>
  </BaseCard>
</template>

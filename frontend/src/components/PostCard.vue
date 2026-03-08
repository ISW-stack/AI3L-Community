<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type { Post } from '@/types'
import BaseCard from '@/components/base/BaseCard.vue'
import BaseBadge from '@/components/base/BaseBadge.vue'
import BaseAvatar from '@/components/base/BaseAvatar.vue'
import { Pin, Eye, MessageCircle } from 'lucide-vue-next'

const { t } = useI18n()

const props = withDefaults(
  defineProps<{
    post: Post
    formatTime?: (dateStr: string) => string
    contentClamp?: 3 | 8
  }>(),
  {
    formatTime: undefined,
    contentClamp: 8,
  },
)

/** Extract the first <img src="..."> from HTML content */
const thumbnailUrl = computed(() => {
  const match = props.post.content.match(/<img[^>]+src=["']([^"']+)["']/)
  return match ? match[1] : null
})

function defaultFormatTime(dateStr: string): string {
  const now = Date.now()
  const diff = now - new Date(dateStr).getTime()
  const seconds = Math.floor(diff / 1000)
  if (seconds < 60) return t('post.card.timeFormat.justNow')
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return t('post.card.timeFormat.minutesAgo', { count: minutes })
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return t('post.card.timeFormat.hoursAgo', { count: hours })
  const days = Math.floor(hours / 24)
  if (days < 7) return t('post.card.timeFormat.daysAgo', { count: days })
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
    <!-- SIG context — shown above header when post belongs to a SIG -->
    <div v-if="post.sig_name" class="px-4 pt-3 pb-1">
      <router-link
        :to="`/sigs/${post.sig_id}`"
        class="text-xs font-medium text-brand-600 hover:text-brand-700 hover:underline"
      >
        {{ post.sig_name }}
      </router-link>
    </div>

    <!-- Post Header — avatar + name link to profile -->
    <div class="flex items-center gap-3 px-4 pb-2" :class="post.sig_name ? 'pt-1' : 'pt-4'">
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
            <Pin class="w-3 h-3" />
            {{ t('post.card.pinned') }}
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
      <h2 class="text-base font-bold text-foreground mb-1.5">{{ post.title }}</h2>

      <!-- Content area: text + optional thumbnail -->
      <div class="flex gap-4">
        <p
          class="flex-1 text-sm text-muted leading-relaxed content-preview"
          :class="contentClamp === 3 ? 'line-clamp-3' : 'line-clamp-8'"
        >
          {{ stripHtml(post.content) }}
        </p>
        <img
          v-if="thumbnailUrl"
          :src="thumbnailUrl"
          alt=""
          class="w-28 h-28 sm:w-36 sm:h-28 object-cover rounded-lg shrink-0 bg-surface-alt"
        />
      </div>
    </router-link>

    <!-- Keywords -->
    <div v-if="post.keywords?.length" class="px-4 pb-3 flex gap-1 flex-wrap">
      <BaseBadge v-for="kw in post.keywords.slice(0, 5)" :key="kw" variant="neutral">{{
        kw
      }}</BaseBadge>
    </div>

    <!-- Action Bar -->
    <div class="border-t border-border px-4 py-2.5 flex items-center gap-4">
      <span class="text-sm text-muted flex items-center gap-1">
        <MessageCircle class="w-3.5 h-3.5" />
        {{ post.comment_count }}
      </span>
      <span class="text-sm text-muted flex items-center gap-1">
        <Eye class="w-3.5 h-3.5" />
        {{ post.view_count }}
      </span>
      <span v-if="post.last_comment_at" class="text-xs text-muted ml-auto">
        {{ t('post.card.lastReply', { time: displayTime(post.last_comment_at) }) }}
      </span>
    </div>
  </BaseCard>
</template>

<style scoped>
.content-preview {
  position: relative;
  overflow: hidden;
}
.content-preview::after {
  content: '';
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 2rem;
  background: linear-gradient(transparent, var(--color-surface));
}
</style>

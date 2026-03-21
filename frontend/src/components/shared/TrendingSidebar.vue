<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import type { Post } from '@/types'
import BaseCard from '@/components/base/BaseCard.vue'

withDefaults(
  defineProps<{
    posts: Post[]
    title?: string
    linkPrefix?: string
  }>(),
  { title: undefined, linkPrefix: '/forum' },
)

const { t } = useI18n()
</script>

<template>
  <BaseCard v-if="posts.length > 0">
    <h3 class="text-sm font-semibold text-foreground mb-3">
      {{ title ?? t('common.trending') }}
    </h3>
    <ul class="space-y-3">
      <li v-for="post in posts" :key="post.id">
        <slot name="item" :post="post">
          <!-- Default rendering (forum-style) -->
          <router-link
            :to="`${linkPrefix}/${post.id}`"
            class="block hover:bg-surface-alt rounded-lg px-2 py-1.5 -mx-2 transition"
          >
            <p class="text-sm text-foreground font-medium line-clamp-2">{{ post.title }}</p>
            <div class="flex items-center gap-3 mt-1 text-xs text-muted">
              <span>{{ t('common.commentCount', { count: post.comment_count }) }}</span>
              <span>{{ t('common.viewCount', { count: post.view_count }) }}</span>
            </div>
          </router-link>
        </slot>
      </li>
    </ul>
  </BaseCard>
</template>

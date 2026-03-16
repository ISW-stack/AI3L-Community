<script setup lang="ts">
import type { Post } from '@/types'
import BaseBadge from '@/components/base/BaseBadge.vue'
import BaseCard from '@/components/base/BaseCard.vue'
import { MessageCircle } from 'lucide-vue-next'

defineProps<{
  question: Post
}>()

function formatDate(dateStr: string): string {
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
</script>

<template>
  <router-link :to="`/qa/${question.id}`" class="block">
    <BaseCard hoverable class="!p-0">
      <div class="flex items-start gap-4 p-4">
        <!-- Vote count (left side) -->
        <div class="flex flex-col items-center justify-center min-w-[50px] py-1">
          <span class="text-lg font-bold text-foreground tabular-nums">{{
            question.view_count
          }}</span>
          <span class="text-[10px] text-muted uppercase tracking-wide">views</span>
        </div>

        <!-- Answer count -->
        <div
          class="flex flex-col items-center justify-center min-w-[50px] py-1 rounded-lg"
          :class="question.best_answer_id ? 'bg-green-50 text-green-700' : 'text-muted'"
        >
          <span class="text-lg font-bold tabular-nums">{{ question.answer_count }}</span>
          <span class="text-[10px] uppercase tracking-wide">
            {{ question.answer_count === 1 ? 'answer' : 'answers' }}
          </span>
        </div>

        <!-- Title + meta (center) -->
        <div class="flex-1 min-w-0">
          <h3 class="text-base font-semibold text-foreground line-clamp-2 mb-1">
            {{ question.title }}
          </h3>
          <div class="flex items-center gap-2 flex-wrap">
            <BaseBadge
              v-if="question.best_answer_id"
              class="!text-[10px] !bg-green-100 !text-green-700"
            >
              Answered
            </BaseBadge>
            <BaseBadge v-else variant="neutral" class="!text-[10px]"> Unanswered </BaseBadge>
            <BaseBadge v-if="question.category_name" variant="neutral" class="!text-[10px]">
              {{ question.category_name }}
            </BaseBadge>
          </div>
          <!-- Keywords -->
          <div v-if="question.keywords?.length" class="flex gap-1 flex-wrap mt-2">
            <BaseBadge
              v-for="kw in question.keywords.slice(0, 5)"
              :key="kw"
              variant="neutral"
              class="!text-[10px] !px-1.5 !py-0"
            >
              {{ kw }}
            </BaseBadge>
          </div>
          <!-- Author + date -->
          <div class="flex items-center gap-2 mt-2 text-xs text-muted">
            <span>{{ question.author.display_name }}</span>
            <span>{{ formatDate(question.created_at) }}</span>
            <span v-if="question.comment_count > 0" class="flex items-center gap-0.5">
              <MessageCircle class="w-3 h-3" />
              {{ question.comment_count }}
            </span>
          </div>
        </div>
      </div>
    </BaseCard>
  </router-link>
</template>

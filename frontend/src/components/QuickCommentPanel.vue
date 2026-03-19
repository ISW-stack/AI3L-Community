<script setup lang="ts">
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@/stores/auth'
import { listComments, createComment } from '@/api/comments'
import { getErrorMessage } from '@/utils/error'
import { useToastStore } from '@/stores/toast'
import type { Comment } from '@/types'
import BaseAvatar from '@/components/base/BaseAvatar.vue'
import { Send, Loader2 } from 'lucide-vue-next'

const props = defineProps<{
  postId: string
  allowComments: boolean
}>()

const emit = defineEmits<{
  (e: 'commented'): void
}>()

const { t } = useI18n()
const auth = useAuthStore()
const toast = useToastStore()

const comments = ref<Comment[]>([])
const loading = ref(true)
const newComment = ref('')
const saving = ref(false)

const canComment = computed(() => auth.isAuthenticated && !auth.isGuest && props.allowComments)

async function fetchRecentComments() {
  loading.value = true
  try {
    const data = await listComments(props.postId, { page: 1, page_size: 3 })
    comments.value = data.comments
  } catch {
    comments.value = []
  } finally {
    loading.value = false
  }
}

async function submitComment() {
  const content = newComment.value.trim()
  if (!content || saving.value) return

  saving.value = true
  try {
    const created = await createComment(props.postId, { content })
    // Prepend the new comment (newest first)
    comments.value.unshift(created)
    // Keep only 3 visible
    if (comments.value.length > 3) {
      comments.value = comments.value.slice(0, 3)
    }
    newComment.value = ''
    emit('commented')
  } catch (e: unknown) {
    toast.show(getErrorMessage(e, t('post.quickComment.submitError')), 'error')
  } finally {
    saving.value = false
  }
}

function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    submitComment()
  }
}

function formatCommentTime(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime()
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

// Fetch on mount
fetchRecentComments()
</script>

<template>
  <div class="border-t border-border px-4 py-3 space-y-3">
    <!-- Loading -->
    <div v-if="loading" class="flex justify-center py-2">
      <Loader2 class="w-4 h-4 animate-spin text-muted" />
    </div>

    <!-- Comments list -->
    <template v-else>
      <div v-if="comments.length === 0 && !canComment" class="text-xs text-muted text-center py-1">
        {{ t('post.quickComment.noComments') }}
      </div>

      <div v-for="comment in comments" :key="comment.id" class="flex gap-2">
        <router-link :to="`/users/${comment.author.id}`" class="shrink-0">
          <BaseAvatar
            :src="comment.author.avatar_url"
            :name="comment.author.display_name"
            size="xs"
          />
        </router-link>
        <div class="min-w-0 flex-1">
          <div class="bg-surface-alt rounded-xl px-3 py-1.5">
            <router-link
              :to="`/users/${comment.author.id}`"
              class="text-xs font-semibold text-foreground hover:underline"
            >
              {{ comment.author.display_name }}
            </router-link>
            <p class="text-sm text-foreground break-words">{{ comment.content }}</p>
          </div>
          <span class="text-[10px] text-muted ml-3">{{
            formatCommentTime(comment.created_at)
          }}</span>
        </div>
      </div>
    </template>

    <!-- Comment input -->
    <div v-if="canComment" class="flex gap-2 items-start">
      <BaseAvatar
        :src="auth.user?.avatar_url"
        :name="auth.user?.display_name || ''"
        size="xs"
        class="shrink-0 mt-0.5"
      />
      <div class="flex-1 relative">
        <textarea
          v-model="newComment"
          :placeholder="t('post.quickComment.placeholder')"
          rows="1"
          class="w-full rounded-full bg-surface-alt border-none px-4 py-2 text-sm text-foreground placeholder:text-muted resize-none focus:outline-none focus:ring-2 focus:ring-brand-500"
          :disabled="saving"
          @keydown="handleKeydown"
        />
      </div>
      <button
        type="button"
        class="shrink-0 mt-0.5 p-2 rounded-full text-brand-600 hover:bg-brand-50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        :disabled="!newComment.trim() || saving"
        @click="submitComment"
      >
        <Loader2 v-if="saving" class="w-4 h-4 animate-spin" />
        <Send v-else class="w-4 h-4" />
      </button>
    </div>

    <!-- Guest prompt -->
    <div
      v-else-if="!auth.isAuthenticated || auth.isGuest"
      class="text-xs text-muted text-center py-1"
    >
      <router-link to="/login" class="text-brand-600 hover:underline">
        {{ t('post.quickComment.loginToComment') }}
      </router-link>
    </div>

    <!-- Comments disabled -->
    <div v-else-if="!allowComments" class="text-xs text-muted text-center py-1">
      {{ t('post.quickComment.disabled') }}
    </div>
  </div>
</template>

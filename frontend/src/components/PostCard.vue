<script setup lang="ts">
import { computed, ref, onMounted, watch, nextTick } from 'vue'
import { useI18n } from 'vue-i18n'
import DOMPurify from 'dompurify'
import type { Post } from '@/types'
import type { CoAuthor } from '@/types/coauthor'
import { useAuthStore } from '@/stores/auth'
import { togglePostReaction } from '@/api/posts'
import BaseCard from '@/components/base/BaseCard.vue'
import BaseBadge from '@/components/base/BaseBadge.vue'
import BaseAvatar from '@/components/base/BaseAvatar.vue'
import { Pin, Eye, MessageCircle, Quote, HelpCircle, MessageSquare } from 'lucide-vue-next'
import ReactionPicker from '@/components/ReactionPicker.vue'
import CoAuthorBadges from '@/components/post/CoAuthorBadges.vue'

const { t } = useI18n()
const auth = useAuthStore()

const PREVIEW_ALLOWED_TAGS = [
  'p',
  'br',
  'strong',
  'b',
  'em',
  'i',
  'ul',
  'ol',
  'li',
  'blockquote',
  'h1',
  'h2',
  'h3',
  'h4',
  'h5',
  'h6',
  'code',
  'pre',
]

const props = withDefaults(
  defineProps<{
    post: Post
    coAuthors?: CoAuthor[]
    formatTime?: (dateStr: string) => string
    maxPreviewLines?: number
  }>(),
  {
    coAuthors: () => [],
    formatTime: undefined,
    maxPreviewLines: 15,
  },
)

const isQuestion = computed(() => props.post.type === 'question')
const postLink = computed(() => isQuestion.value ? `/qa/${props.post.id}` : `/forum/${props.post.id}`)
const acceptedCoAuthors = computed(() =>
  props.coAuthors.filter((ca) => ca.status === 'ACCEPTED'),
)

const emit = defineEmits<{
  (e: 'reactionToggled', post: Post): void
}>()

// Show more / show less
const isExpanded = ref(false)
const isOverflowing = ref(false)
const contentRef = ref<HTMLElement | null>(null)

const maxHeight = computed(() => `${props.maxPreviewLines * 1.5}rem`)

function checkOverflow() {
  nextTick(() => {
    if (contentRef.value) {
      isOverflowing.value = contentRef.value.scrollHeight > contentRef.value.clientHeight + 1
    }
  })
}

function toggleExpanded() {
  isExpanded.value = !isExpanded.value
}

onMounted(checkOverflow)
watch(
  () => props.post.content,
  () => {
    isExpanded.value = false
    checkOverflow()
  },
)

// Sanitized HTML for preview (strips images, links text only, allows basic formatting)
const sanitizedPreviewHtml = computed(() => {
  return DOMPurify.sanitize(props.post.content, {
    ALLOWED_TAGS: PREVIEW_ALLOWED_TAGS,
    ALLOWED_ATTR: [],
  })
})

// Local optimistic reactions state
const localReactions = ref<Record<string, string[]> | null>(null)
const reactionsData = computed(() => localReactions.value ?? props.post.reactions)

async function handleReaction(reaction: string) {
  if (!auth.user?.id || auth.isGuest) return

  // Optimistic update
  const current = { ...(reactionsData.value ?? {}) }
  const list = [...(current[reaction] ?? [])]
  const idx = list.indexOf(auth.user.id)
  if (idx >= 0) {
    list.splice(idx, 1)
  } else {
    list.push(auth.user.id)
  }
  if (list.length === 0) {
    delete current[reaction]
  } else {
    current[reaction] = list
  }
  localReactions.value = Object.keys(current).length > 0 ? current : null

  try {
    const updated = await togglePostReaction(props.post.id, reaction)
    localReactions.value = updated.reactions
    emit('reactionToggled', updated)
  } catch {
    // Rollback on error
    localReactions.value = null
  }
}

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
</script>

<template>
  <BaseCard hoverable class="!p-0">
    <!-- SIG context — shown above header when post belongs to a SIG -->
    <div v-if="post.sig_id && post.sig_name" class="px-4 pt-3 pb-1">
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
        <div class="flex items-center gap-2 flex-wrap">
          <router-link
            :to="`/users/${post.author.id}`"
            class="text-sm font-semibold text-foreground hover:text-brand-600 hover:underline"
          >
            {{ post.author.display_name }}
          </router-link>
          <CoAuthorBadges v-if="acceptedCoAuthors.length > 0" :co-authors="acceptedCoAuthors" />
          <span
            v-if="post.is_pinned"
            class="inline-flex items-center gap-1 text-xs font-medium text-amber-600"
          >
            <Pin class="w-3 h-3" />
            {{ t('post.card.pinned') }}
          </span>
          <BaseBadge
            v-if="isQuestion"
            class="!text-[10px] !px-1.5 !py-0 !bg-purple-100 !text-purple-700"
          >
            <HelpCircle class="w-3 h-3 mr-0.5 inline" />
            Question
          </BaseBadge>
        </div>
        <div class="flex items-center gap-2 text-xs text-muted">
          <span>{{ displayTime(post.created_at) }}</span>
          <BaseBadge v-if="post.category_name" class="!text-[10px] !px-1.5 !py-0">{{
            post.category_name
          }}</BaseBadge>
        </div>
      </div>
    </div>

    <!-- Post Title — link to post -->
    <router-link :to="postLink" class="block px-4">
      <h2 class="text-base font-bold text-foreground mb-1.5">{{ post.title }}</h2>
    </router-link>

    <!-- Content preview — sanitized HTML with show more/less -->
    <div class="px-4 pb-2">
      <div
        ref="contentRef"
        class="prose prose-sm max-w-none break-words text-muted post-preview-content"
        :class="{ 'is-collapsed': !isExpanded && isOverflowing }"
        :style="!isExpanded ? { maxHeight: maxHeight, overflow: 'hidden' } : {}"
        v-html="sanitizedPreviewHtml"
      ></div>
      <button
        v-if="isOverflowing || isExpanded"
        type="button"
        class="text-sm font-medium text-brand-600 hover:text-brand-700 hover:underline mt-1"
        @click.stop.prevent="toggleExpanded"
      >
        {{ isExpanded ? t('post.card.showLess') : t('post.card.showMore') }}
      </button>
    </div>

    <!-- Full-width image below content -->
    <router-link v-if="thumbnailUrl" :to="postLink" class="block">
      <img
        :src="thumbnailUrl"
        :alt="post.title || 'Post image'"
        loading="lazy"
        class="w-full max-h-80 object-cover bg-surface-alt"
      />
    </router-link>

    <!-- Keywords -->
    <div v-if="post.keywords?.length" class="px-4 pb-3 pt-2 flex gap-1 flex-wrap">
      <BaseBadge v-for="kw in post.keywords.slice(0, 5)" :key="kw" variant="neutral">{{
        kw
      }}</BaseBadge>
    </div>

    <!-- Reactions -->
    <div
      v-if="auth.isAuthenticated || (reactionsData && Object.keys(reactionsData).length)"
      class="px-4 pb-2"
    >
      <ReactionPicker
        :reactions="reactionsData"
        :user-id="auth.user?.id ?? null"
        :readonly="!auth.isAuthenticated || auth.isGuest"
        @toggle="handleReaction"
      />
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
      <span v-if="post.citation_count > 0" class="text-sm text-muted flex items-center gap-1">
        <Quote class="w-3.5 h-3.5" />
        {{ post.citation_count }}
      </span>
      <span
        v-if="isQuestion"
        class="text-sm flex items-center gap-1"
        :class="post.best_answer_id ? 'text-green-600' : 'text-muted'"
      >
        <MessageSquare class="w-3.5 h-3.5" />
        {{ t('qa.answerCount', { count: post.answer_count }, post.answer_count) }}
      </span>
      <span v-if="post.last_comment_at" class="text-xs text-muted ml-auto">
        {{ t('post.card.lastReply', { time: displayTime(post.last_comment_at) }) }}
      </span>
    </div>
  </BaseCard>
</template>

<style scoped>
.is-collapsed {
  position: relative;
}
.is-collapsed::after {
  content: '';
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 3rem;
  background: linear-gradient(transparent, var(--color-surface));
  pointer-events: none;
}
.post-preview-content :deep(p) {
  margin-top: 0.25em;
  margin-bottom: 0.25em;
}
.post-preview-content :deep(ul),
.post-preview-content :deep(ol) {
  margin-top: 0.25em;
  margin-bottom: 0.25em;
}
.post-preview-content :deep(blockquote) {
  margin-top: 0.5em;
  margin-bottom: 0.5em;
}
</style>

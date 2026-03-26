<script setup lang="ts">
import { ref, computed, watch, onMounted, defineAsyncComponent } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useLocale } from '@/composables/useLocale'
import { formatDateTime } from '@/utils/date'
import { useAuthStore } from '@/stores/auth'
import { useToastStore } from '@/stores/toast'
import { sanitizeHtml } from '@/utils/sanitize'
import type { Post, Comment } from '@/types'
import { getPost, deletePost as apiDeletePost } from '@/api/posts'
import { listComments, createComment } from '@/api/comments'
import { markBestAnswer, unmarkBestAnswer, voteOnAnswer, getUserVotes } from '@/api/qa'
import { getErrorMessage } from '@/utils/error'
import { renderMentions, isContentEmpty } from '@/utils/html'
import BaseCard from '@/components/base/BaseCard.vue'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseAlert from '@/components/base/BaseAlert.vue'
import BaseBadge from '@/components/base/BaseBadge.vue'
import BaseModal from '@/components/base/BaseModal.vue'
import BaseAvatar from '@/components/base/BaseAvatar.vue'
import BasePagination from '@/components/base/BasePagination.vue'
import SkeletonLoader from '@/components/SkeletonLoader.vue'
import EmptyState from '@/components/EmptyState.vue'
import BaseBreadcrumb from '@/components/base/BaseBreadcrumb.vue'
import VoteButtons from '@/components/qa/VoteButtons.vue'
import BestAnswerBadge from '@/components/qa/BestAnswerBadge.vue'
import { ArrowLeft } from 'lucide-vue-next'
const TiptapEditor = defineAsyncComponent(() => import('@/components/TiptapEditor.vue'))

const { t, currentLocale: locale } = useLocale()
const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const toast = useToastStore()

const postId = computed(() => route.params.id as string)

const post = ref<Post | null>(null)
const loading = ref(true)
const answers = ref<Comment[]>([])
const answersTotal = ref(0)
const answersPage = ref(1)
const answersTotalPages = ref(1)
const PAGE_SIZE = 20

// Vote state: commentId -> { user_vote, score }
const voteState = ref<Record<string, { user_vote: -1 | 0 | 1; score: number }>>({})

const newAnswer = ref('')
const answerSaving = ref(false)
const answerMessage = ref('')

const showDeleteConfirm = ref(false)

const isAuthor = computed(() => post.value && auth.user && post.value.author.id === auth.user.id)
const canModify = computed(() => isAuthor.value || auth.isAdmin)

const breadcrumbItems = computed(() => [
  { label: t('breadcrumb.home'), to: '/' },
  { label: t('qa.title'), to: '/qa' },
  { label: post.value?.title || '...' },
])

// Sort answers: best answer first, then by vote score desc, then by date
const sortedAnswers = computed(() => {
  const bestId = post.value?.best_answer_id
  return [...answers.value].sort((a, b) => {
    // Best answer first
    if (a.id === bestId) return -1
    if (b.id === bestId) return 1
    // Then by vote score desc
    const scoreA = voteState.value[a.id]?.score ?? 0
    const scoreB = voteState.value[b.id]?.score ?? 0
    if (scoreB !== scoreA) return scoreB - scoreA
    // Then by date
    return new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
  })
})

async function fetchPost() {
  loading.value = true
  try {
    post.value = await getPost(postId.value)
  } catch (e: unknown) {
    post.value = null
    toast.show(getErrorMessage(e, t('qa.loadQuestionError')), 'error')
  } finally {
    loading.value = false
  }
}

async function fetchAnswers() {
  try {
    const data = await listComments(postId.value, {
      page: answersPage.value,
      page_size: PAGE_SIZE,
      root_only: true,
    })
    // F-12: Backend now filters to root-only answers with correct total
    answers.value = data.comments
    answersTotal.value = data.total ?? 0
    answersTotalPages.value = Math.ceil((data.total ?? 0) / PAGE_SIZE)
    // Initialize vote state for answers
    for (const a of answers.value) {
      if (!voteState.value[a.id]) {
        voteState.value[a.id] = { user_vote: 0, score: a.vote_score ?? 0 }
      }
    }
  } catch (e: unknown) {
    toast.show(getErrorMessage(e, t('qa.loadAnswersError')), 'error')
  }
}

async function fetchUserVotes() {
  if (!auth.isAuthenticated || auth.isGuest) return
  try {
    const votes = await getUserVotes(postId.value)
    for (const v of votes) {
      if (voteState.value[v.comment_id]) {
        voteState.value[v.comment_id].user_vote = v.vote
      }
    }
  } catch {
    /* silent - votes are non-critical */
  }
}

async function goToAnswersPage(p: number) {
  answersPage.value = p
  await fetchAnswers()
  await fetchUserVotes()
}

async function submitAnswer() {
  if (isContentEmpty(newAnswer.value)) return
  answerSaving.value = true
  answerMessage.value = ''
  try {
    await createComment(postId.value, { content: newAnswer.value })
    newAnswer.value = ''
    await fetchAnswers()
    if (post.value) post.value.answer_count++
  } catch (e: unknown) {
    answerMessage.value = getErrorMessage(e, t('qa.postAnswerError'))
  } finally {
    answerSaving.value = false
  }
}

async function handleVote(commentId: string, value: -1 | 0 | 1) {
  // Optimistic update
  const prev = voteState.value[commentId] ?? { user_vote: 0, score: 0 }
  const oldVote = prev.user_vote
  const scoreDiff = value - oldVote
  voteState.value[commentId] = {
    user_vote: value,
    score: prev.score + scoreDiff,
  }
  try {
    await voteOnAnswer(commentId, value)
  } catch (e: unknown) {
    // Rollback
    voteState.value[commentId] = prev
    toast.show(getErrorMessage(e, t('qa.voteError')), 'error')
  }
}

async function handleMarkBest(commentId: string) {
  if (!post.value) return
  try {
    await markBestAnswer(postId.value, commentId)
    post.value.best_answer_id = commentId
    toast.show(t('qa.bestAnswerMarked'), 'success')
  } catch (e: unknown) {
    toast.show(getErrorMessage(e, t('qa.bestAnswerMarkError')), 'error')
  }
}

async function handleUnmarkBest() {
  if (!post.value) return
  try {
    await unmarkBestAnswer(postId.value)
    post.value.best_answer_id = null
    toast.show(t('qa.bestAnswerUnmarked'), 'success')
  } catch (e: unknown) {
    toast.show(getErrorMessage(e, t('qa.bestAnswerUnmarkError')), 'error')
  }
}

async function deleteQuestion() {
  try {
    await apiDeletePost(postId.value)
    router.push('/qa')
  } catch (e: unknown) {
    toast.show(getErrorMessage(e, t('qa.deleteError')), 'error')
  } finally {
    showDeleteConfirm.value = false
  }
}

function formatDate(dateStr: string): string {
  return formatDateTime(dateStr, locale.value)
}

function getUserVote(commentId: string): -1 | 0 | 1 {
  return voteState.value[commentId]?.user_vote ?? 0
}

function getScore(commentId: string): number {
  return voteState.value[commentId]?.score ?? 0
}

function isOwnAnswer(comment: Comment): boolean {
  return !!(auth.user && comment.author.id === auth.user.id)
}

onMounted(async () => {
  await Promise.all([fetchPost(), fetchAnswers()])
  await fetchUserVotes()
})

// Re-fetch when route param changes (component reuse)
watch(postId, async () => {
  post.value = null
  answers.value = []
  voteState.value = {}
  answersPage.value = 1
  newAnswer.value = ''
  answerMessage.value = ''
  await Promise.all([fetchPost(), fetchAnswers()])
  await fetchUserVotes()
})
</script>

<template>
  <div class="max-w-4xl mx-auto py-6 px-4">
    <router-link
      v-if="loading || !post"
      to="/qa"
      class="flex items-center gap-1 text-sm text-muted hover:text-foreground mb-4"
    >
      <ArrowLeft :size="16" />
      {{ t('qa.backToList') }}
    </router-link>
    <SkeletonLoader v-if="loading" :lines="1" variant="card" />

    <div v-else-if="!post" class="text-center py-12">
      <p class="text-muted mb-4">{{ t('qa.questionNotFound') }}</p>
    </div>

    <template v-else>
      <BaseBreadcrumb :items="breadcrumbItems" />

      <!-- Question Card -->
      <BaseCard padding="lg" class="mb-6">
        <div class="flex items-start gap-3 mb-4">
          <router-link :to="`/users/${post.author.id}`">
            <BaseAvatar :src="post.author.avatar_url" :name="post.author.display_name" size="md" />
          </router-link>
          <div class="flex-1 min-w-0">
            <h1 class="text-2xl font-bold text-foreground mb-1">{{ post.title }}</h1>
            <div class="flex items-center gap-3 text-sm text-muted flex-wrap">
              <router-link
                :to="`/users/${post.author.id}`"
                class="font-medium hover:text-brand-600 hover:underline"
              >
                {{ post.author.display_name }}
              </router-link>
              <span>{{ formatDate(post.created_at) }}</span>
              <BaseBadge v-if="post.category_name">{{ post.category_name }}</BaseBadge>
              <BaseBadge v-if="post.best_answer_id" class="!bg-success-100 !text-success-700">
                {{ t('qa.answered') }}
              </BaseBadge>
              <BaseBadge v-else variant="neutral">{{ t('qa.unanswered') }}</BaseBadge>
            </div>
          </div>
          <div v-if="canModify" class="flex gap-2 shrink-0">
            <button
              class="text-sm text-danger-600 hover:underline"
              @click="showDeleteConfirm = true"
            >
              {{ t('qa.delete') }}
            </button>
          </div>
        </div>

        <!-- Question content -->
        <div
          class="prose prose-sm max-w-none break-words text-foreground/80 mb-4"
          v-html="sanitizeHtml(post.content)"
        ></div>

        <!-- Keywords -->
        <div v-if="post.keywords?.length" class="flex gap-1 flex-wrap mb-3">
          <BaseBadge v-for="kw in post.keywords" :key="kw" variant="neutral">{{ kw }}</BaseBadge>
        </div>

        <div class="flex items-center gap-4 border-t border-border pt-3 text-sm text-muted">
          <span>{{
            t('qa.answerCountLabel', { count: post.answer_count }, post.answer_count)
          }}</span>
          <span>{{ t('qa.viewCountLabel', { count: post.view_count }) }}</span>
        </div>
      </BaseCard>

      <!-- Answers Section -->
      <BaseCard padding="lg">
        <h3 class="text-lg font-semibold text-foreground mb-4">
          {{ t('qa.answersSection', { count: answersTotal }, answersTotal) }}
        </h3>

        <EmptyState v-if="sortedAnswers.length === 0" :message="t('qa.noAnswers')" />

        <div class="space-y-4">
          <div
            v-for="answer in sortedAnswers"
            :key="answer.id"
            class="group border-b border-border last:border-0 pb-4 last:pb-0"
            :class="
              answer.id === post.best_answer_id ? 'bg-success-50/50 -mx-4 px-4 py-3 rounded-lg' : ''
            "
          >
            <div class="flex items-start gap-3">
              <!-- Vote buttons -->
              <VoteButtons
                :comment-id="answer.id"
                :score="getScore(answer.id)"
                :user-vote="getUserVote(answer.id)"
                :disabled="isOwnAnswer(answer) || !auth.isAuthenticated || auth.isGuest"
                @vote="(v) => handleVote(answer.id, v)"
              />

              <div class="flex-1 min-w-0">
                <!-- Best answer badge -->
                <BestAnswerBadge
                  v-if="answer.id === post.best_answer_id || isAuthor"
                  :is-owner="!!isAuthor"
                  :is-best="answer.id === post.best_answer_id"
                  class="mb-2"
                  @mark="handleMarkBest(answer.id)"
                  @unmark="handleUnmarkBest"
                />

                <!-- Answer content -->
                <div
                  class="prose prose-sm max-w-none break-words text-foreground/80 mb-2"
                  v-html="renderMentions(sanitizeHtml(answer.content), answer.mentions)"
                ></div>

                <!-- Answer meta -->
                <div class="flex items-center gap-2 text-xs text-muted">
                  <router-link
                    :to="`/users/${answer.author.id}`"
                    class="flex items-center gap-1 hover:text-brand-600"
                  >
                    <BaseAvatar
                      :src="answer.author.avatar_url"
                      :name="answer.author.display_name"
                      size="xs"
                    />
                    <span>{{ answer.author.display_name }}</span>
                  </router-link>
                  <span>{{ formatDate(answer.created_at) }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <BasePagination
          v-if="answersTotalPages > 1"
          :current-page="answersPage"
          :total-pages="answersTotalPages"
          class="mt-4"
          @update:current-page="goToAnswersPage"
        />

        <!-- Answer input -->
        <div v-if="auth.isAuthenticated && !auth.isGuest" class="mt-6 border-t border-border pt-4">
          <h4 class="text-sm font-semibold text-foreground mb-2">{{ t('qa.yourAnswer') }}</h4>
          <BaseAlert v-if="answerMessage" type="error" class="mb-2">{{ answerMessage }}</BaseAlert>
          <div class="mb-2">
            <TiptapEditor v-model="newAnswer" />
          </div>
          <BaseButton
            :loading="answerSaving"
            :disabled="isContentEmpty(newAnswer)"
            @click="submitAnswer"
          >
            {{ t('qa.postAnswer') }}
          </BaseButton>
        </div>
      </BaseCard>
    </template>

    <!-- Delete Confirmation -->
    <BaseModal v-model="showDeleteConfirm" :title="t('qa.deleteQuestion')" size="sm">
      <p class="text-sm text-muted">
        {{ t('qa.deleteQuestionConfirm') }}
      </p>
      <template #footer>
        <BaseButton variant="secondary" @click="showDeleteConfirm = false">{{
          t('common.cancel')
        }}</BaseButton>
        <BaseButton variant="danger" @click="deleteQuestion">{{ t('common.delete') }}</BaseButton>
      </template>
    </BaseModal>
  </div>
</template>

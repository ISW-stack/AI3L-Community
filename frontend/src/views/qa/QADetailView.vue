<script setup lang="ts">
import { ref, computed, onMounted, defineAsyncComponent } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useToastStore } from '@/stores/toast'
import DOMPurify from 'dompurify'
import type { Post, Comment } from '@/types'
import type { CommentVote } from '@/types/qa'
import { getPost, deletePost as apiDeletePost } from '@/api/posts'
import { listComments, createComment } from '@/api/comments'
import { markBestAnswer, unmarkBestAnswer, voteOnAnswer } from '@/api/qa'
import { getErrorMessage } from '@/utils/error'
import { renderMentions } from '@/utils/html'
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
const TiptapEditor = defineAsyncComponent(() => import('@/components/TiptapEditor.vue'))

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
  { label: 'Home', to: '/' },
  { label: 'Q&A', to: '/qa' },
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
    return new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
  })
})

async function fetchPost() {
  loading.value = true
  try {
    post.value = await getPost(postId.value)
  } catch (e: unknown) {
    post.value = null
    toast.show(getErrorMessage(e, 'Failed to load question.'), 'error')
  } finally {
    loading.value = false
  }
}

async function fetchAnswers() {
  try {
    const data = await listComments(postId.value, {
      page: answersPage.value,
      page_size: PAGE_SIZE,
    })
    // Only root-level comments are "answers" in Q&A
    answers.value = data.comments.filter((c) => !c.parent_id)
    answersTotal.value = answers.value.length
    answersTotalPages.value = Math.ceil((data.total ?? answers.value.length) / PAGE_SIZE)
    // Initialize vote state for answers
    for (const a of answers.value) {
      if (!voteState.value[a.id]) {
        voteState.value[a.id] = { user_vote: 0, score: 0 }
      }
    }
  } catch (e: unknown) {
    toast.show(getErrorMessage(e, 'Failed to load answers.'), 'error')
  }
}

function goToAnswersPage(p: number) {
  answersPage.value = p
  fetchAnswers()
}

async function submitAnswer() {
  if (!newAnswer.value.trim()) return
  answerSaving.value = true
  answerMessage.value = ''
  try {
    await createComment(postId.value, { content: newAnswer.value })
    newAnswer.value = ''
    await fetchAnswers()
    if (post.value) post.value.answer_count++
  } catch (e: unknown) {
    answerMessage.value = getErrorMessage(e, 'Failed to post answer.')
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
    toast.show(getErrorMessage(e, 'Failed to vote.'), 'error')
  }
}

async function handleMarkBest(commentId: string) {
  if (!post.value) return
  try {
    await markBestAnswer(postId.value, commentId)
    post.value.best_answer_id = commentId
    toast.show('Best answer marked.', 'success')
  } catch (e: unknown) {
    toast.show(getErrorMessage(e, 'Failed to mark best answer.'), 'error')
  }
}

async function handleUnmarkBest() {
  if (!post.value) return
  try {
    await unmarkBestAnswer(postId.value)
    post.value.best_answer_id = null
    toast.show('Best answer unmarked.', 'success')
  } catch (e: unknown) {
    toast.show(getErrorMessage(e, 'Failed to unmark best answer.'), 'error')
  }
}

async function deleteQuestion() {
  try {
    await apiDeletePost(postId.value)
    router.push('/qa')
  } catch (e: unknown) {
    toast.show(getErrorMessage(e, 'Failed to delete question.'), 'error')
  } finally {
    showDeleteConfirm.value = false
  }
}

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleString()
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

onMounted(() => {
  fetchPost()
  fetchAnswers()
})
</script>

<template>
  <div class="max-w-4xl mx-auto py-6 px-4">
    <SkeletonLoader v-if="loading" :lines="1" variant="card" />

    <div v-else-if="!post" class="text-center py-12">
      <p class="text-muted mb-4">Question not found.</p>
      <router-link to="/qa" class="text-brand-600 hover:underline">Back to Q&A</router-link>
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
              <BaseBadge
                v-if="post.best_answer_id"
                class="!bg-green-100 !text-green-700"
              >
                Answered
              </BaseBadge>
              <BaseBadge v-else variant="neutral">Unanswered</BaseBadge>
            </div>
          </div>
          <div v-if="canModify" class="flex gap-2 shrink-0">
            <button
              class="text-sm text-danger-600 hover:underline"
              @click="showDeleteConfirm = true"
            >
              Delete
            </button>
          </div>
        </div>

        <!-- Question content -->
        <div
          class="prose prose-sm max-w-none break-words text-foreground/80 mb-4"
          v-html="DOMPurify.sanitize(post.content)"
        ></div>

        <!-- Keywords -->
        <div v-if="post.keywords?.length" class="flex gap-1 flex-wrap mb-3">
          <BaseBadge v-for="kw in post.keywords" :key="kw" variant="neutral">{{ kw }}</BaseBadge>
        </div>

        <div class="flex items-center gap-4 border-t border-border pt-3 text-sm text-muted">
          <span>{{ post.answer_count }} answer{{ post.answer_count !== 1 ? 's' : '' }}</span>
          <span>{{ post.view_count }} views</span>
        </div>
      </BaseCard>

      <!-- Answers Section -->
      <BaseCard padding="lg">
        <h3 class="text-lg font-semibold text-foreground mb-4">
          {{ answersTotal }} Answer{{ answersTotal !== 1 ? 's' : '' }}
        </h3>

        <EmptyState
          v-if="sortedAnswers.length === 0"
          message="No answers yet. Be the first to answer!"
        />

        <div class="space-y-4">
          <div
            v-for="answer in sortedAnswers"
            :key="answer.id"
            class="group border-b border-border last:border-0 pb-4 last:pb-0"
            :class="answer.id === post.best_answer_id ? 'bg-green-50/50 -mx-4 px-4 py-3 rounded-lg' : ''"
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
                  v-html="renderMentions(DOMPurify.sanitize(answer.content), answer.mentions)"
                ></div>

                <!-- Answer meta -->
                <div class="flex items-center gap-2 text-xs text-muted">
                  <router-link :to="`/users/${answer.author.id}`" class="flex items-center gap-1 hover:text-brand-600">
                    <BaseAvatar :src="answer.author.avatar_url" :name="answer.author.display_name" size="xs" />
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
        <div
          v-if="auth.isAuthenticated && !auth.isGuest"
          class="mt-6 border-t border-border pt-4"
        >
          <h4 class="text-sm font-semibold text-foreground mb-2">Your Answer</h4>
          <BaseAlert v-if="answerMessage" type="error" class="mb-2">{{ answerMessage }}</BaseAlert>
          <textarea
            v-model="newAnswer"
            rows="4"
            placeholder="Write your answer..."
            class="w-full min-h-[100px] px-3 py-2 border border-border rounded-lg focus:ring-2 focus:ring-brand-500 focus:border-transparent outline-none text-sm text-foreground mb-2"
          ></textarea>
          <BaseButton
            :loading="answerSaving"
            :disabled="!newAnswer.trim()"
            @click="submitAnswer"
          >
            Post Answer
          </BaseButton>
        </div>
      </BaseCard>
    </template>

    <!-- Delete Confirmation -->
    <BaseModal v-model="showDeleteConfirm" title="Delete Question" size="sm">
      <p class="text-sm text-muted">
        Are you sure you want to delete this question? This action cannot be undone.
      </p>
      <template #footer>
        <BaseButton variant="secondary" @click="showDeleteConfirm = false">Cancel</BaseButton>
        <BaseButton variant="danger" @click="deleteQuestion">Delete</BaseButton>
      </template>
    </BaseModal>
  </div>
</template>

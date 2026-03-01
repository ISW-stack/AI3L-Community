<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import type { Post, HistoryItem, Comment } from '@/types'
import { getPost, updatePost, deletePost as apiDeletePost, getPostHistory } from '@/api/posts'
import {
  listComments,
  createComment,
  deleteComment as apiDeleteComment,
  toggleReaction as apiToggleReaction,
} from '@/api/comments'
import { createReport } from '@/api/reports'
import DOMPurify from 'dompurify'
import TiptapEditor from '@/components/TiptapEditor.vue'
import BaseCard from '@/components/base/BaseCard.vue'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseAlert from '@/components/base/BaseAlert.vue'
import BaseBadge from '@/components/base/BaseBadge.vue'
import BaseModal from '@/components/base/BaseModal.vue'
import BaseInput from '@/components/base/BaseInput.vue'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const post = ref<Post | null>(null)
const comments = ref<Comment[]>([])
const commentsTotal = ref(0)
const history = ref<HistoryItem[]>([])
const loading = ref(true)
const showHistory = ref(false)

const editing = ref(false)
const editTitle = ref('')
const editContent = ref('')
const editSaving = ref(false)
const editMessage = ref('')

const newComment = ref('')
const replyTo = ref<Comment | null>(null)
const commentSaving = ref(false)
const commentMessage = ref('')

const postId = computed(() => route.params.id as string)
const isAuthor = computed(() => post.value && auth.user && post.value.author.id === auth.user.id)
const canModify = computed(() => isAuthor.value || auth.isAdmin)

async function fetchPost() {
  loading.value = true
  try {
    post.value = await getPost(postId.value)
  } catch {
    post.value = null
  } finally {
    loading.value = false
  }
}

async function fetchComments() {
  try {
    const data = await listComments(postId.value)
    comments.value = data.comments
    commentsTotal.value = data.total
  } catch {
    /* silent */
  }
}

async function fetchHistory() {
  try {
    history.value = await getPostHistory(postId.value)
    showHistory.value = true
  } catch {
    /* silent */
  }
}

function startEdit() {
  if (!post.value) return
  editTitle.value = post.value.title
  editContent.value = post.value.content
  editMessage.value = ''
  editing.value = true
}

async function saveEdit() {
  if (!post.value) return
  editSaving.value = true
  editMessage.value = ''
  try {
    post.value = await updatePost(postId.value, {
      title: editTitle.value,
      content: editContent.value,
      version: post.value.version,
    })
    editing.value = false
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: string } } }
    editMessage.value = err.response?.data?.detail || 'Failed to save changes.'
  } finally {
    editSaving.value = false
  }
}

async function deletePostHandler() {
  if (!confirm('Are you sure you want to delete this post?')) return
  try {
    await apiDeletePost(postId.value)
    router.push('/forum')
  } catch {
    /* error */
  }
}

async function submitComment() {
  if (!newComment.value.trim()) return
  commentSaving.value = true
  commentMessage.value = ''
  try {
    const payload: { content: string; parent_id?: string } = { content: newComment.value }
    if (replyTo.value) payload.parent_id = replyTo.value.id
    await createComment(postId.value, payload)
    newComment.value = ''
    replyTo.value = null
    await fetchComments()
    if (post.value) post.value.comment_count++
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: string } } }
    commentMessage.value = err.response?.data?.detail || 'Failed to post comment.'
  } finally {
    commentSaving.value = false
  }
}

async function deleteCommentHandler(commentId: string) {
  if (!confirm('Are you sure you want to delete this comment?')) return
  try {
    await apiDeleteComment(postId.value, commentId)
    await fetchComments()
    if (post.value && post.value.comment_count > 0) post.value.comment_count--
  } catch {
    /* silent */
  }
}

function canDeleteComment(comment: Comment): boolean {
  if (auth.isAdmin) return true
  return !!(auth.user && comment.author.id === auth.user.id)
}

const showReportModal = ref(false)
const reportReason = ref('')
const reportSaving = ref(false)
const reportMessage = ref('')

async function submitReport() {
  if (!reportReason.value.trim()) return
  reportSaving.value = true
  reportMessage.value = ''
  try {
    await createReport(postId.value, reportReason.value)
    showReportModal.value = false
    reportReason.value = ''
    reportMessage.value = ''
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: string } } }
    reportMessage.value = err.response?.data?.detail || 'Failed to submit report.'
  } finally {
    reportSaving.value = false
  }
}

const canReport = computed(() => {
  if (!auth.isAuthenticated || auth.isGuest) return false
  if (!post.value || !auth.user) return false
  return post.value.author.id !== auth.user.id
})

async function toggleReactionHandler(commentId: string, reaction: string) {
  try {
    await apiToggleReaction(postId.value, commentId, reaction)
    await fetchComments()
  } catch {
    /* silent */
  }
}

function getReactionCount(comment: Comment, reaction: string): number {
  return comment.reactions?.[reaction]?.length || 0
}
function hasReacted(comment: Comment, reaction: string): boolean {
  if (!auth.user) return false
  return comment.reactions?.[reaction]?.includes(auth.user.id) || false
}

onMounted(() => {
  fetchPost()
  fetchComments()
})
</script>

<template>
  <div class="max-w-4xl mx-auto">
    <div v-if="loading" class="text-center text-muted py-12">Loading...</div>

    <div v-else-if="!post" class="text-center py-12">
      <p class="text-muted mb-4">Post not found.</p>
      <router-link to="/forum" class="text-brand-600 hover:underline">Back to Forum</router-link>
    </div>

    <template v-else>
      <!-- Editing mode -->
      <div v-if="editing" class="space-y-4">
        <h2 class="text-xl font-bold text-foreground mb-4">Edit Post</h2>
        <BaseAlert v-if="editMessage" type="error">{{ editMessage }}</BaseAlert>
        <BaseInput v-model="editTitle" placeholder="Post title" />
        <TiptapEditor v-model="editContent" />
        <div class="flex gap-3">
          <BaseButton :loading="editSaving" @click="saveEdit">Save Changes</BaseButton>
          <BaseButton variant="secondary" @click="editing = false">Cancel</BaseButton>
        </div>
      </div>

      <!-- View mode -->
      <div v-else>
        <div class="mb-6">
          <router-link to="/forum" class="text-sm text-brand-600 hover:underline"
            >&larr; Back to Forum</router-link
          >
        </div>

        <BaseCard padding="lg" class="mb-6">
          <div class="flex justify-between items-start mb-4">
            <div>
              <h1 class="text-2xl font-bold text-foreground mb-2">{{ post.title }}</h1>
              <div class="flex items-center gap-3 text-sm text-muted flex-wrap">
                <span>{{ post.author.display_name }}</span>
                <span>{{ new Date(post.created_at).toLocaleString() }}</span>
                <BaseBadge v-if="post.category_name">{{ post.category_name }}</BaseBadge>
                <span v-if="post.version > 1" class="text-xs text-muted">v{{ post.version }}</span>
              </div>
            </div>
            <div class="flex gap-2 shrink-0">
              <button
                v-if="canModify"
                @click="startEdit"
                class="text-sm text-brand-600 hover:underline"
              >
                Edit
              </button>
              <button
                v-if="canModify"
                @click="deletePostHandler"
                class="text-sm text-danger-600 hover:underline"
              >
                Delete
              </button>
              <button
                v-if="canReport"
                @click="showReportModal = true"
                class="text-sm text-orange-600 hover:underline"
              >
                Report
              </button>
            </div>
          </div>

          <div
            class="prose prose-sm max-w-none text-foreground/80 mb-4"
            v-html="DOMPurify.sanitize(post.content)"
          ></div>

          <div v-if="post.keywords?.length" class="flex gap-1 flex-wrap mb-3">
            <BaseBadge v-for="kw in post.keywords" :key="kw" variant="neutral">{{ kw }}</BaseBadge>
          </div>

          <div class="flex items-center justify-between border-t border-border pt-3">
            <span class="text-xs text-muted">{{ post.comment_count }} comments</span>
            <button
              v-if="post.version > 1"
              @click="fetchHistory"
              class="text-xs text-brand-600 hover:underline"
            >
              View edit history
            </button>
          </div>
        </BaseCard>

        <!-- Comments Section -->
        <BaseCard padding="lg">
          <h3 class="text-lg font-semibold text-foreground mb-4">Comments ({{ commentsTotal }})</h3>

          <div v-if="post.allow_comments && auth.isAuthenticated && !auth.isGuest" class="mb-6">
            <div
              v-if="replyTo"
              class="bg-surface-alt rounded-lg p-2 mb-2 flex justify-between items-center"
            >
              <span class="text-xs text-muted">Replying to {{ replyTo.author.display_name }}</span>
              <button @click="replyTo = null" class="text-xs text-muted hover:text-foreground">
                &times;
              </button>
            </div>
            <BaseAlert v-if="commentMessage" type="error" class="mb-2">{{
              commentMessage
            }}</BaseAlert>
            <textarea
              v-model="newComment"
              rows="3"
              placeholder="Write a comment..."
              class="w-full px-3 py-2 border border-border rounded-lg focus:ring-2 focus:ring-brand-500 focus:border-transparent outline-none text-sm mb-2 text-foreground"
            ></textarea>
            <BaseButton
              size="sm"
              :loading="commentSaving"
              :disabled="!newComment.trim()"
              @click="submitComment"
              >Post Comment</BaseButton
            >
          </div>

          <div v-else-if="!post.allow_comments" class="text-sm text-muted mb-4">
            Comments are disabled for this post.
          </div>

          <div class="space-y-4">
            <div v-if="comments.length === 0" class="text-sm text-muted text-center py-4">
              No comments yet.
            </div>
            <div
              v-for="comment in comments"
              :key="comment.id"
              class="border-b border-border last:border-0 pb-4 last:pb-0"
              :class="{ 'pl-8 border-l-2 border-brand-100': comment.parent_id }"
            >
              <div class="flex items-center gap-2 mb-1">
                <span class="text-sm font-medium text-foreground">{{
                  comment.author.display_name
                }}</span>
                <span class="text-xs text-muted">{{
                  new Date(comment.created_at).toLocaleString()
                }}</span>
              </div>
              <p
                class="text-sm text-foreground/80 mb-2"
                v-html="DOMPurify.sanitize(comment.content)"
              ></p>
              <div class="flex items-center gap-3">
                <button
                  v-for="r in ['LIKE', 'SMILE', 'CRY']"
                  :key="r"
                  @click="toggleReactionHandler(comment.id, r)"
                  class="text-xs px-2 py-0.5 rounded-full transition"
                  :class="
                    hasReacted(comment, r)
                      ? 'bg-brand-100 text-brand-700'
                      : 'bg-surface-alt text-muted hover:bg-gray-100'
                  "
                >
                  {{ r === 'LIKE' ? '&#128077;' : r === 'SMILE' ? '&#128522;' : '&#128546;' }}
                  {{ getReactionCount(comment, r) || '' }}
                </button>
                <button
                  v-if="post.allow_comments && auth.isAuthenticated && !auth.isGuest"
                  @click="replyTo = comment"
                  class="text-xs text-muted hover:text-brand-600"
                >
                  Reply
                </button>
                <button
                  v-if="canDeleteComment(comment)"
                  @click="deleteCommentHandler(comment.id)"
                  class="text-xs text-danger-500 hover:text-danger-600"
                >
                  Delete
                </button>
              </div>
            </div>
          </div>
        </BaseCard>
      </div>
    </template>

    <!-- History Modal -->
    <BaseModal v-model="showHistory" title="Edit History" size="xl">
      <div v-if="history.length === 0" class="text-muted text-sm text-center py-4">
        No edit history.
      </div>
      <div v-for="item in history" :key="item.id" class="border-b border-border last:border-0 py-4">
        <div class="flex justify-between items-center mb-2">
          <span class="text-sm font-medium text-foreground/80">Version {{ item.version }}</span>
          <span class="text-xs text-muted">{{ new Date(item.edited_at).toLocaleString() }}</span>
        </div>
        <h4 class="text-sm font-semibold text-foreground mb-1">{{ item.title }}</h4>
        <div
          class="text-sm text-muted prose prose-sm max-w-none"
          v-html="DOMPurify.sanitize(item.content)"
        ></div>
      </div>
    </BaseModal>

    <!-- Report Modal -->
    <BaseModal v-model="showReportModal" title="Report Post">
      <BaseAlert v-if="reportMessage" type="error" class="mb-3">{{ reportMessage }}</BaseAlert>
      <textarea
        v-model="reportReason"
        rows="4"
        placeholder="Describe why you are reporting this post..."
        class="w-full px-3 py-2 border border-border rounded-lg focus:ring-2 focus:ring-brand-500 focus:border-transparent outline-none text-sm text-foreground mb-3"
      ></textarea>
      <template #footer>
        <BaseButton variant="secondary" @click="showReportModal = false">Cancel</BaseButton>
        <BaseButton
          class="bg-orange-600 hover:bg-orange-700 text-white"
          :loading="reportSaving"
          :disabled="!reportReason.trim()"
          @click="submitReport"
          >Submit Report</BaseButton
        >
      </template>
    </BaseModal>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import api from '@/composables/api'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

interface Author {
  id: string
  username: string
  display_name: string
  avatar_url: string | null
}

interface Post {
  id: string
  title: string
  content: string
  author: Author
  category_id: string | null
  category_name: string | null
  keywords: string[] | null
  allow_comments: boolean
  version: number
  comment_count: number
  created_at: string
  updated_at: string
}

interface HistoryItem {
  id: string
  version: number
  title: string
  content: string
  edited_at: string
}

interface Comment {
  id: string
  post_id: string
  content: string
  author: Author
  parent_id: string | null
  mentions: string[] | null
  reactions: Record<string, string[]> | null
  created_at: string
  updated_at: string
}

const post = ref<Post | null>(null)
const comments = ref<Comment[]>([])
const commentsTotal = ref(0)
const history = ref<HistoryItem[]>([])
const loading = ref(true)
const showHistory = ref(false)

// Edit mode
const editing = ref(false)
const editTitle = ref('')
const editContent = ref('')
const editSaving = ref(false)
const editMessage = ref('')

// Comment form
const newComment = ref('')
const replyTo = ref<Comment | null>(null)
const commentSaving = ref(false)
const commentMessage = ref('')

const postId = computed(() => route.params.id as string)

const isAuthor = computed(() => {
  return post.value && auth.user && post.value.author.id === auth.user.id
})

const canModify = computed(() => {
  return isAuthor.value || auth.isAdmin
})

async function fetchPost() {
  loading.value = true
  try {
    const { data } = await api.get(`/posts/${postId.value}`)
    post.value = data
  } catch {
    post.value = null
  } finally {
    loading.value = false
  }
}

async function fetchComments() {
  try {
    const { data } = await api.get(`/posts/${postId.value}/comments`)
    comments.value = data.comments
    commentsTotal.value = data.total
  } catch {
    // silent
  }
}

async function fetchHistory() {
  try {
    const { data } = await api.get(`/posts/${postId.value}/history`, {
      headers: { Authorization: `Bearer ${auth.token}` },
    })
    history.value = data.history
    showHistory.value = true
  } catch {
    // silent
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
    const { data } = await api.put(`/posts/${postId.value}`, {
      title: editTitle.value,
      content: editContent.value,
      version: post.value.version,
    })
    post.value = data
    editing.value = false
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: string } } }
    editMessage.value = err.response?.data?.detail || 'Failed to save changes.'
  } finally {
    editSaving.value = false
  }
}

async function deletePost() {
  if (!confirm('Are you sure you want to delete this post?')) return
  try {
    await api.delete(`/posts/${postId.value}`)
    router.push('/forum')
  } catch {
    // error
  }
}

async function submitComment() {
  if (!newComment.value.trim()) return
  commentSaving.value = true
  commentMessage.value = ''
  try {
    const body: Record<string, unknown> = { content: newComment.value }
    if (replyTo.value) body.parent_id = replyTo.value.id

    await api.post(`/posts/${postId.value}/comments`, body)
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

async function toggleReaction(commentId: string, reaction: string) {
  try {
    await api.post(`/posts/${postId.value}/comments/${commentId}/reactions`, { reaction })
    await fetchComments()
  } catch {
    // silent
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
  <div class="max-w-4xl mx-auto py-8 px-4">
    <!-- Loading -->
    <div v-if="loading" class="text-center text-gray-400 py-12">Loading...</div>

    <!-- Not found -->
    <div v-else-if="!post" class="text-center py-12">
      <p class="text-gray-500 mb-4">Post not found.</p>
      <router-link to="/forum" class="text-blue-600 hover:underline">Back to Forum</router-link>
    </div>

    <!-- Post detail -->
    <template v-else>
      <!-- Editing mode -->
      <div v-if="editing" class="space-y-4">
        <h2 class="text-xl font-bold text-gray-900 mb-4">Edit Post</h2>
        <div v-if="editMessage" class="bg-red-50 border border-red-200 text-red-700 rounded-lg p-3 text-sm">
          {{ editMessage }}
        </div>
        <input
          v-model="editTitle"
          type="text"
          maxlength="300"
          class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none"
        />
        <textarea
          v-model="editContent"
          rows="12"
          class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none font-mono text-sm"
        ></textarea>
        <div class="flex gap-3">
          <button
            @click="saveEdit"
            :disabled="editSaving"
            class="bg-blue-600 text-white px-4 py-2 rounded-lg text-sm hover:bg-blue-700 disabled:opacity-50"
          >
            {{ editSaving ? 'Saving...' : 'Save Changes' }}
          </button>
          <button @click="editing = false" class="px-4 py-2 bg-gray-100 text-gray-600 rounded-lg text-sm hover:bg-gray-200">
            Cancel
          </button>
        </div>
      </div>

      <!-- View mode -->
      <div v-else>
        <div class="mb-6">
          <router-link to="/forum" class="text-sm text-blue-600 hover:underline">&larr; Back to Forum</router-link>
        </div>

        <article class="bg-white rounded-xl shadow p-6 mb-6">
          <div class="flex justify-between items-start mb-4">
            <div>
              <h1 class="text-2xl font-bold text-gray-900 mb-2">{{ post.title }}</h1>
              <div class="flex items-center gap-3 text-sm text-gray-500">
                <span>{{ post.author.display_name }}</span>
                <span>{{ new Date(post.created_at).toLocaleString() }}</span>
                <span v-if="post.category_name" class="px-2 py-0.5 bg-blue-50 text-blue-600 rounded-full text-xs">
                  {{ post.category_name }}
                </span>
                <span v-if="post.version > 1" class="text-xs text-gray-400">v{{ post.version }}</span>
              </div>
            </div>

            <div v-if="canModify" class="flex gap-2 shrink-0">
              <button @click="startEdit" class="text-sm text-blue-600 hover:underline">Edit</button>
              <button @click="deletePost" class="text-sm text-red-600 hover:underline">Delete</button>
            </div>
          </div>

          <div class="prose prose-sm max-w-none text-gray-700 mb-4" v-html="post.content"></div>

          <div v-if="post.keywords?.length" class="flex gap-1 flex-wrap mb-3">
            <span
              v-for="kw in post.keywords"
              :key="kw"
              class="text-xs bg-gray-100 text-gray-500 px-2 py-0.5 rounded-full"
            >
              {{ kw }}
            </span>
          </div>

          <div class="flex items-center justify-between border-t pt-3">
            <span class="text-xs text-gray-400">{{ post.comment_count }} comments</span>
            <button
              v-if="post.version > 1"
              @click="fetchHistory"
              class="text-xs text-blue-600 hover:underline"
            >
              View edit history
            </button>
          </div>
        </article>

        <!-- Comments Section -->
        <div class="bg-white rounded-xl shadow p-6">
          <h3 class="text-lg font-semibold text-gray-900 mb-4">Comments ({{ commentsTotal }})</h3>

          <!-- Comment form -->
          <div v-if="post.allow_comments && auth.isAuthenticated && !auth.isGuest" class="mb-6">
            <div v-if="replyTo" class="bg-gray-50 rounded-lg p-2 mb-2 flex justify-between items-center">
              <span class="text-xs text-gray-500">Replying to {{ replyTo.author.display_name }}</span>
              <button @click="replyTo = null" class="text-xs text-gray-400 hover:text-gray-600">&times;</button>
            </div>
            <div v-if="commentMessage" class="bg-red-50 border border-red-200 text-red-700 rounded-lg p-2 mb-2 text-xs">
              {{ commentMessage }}
            </div>
            <textarea
              v-model="newComment"
              rows="3"
              placeholder="Write a comment..."
              class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none text-sm mb-2"
            ></textarea>
            <button
              @click="submitComment"
              :disabled="commentSaving || !newComment.trim()"
              class="bg-blue-600 text-white px-4 py-1.5 rounded-lg text-sm hover:bg-blue-700 disabled:opacity-50"
            >
              {{ commentSaving ? 'Posting...' : 'Post Comment' }}
            </button>
          </div>

          <div v-else-if="!post.allow_comments" class="text-sm text-gray-400 mb-4">
            Comments are disabled for this post.
          </div>

          <!-- Comment list -->
          <div class="space-y-4">
            <div v-if="comments.length === 0" class="text-sm text-gray-400 text-center py-4">
              No comments yet.
            </div>

            <div
              v-for="comment in comments"
              :key="comment.id"
              class="border-b last:border-0 pb-4 last:pb-0"
              :class="{ 'pl-8 border-l-2 border-blue-100': comment.parent_id }"
            >
              <div class="flex items-center gap-2 mb-1">
                <span class="text-sm font-medium text-gray-900">{{ comment.author.display_name }}</span>
                <span class="text-xs text-gray-400">{{ new Date(comment.created_at).toLocaleString() }}</span>
              </div>
              <p class="text-sm text-gray-700 mb-2" v-html="comment.content"></p>
              <div class="flex items-center gap-3">
                <!-- Reactions -->
                <button
                  v-for="r in ['LIKE', 'SMILE', 'CRY']"
                  :key="r"
                  @click="toggleReaction(comment.id, r)"
                  class="text-xs px-2 py-0.5 rounded-full transition"
                  :class="hasReacted(comment, r) ? 'bg-blue-100 text-blue-700' : 'bg-gray-50 text-gray-400 hover:bg-gray-100'"
                >
                  {{ r === 'LIKE' ? '&#128077;' : r === 'SMILE' ? '&#128522;' : '&#128546;' }}
                  {{ getReactionCount(comment, r) || '' }}
                </button>

                <!-- Reply -->
                <button
                  v-if="post.allow_comments && auth.isAuthenticated && !auth.isGuest"
                  @click="replyTo = comment"
                  class="text-xs text-gray-400 hover:text-blue-600"
                >
                  Reply
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </template>

    <!-- History Modal -->
    <div v-if="showHistory" class="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
      <div class="bg-white rounded-xl shadow-xl p-6 w-full max-w-2xl max-h-[80vh] overflow-y-auto">
        <div class="flex justify-between items-center mb-4">
          <h2 class="text-lg font-bold">Edit History</h2>
          <button @click="showHistory = false" class="text-gray-400 hover:text-gray-600 text-xl">&times;</button>
        </div>
        <div v-if="history.length === 0" class="text-gray-400 text-sm text-center py-4">No edit history.</div>
        <div v-for="item in history" :key="item.id" class="border-b last:border-0 py-4">
          <div class="flex justify-between items-center mb-2">
            <span class="text-sm font-medium text-gray-700">Version {{ item.version }}</span>
            <span class="text-xs text-gray-400">{{ new Date(item.edited_at).toLocaleString() }}</span>
          </div>
          <h4 class="text-sm font-semibold text-gray-800 mb-1">{{ item.title }}</h4>
          <div class="text-sm text-gray-600 prose prose-sm max-w-none" v-html="item.content"></div>
        </div>
      </div>
    </div>
  </div>
</template>

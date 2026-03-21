<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@/stores/auth'
import { useToastStore } from '@/stores/toast'
import { useAlbumLayout } from '@/composables/useAlbumLayout'
import { listAlbumComments, createAlbumComment, deleteAlbumComment } from '@/api/albums'
import { getErrorMessage } from '@/utils/error'
import { usePagination } from '@/composables/usePagination'
import type { AlbumComment } from '@/types/album'
import SkeletonLoader from '@/components/SkeletonLoader.vue'
import EmptyState from '@/components/EmptyState.vue'
import BaseCard from '@/components/base/BaseCard.vue'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseAvatar from '@/components/base/BaseAvatar.vue'
import BasePagination from '@/components/base/BasePagination.vue'

const { t } = useI18n()
const auth = useAuthStore()
const toast = useToastStore()
const { album, userAlbumRole } = useAlbumLayout()

const comments = ref<AlbumComment[]>([])
const loading = ref(false)
const newComment = ref('')
const replyingTo = ref<string | null>(null)
const replyContent = ref('')
const submitting = ref(false)
const PAGE_SIZE = 20

const { page, total, totalPages, setPage, resetPage, updateFromResponse } = usePagination(PAGE_SIZE)

const canComment = computed(() => auth.isAuthenticated && !auth.isGuest)

const topLevelComments = computed(() => comments.value.filter((c) => !c.parent_id && !c.is_deleted))

function getReplies(parentId: string): AlbumComment[] {
  return comments.value.filter((c) => c.parent_id === parentId && !c.is_deleted)
}

function formatTime(dateStr: string): string {
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

async function fetchComments() {
  if (!album.value) return
  loading.value = true
  try {
    const result = await listAlbumComments(album.value.id, page.value, PAGE_SIZE)
    comments.value = result.comments
    updateFromResponse(result.total)
  } catch (e: unknown) {
    toast.show(getErrorMessage(e, t('albums.failedLoadComments')), 'error')
  } finally {
    loading.value = false
  }
}

function handlePageChange(p: number) {
  setPage(p)
}

async function handleSubmitComment() {
  if (!album.value || !newComment.value.trim()) return
  submitting.value = true
  try {
    await createAlbumComment(album.value.id, { content: newComment.value.trim() })
    newComment.value = ''
    toast.show(t('albums.commentPosted'), 'success')
    await fetchComments()
  } catch (e: unknown) {
    toast.show(getErrorMessage(e, t('albums.failedPostComment')), 'error')
  } finally {
    submitting.value = false
  }
}

function startReply(commentId: string) {
  replyingTo.value = commentId
  replyContent.value = ''
}

function cancelReply() {
  replyingTo.value = null
  replyContent.value = ''
}

async function handleSubmitReply() {
  if (!album.value || !replyingTo.value || !replyContent.value.trim()) return
  submitting.value = true
  try {
    await createAlbumComment(album.value.id, {
      content: replyContent.value.trim(),
      parent_id: replyingTo.value,
    })
    replyingTo.value = null
    replyContent.value = ''
    toast.show(t('albums.replyPosted'), 'success')
    await fetchComments()
  } catch (e: unknown) {
    toast.show(getErrorMessage(e, t('albums.failedPostReply')), 'error')
  } finally {
    submitting.value = false
  }
}

async function handleDelete(commentId: string) {
  if (!album.value) return
  try {
    await deleteAlbumComment(album.value.id, commentId)
    toast.show(t('albums.commentDeleted'), 'info')
    await fetchComments()
  } catch (e: unknown) {
    toast.show(getErrorMessage(e, t('albums.failedDeleteComment')), 'error')
  }
}

function canDeleteComment(comment: AlbumComment): boolean {
  if (!auth.user) return false
  return auth.isAdmin || userAlbumRole.value === 'ADMIN' || comment.user_id === auth.user.id
}

onMounted(fetchComments)
watch(
  () => album.value?.id,
  () => {
    resetPage()
    fetchComments()
  },
)
watch(page, fetchComments)
</script>

<template>
  <div>
    <h2 class="text-lg font-semibold text-foreground mb-4">{{ t('albums.comments') }}</h2>

    <!-- New comment form -->
    <div v-if="canComment" class="mb-6">
      <BaseCard class="!p-3">
        <div class="flex gap-3">
          <BaseAvatar
            :src="auth.user?.avatar_url"
            :name="auth.user?.display_name || ''"
            size="sm"
          />
          <div class="flex-1">
            <textarea
              v-model="newComment"
              rows="2"
              name="new-comment"
              :placeholder="t('albums.commentPlaceholder')"
              class="w-full border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 text-foreground resize-none"
            ></textarea>
            <div class="flex justify-end mt-2">
              <BaseButton
                size="sm"
                :loading="submitting"
                :disabled="!newComment.trim()"
                @click="handleSubmitComment"
              >
                {{ t('albums.postComment') }}
              </BaseButton>
            </div>
          </div>
        </div>
      </BaseCard>
    </div>

    <SkeletonLoader v-if="loading" :lines="4" variant="card" />

    <EmptyState
      v-else-if="topLevelComments.length === 0"
      :title="t('albums.noCommentsTitle')"
      :message="t('albums.noCommentsMessage')"
    />

    <template v-else>
      <div class="space-y-4">
        <BaseCard v-for="comment in topLevelComments" :key="comment.id" class="!p-4">
          <!-- Top-level comment -->
          <div class="flex gap-3">
            <BaseAvatar :src="comment.avatar_url" :name="comment.display_name" size="sm" />
            <div class="flex-1 min-w-0">
              <div class="flex items-center gap-2 mb-1">
                <span class="text-sm font-medium text-foreground">{{ comment.display_name }}</span>
                <span class="text-xs text-muted">{{ formatTime(comment.created_at) }}</span>
              </div>
              <p class="text-sm text-foreground whitespace-pre-wrap break-words">
                {{ comment.content }}
              </p>
              <div class="flex items-center gap-3 mt-2">
                <button
                  v-if="canComment"
                  type="button"
                  class="text-xs text-muted hover:text-brand-600"
                  @click="startReply(comment.id)"
                >
                  {{ t('albums.reply') }}
                </button>
                <button
                  v-if="canDeleteComment(comment)"
                  type="button"
                  class="text-xs text-muted hover:text-danger-600"
                  @click="handleDelete(comment.id)"
                >
                  {{ t('common.delete') }}
                </button>
              </div>
            </div>
          </div>

          <!-- Reply form -->
          <div v-if="replyingTo === comment.id" class="mt-3 ml-10">
            <textarea
              v-model="replyContent"
              rows="2"
              name="reply"
              :placeholder="t('albums.replyPlaceholder')"
              class="w-full border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 text-foreground resize-none"
            ></textarea>
            <div class="flex justify-end gap-2 mt-2">
              <BaseButton size="sm" variant="secondary" @click="cancelReply">{{
                t('common.cancel')
              }}</BaseButton>
              <BaseButton
                size="sm"
                :loading="submitting"
                :disabled="!replyContent.trim()"
                @click="handleSubmitReply"
              >
                {{ t('albums.reply') }}
              </BaseButton>
            </div>
          </div>

          <!-- Replies -->
          <div v-if="getReplies(comment.id).length > 0" class="mt-3 ml-10 space-y-3">
            <div v-for="reply in getReplies(comment.id)" :key="reply.id" class="flex gap-3">
              <BaseAvatar :src="reply.avatar_url" :name="reply.display_name" size="sm" />
              <div class="flex-1 min-w-0">
                <div class="flex items-center gap-2 mb-1">
                  <span class="text-sm font-medium text-foreground">{{ reply.display_name }}</span>
                  <span class="text-xs text-muted">{{ formatTime(reply.created_at) }}</span>
                </div>
                <p class="text-sm text-foreground whitespace-pre-wrap break-words">
                  {{ reply.content }}
                </p>
                <button
                  v-if="canDeleteComment(reply)"
                  type="button"
                  class="text-xs text-muted hover:text-danger-600 mt-1"
                  @click="handleDelete(reply.id)"
                >
                  {{ t('common.delete') }}
                </button>
              </div>
            </div>
          </div>
        </BaseCard>
      </div>

      <div class="mt-6">
        <BasePagination
          :current-page="page"
          :total-pages="totalPages"
          :page-size="PAGE_SIZE"
          :total="total"
          @update:current-page="handlePageChange"
        />
      </div>
    </template>
  </div>
</template>

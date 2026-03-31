<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useLocale } from '@/composables/useLocale'
import { useAuthStore } from '@/stores/auth'
import { useToastStore } from '@/stores/toast'
import { getErrorMessage } from '@/utils/error'
import { formatDateTime } from '@/utils/date'
import { sanitizeHtml } from '@/utils/sanitize'
import {
  getEvent,
  deleteEvent,
  listEventComments,
  createEventComment,
  deleteEventComment,
} from '@/api/events'
import type { Event, Comment } from '@/types'
import SkeletonLoader from '@/components/SkeletonLoader.vue'
import BaseCard from '@/components/base/BaseCard.vue'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseBadge from '@/components/base/BaseBadge.vue'
import BaseBreadcrumb from '@/components/base/BaseBreadcrumb.vue'
import BaseModal from '@/components/base/BaseModal.vue'
import BaseAvatar from '@/components/base/BaseAvatar.vue'

const { t, currentLocale } = useLocale()
const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const toast = useToastStore()

const event = ref<Event | null>(null)
const loading = ref(true)
const comments = ref<Comment[]>([])
const commentsLoading = ref(false)
const commentContent = ref('')
const submittingComment = ref(false)
const showDeleteModal = ref(false)
const deleting = ref(false)

const eventId = computed(() => route.params.id as string)

const canEdit = computed(() => {
  if (!event.value || !auth.user) return false
  return event.value.author.id === auth.user.id || auth.isSuperAdmin
})

const canComment = computed(() => {
  return auth.isAuthenticated && !auth.isGuest && event.value?.allow_comments
})

function visibilityLabel(role: string): string {
  const map: Record<string, string> = {
    GUEST: t('events.roleGuest'),
    MEMBER: t('events.roleMember'),
    ADMIN: t('events.roleAdmin'),
    SUPER_ADMIN: t('events.roleSuperAdmin'),
  }
  return map[role] || role
}

async function fetchEvent() {
  loading.value = true
  try {
    event.value = await getEvent(eventId.value)
  } catch (e: unknown) {
    toast.show(getErrorMessage(e, t('events.fetchError')), 'error')
    router.push('/events')
  } finally {
    loading.value = false
  }
}

async function fetchComments() {
  commentsLoading.value = true
  try {
    const data = await listEventComments(eventId.value, { page: 1, page_size: 100 })
    comments.value = data.comments ?? []
  } catch {
    // Comments are non-critical
  } finally {
    commentsLoading.value = false
  }
}

async function handleSubmitComment() {
  if (!commentContent.value.trim()) return
  submittingComment.value = true
  try {
    await createEventComment(eventId.value, { content: commentContent.value.trim() })
    commentContent.value = ''
    toast.show(t('events.commentSuccess'), 'success')
    await fetchComments()
    // Update local comment count
    if (event.value) {
      event.value = { ...event.value, comment_count: event.value.comment_count + 1 }
    }
  } catch (e: unknown) {
    toast.show(getErrorMessage(e, t('events.commentError')), 'error')
  } finally {
    submittingComment.value = false
  }
}

async function handleDeleteComment(commentId: string) {
  try {
    await deleteEventComment(eventId.value, commentId)
    toast.show(t('events.commentDeleted'), 'success')
    await fetchComments()
    if (event.value) {
      event.value = { ...event.value, comment_count: Math.max(0, event.value.comment_count - 1) }
    }
  } catch (e: unknown) {
    toast.show(getErrorMessage(e, t('events.commentDeleteError')), 'error')
  }
}

function canDeleteComment(comment: Comment): boolean {
  if (!auth.user) return false
  return comment.author.id === auth.user.id || auth.isAdmin
}

async function handleDelete() {
  deleting.value = true
  try {
    await deleteEvent(eventId.value)
    toast.show(t('events.deleteSuccess'), 'success')
    router.push('/events')
  } catch (e: unknown) {
    toast.show(getErrorMessage(e, t('events.deleteError')), 'error')
  } finally {
    deleting.value = false
    showDeleteModal.value = false
  }
}

onMounted(async () => {
  await fetchEvent()
  if (event.value) {
    await fetchComments()
  }
})
</script>

<template>
  <div class="max-w-4xl mx-auto py-6 px-4">
    <SkeletonLoader v-if="loading" :lines="6" variant="card" />

    <template v-else-if="event">
      <BaseBreadcrumb
        :items="[
          { label: t('breadcrumb.home'), to: '/' },
          { label: t('breadcrumb.events'), to: '/events' },
          { label: event.title },
        ]"
      />

      <BaseCard padding="lg" class="mb-6">
        <div class="flex items-start justify-between mb-4">
          <h1 class="text-2xl font-bold text-foreground leading-tight">{{ event.title }}</h1>
          <div v-if="canEdit" class="flex gap-2 shrink-0 ml-4">
            <router-link :to="`/events/${event.id}/edit`">
              <BaseButton variant="secondary" size="sm">{{ t('common.edit') }}</BaseButton>
            </router-link>
            <BaseButton variant="soft-danger" size="sm" @click="showDeleteModal = true">
              {{ t('common.delete') }}
            </BaseButton>
          </div>
        </div>

        <div class="flex items-center gap-3 mb-4">
          <BaseAvatar :src="event.author.avatar_url" :name="event.author.display_name" size="sm" />
          <div>
            <router-link
              :to="`/users/${event.author.id}`"
              class="text-sm font-medium text-foreground hover:text-brand-600"
            >
              {{ event.author.display_name }}
            </router-link>
            <p class="text-xs text-muted">
              {{ formatDateTime(event.created_at, currentLocale) }}
            </p>
          </div>
        </div>

        <div class="flex flex-wrap gap-1 mb-4">
          <BaseBadge v-for="role in event.visibility" :key="role" variant="brand" size="sm">
            {{ visibilityLabel(role) }}
          </BaseBadge>
          <router-link v-if="event.sig_name" :to="`/sigs/${event.sig_id}`">
            <BaseBadge variant="neutral" size="sm">{{ event.sig_name }}</BaseBadge>
          </router-link>
        </div>

        <div class="prose max-w-none text-foreground" v-html="sanitizeHtml(event.content)"></div>
      </BaseCard>

      <!-- Comments Section -->
      <BaseCard v-if="event.allow_comments" padding="lg">
        <h2 class="text-lg font-bold text-foreground mb-4">
          {{ t('events.commentsTitle') }}
          <span v-if="comments.length > 0" class="text-muted font-normal text-sm">
            ({{ comments.length }})
          </span>
        </h2>

        <!-- Comment Form -->
        <div v-if="canComment" class="mb-6">
          <textarea
            v-model="commentContent"
            rows="3"
            class="w-full rounded-lg border border-border bg-surface text-foreground text-sm px-3 py-2 focus:outline-none focus:ring-2 focus:ring-brand-300 resize-none"
            :placeholder="t('events.commentPlaceholder')"
          ></textarea>
          <div class="flex justify-end mt-2">
            <BaseButton
              size="sm"
              :loading="submittingComment"
              :disabled="!commentContent.trim()"
              @click="handleSubmitComment"
            >
              {{ t('events.submitComment') }}
            </BaseButton>
          </div>
        </div>
        <p v-else-if="!event.allow_comments" class="text-sm text-muted mb-4">
          {{ t('events.commentsDisabled') }}
        </p>

        <!-- Comments List -->
        <div v-if="commentsLoading" class="py-4">
          <SkeletonLoader :lines="2" />
        </div>
        <div v-else-if="comments.length === 0" class="text-sm text-muted py-4">
          {{ t('events.noComments') }}
        </div>
        <div v-else class="space-y-4">
          <div
            v-for="comment in comments"
            :key="comment.id"
            class="flex gap-3 py-3 border-b border-border last:border-0"
          >
            <BaseAvatar
              :src="comment.author.avatar_url"
              :name="comment.author.display_name"
              size="xs"
            />
            <div class="flex-1 min-w-0">
              <div class="flex items-center gap-2 mb-1">
                <router-link
                  :to="`/users/${comment.author.id}`"
                  class="text-sm font-medium text-foreground hover:text-brand-600"
                >
                  {{ comment.author.display_name }}
                </router-link>
                <span class="text-xs text-muted">
                  {{ formatDateTime(comment.created_at, currentLocale) }}
                </span>
              </div>
              <div class="text-sm text-foreground" v-html="sanitizeHtml(comment.content)"></div>
              <button
                v-if="canDeleteComment(comment)"
                class="text-xs text-danger-600 hover:text-danger-700 mt-1"
                @click="handleDeleteComment(comment.id)"
              >
                {{ t('common.delete') }}
              </button>
            </div>
          </div>
        </div>
      </BaseCard>
    </template>

    <!-- Delete Confirmation Modal -->
    <BaseModal v-model="showDeleteModal" :title="t('events.deleteConfirmTitle')" size="sm">
      <p class="text-sm text-muted mb-4">{{ t('events.deleteConfirmMessage') }}</p>
      <template #footer>
        <BaseButton variant="secondary" @click="showDeleteModal = false">
          {{ t('common.cancel') }}
        </BaseButton>
        <BaseButton variant="danger" :loading="deleting" @click="handleDelete">
          {{ t('common.delete') }}
        </BaseButton>
      </template>
    </BaseModal>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, defineAsyncComponent } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@/stores/auth'
import DOMPurify from 'dompurify'
import { renderMentions } from '@/utils/html'
import { usePostDetail } from '@/composables/usePostDetail'
const TiptapEditor = defineAsyncComponent(() => import('@/components/TiptapEditor.vue'))
import BaseCard from '@/components/base/BaseCard.vue'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseAlert from '@/components/base/BaseAlert.vue'
import BaseBadge from '@/components/base/BaseBadge.vue'
import BaseModal from '@/components/base/BaseModal.vue'
import BaseInput from '@/components/base/BaseInput.vue'
import BasePagination from '@/components/base/BasePagination.vue'
import BaseAvatar from '@/components/base/BaseAvatar.vue'
import SkeletonLoader from '@/components/SkeletonLoader.vue'
import SigShareCard from '@/components/SigShareCard.vue'
import FormShareCard from '@/components/FormShareCard.vue'
import FloatingCreateButton from '@/components/FloatingCreateButton.vue'
import EmptyState from '@/components/EmptyState.vue'
import BaseBreadcrumb from '@/components/base/BaseBreadcrumb.vue'
import ReactionPicker from '@/components/ReactionPicker.vue'
import CoAuthorManager from '@/components/post/CoAuthorManager.vue'
import { Quote, ChevronDown, ChevronUp, Pin } from 'lucide-vue-next'
import { formatDateTime } from '@/utils/date'

const { t, locale } = useI18n()
const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const postId = computed(() => route.params.id as string)

const {
  post,
  loading,
  editing,
  editTitle,
  editContent,
  editSaving,
  editMessage,
  commentTree,
  commentPage,
  commentTotalPages,
  commentsTotal,
  newComment,
  commentSaving,
  commentMessage,
  inlineReplyTo,
  inlineReplyContent,
  editingComment,
  editCommentContent,
  editCommentSaving,
  history,
  showHistory,
  showDeletePostConfirm,
  showDeleteCommentConfirm,
  showLeaveConfirm,
  confirmLeave,
  cancelLeave,
  showReportModal,
  reportReason,
  reportSaving,
  reportMessage,
  canReport,
  pinSaving,
  isAuthor,
  canModify,
  coAuthors,
  citedBy,
  citing,
  contentSegments,
  postContentRef,
  goToCommentPage,
  fetchHistory,
  startEdit,
  saveEdit,
  deletePostHandler,
  submitComment,
  submitInlineReply,
  confirmDeleteComment,
  deleteCommentHandler,
  canDeleteComment,
  submitReport,
  handleTogglePin,
  formatRelativeTime,
  toggleReactionHandler,
  togglePostReactionHandler,
  canEditComment,
  startEditComment,
  cancelEditComment,
  saveEditComment,
  handleReply,
  cancelEdit,
} = usePostDetail({ postId, auth, router })

const showCitedBy = ref(false)
const showReferences = ref(false)

const acceptedCoAuthors = computed(() => coAuthors.value.filter((ca) => ca.status === 'ACCEPTED'))

function toggleCitedBy() {
  showCitedBy.value = !showCitedBy.value
}

function toggleReferences() {
  showReferences.value = !showReferences.value
}

const breadcrumbItems = computed(() => {
  const fromSigId = route.query.fromSigId as string | undefined
  const fromSigName = route.query.fromSigName as string | undefined
  if (fromSigId) {
    return [
      { label: t('breadcrumb.home'), to: '/' },
      { label: t('breadcrumb.sigs'), to: '/sigs' },
      { label: fromSigName || '...', to: `/sigs/${fromSigId}` },
      { label: post.value?.title || '...' },
    ]
  }
  return [
    { label: t('breadcrumb.home'), to: '/' },
    { label: t('breadcrumb.forum'), to: '/forum' },
    { label: post.value?.title || '...' },
  ]
})
</script>

<template>
  <div class="max-w-4xl mx-auto">
    <SkeletonLoader v-if="loading" :lines="1" variant="card" />

    <div v-else-if="!post" class="text-center py-12">
      <p class="text-muted mb-4">{{ t('post.detail.notFound') }}</p>
      <router-link to="/forum" class="text-brand-600 hover:underline">{{
        t('post.detail.backToForum')
      }}</router-link>
    </div>

    <template v-else>
      <!-- Editing mode -->
      <div v-if="editing" class="space-y-4">
        <h2 class="text-xl font-bold text-foreground mb-4">{{ t('post.detail.editTitle') }}</h2>
        <BaseAlert v-if="editMessage" type="error">{{ editMessage }}</BaseAlert>
        <BaseInput v-model="editTitle" :placeholder="t('post.create.titlePlaceholder')" />
        <TiptapEditor v-model="editContent" />
        <div class="flex gap-3">
          <BaseButton :loading="editSaving" @click="saveEdit">{{
            t('post.detail.saveChanges')
          }}</BaseButton>
          <BaseButton variant="secondary" @click="cancelEdit">{{ t('common.cancel') }}</BaseButton>
        </div>
      </div>

      <!-- View mode -->
      <div v-else>
        <BaseBreadcrumb :items="breadcrumbItems" />

        <BaseCard padding="lg" class="mb-6">
          <!-- Post Header with Avatar -->
          <div class="flex items-start gap-3 mb-4">
            <router-link :to="`/users/${post.author.id}`">
              <BaseAvatar
                :src="post.author.avatar_url"
                :name="post.author.display_name"
                size="md"
              />
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
                <span>{{ formatDateTime(post.created_at, locale) }}</span>
                <BaseBadge v-if="post.category_name">{{ post.category_name }}</BaseBadge>
                <span
                  v-if="post.is_pinned"
                  class="inline-flex items-center gap-1 text-xs font-medium text-amber-600"
                  data-testid="pin-icon"
                >
                  <Pin :size="12" aria-hidden="true" />
                  {{ t('post.detail.pinned') }}
                </span>
                <span v-if="post.version > 1" class="text-xs text-muted">{{
                  t('post.detail.version', { version: post.version })
                }}</span>
              </div>
            </div>
            <div class="flex gap-2 shrink-0">
              <button
                v-if="auth.isAdmin"
                :disabled="pinSaving"
                class="text-sm text-amber-600 hover:underline disabled:opacity-50"
                @click="handleTogglePin"
              >
                {{ post.is_pinned ? t('post.detail.unpin') : t('post.detail.pin') }}
              </button>
              <button
                v-if="canModify"
                class="text-sm text-brand-600 hover:underline"
                @click="startEdit"
              >
                {{ t('post.detail.edit') }}
              </button>
              <button
                v-if="canModify"
                class="text-sm text-danger-600 hover:underline"
                @click="showDeletePostConfirm = true"
              >
                {{ t('post.detail.delete') }}
              </button>
              <button
                v-if="canReport"
                class="text-sm text-orange-600 hover:underline"
                @click="showReportModal = true"
              >
                {{ t('post.detail.report') }}
              </button>
            </div>
          </div>

          <div
            ref="postContentRef"
            class="prose prose-sm max-w-none break-words text-foreground/80 mb-4"
          >
            <template v-for="(seg, i) in contentSegments" :key="i">
              <div v-if="seg.type === 'html'" v-html="seg.content"></div>
              <SigShareCard
                v-else-if="seg.type === 'sig-card'"
                :sig-id="seg.content"
                class="my-3 not-prose"
              />
              <FormShareCard
                v-else-if="seg.type === 'form-card'"
                :form-id="seg.content"
                class="my-3 not-prose"
              />
            </template>
          </div>

          <div v-if="post.keywords?.length" class="flex gap-1 flex-wrap mb-3">
            <BaseBadge v-for="kw in post.keywords" :key="kw" variant="neutral">{{ kw }}</BaseBadge>
          </div>

          <!-- Co-Authors Display -->
          <div v-if="acceptedCoAuthors.length > 0" class="mb-3">
            <h4 class="text-xs font-medium text-muted mb-1.5">{{ t('post.detail.coAuthors') }}</h4>
            <div class="flex items-center gap-2 flex-wrap">
              <div
                v-for="ca in acceptedCoAuthors"
                :key="ca.id"
                class="inline-flex items-center gap-1.5 px-2 py-1 rounded-full bg-surface-alt"
              >
                <BaseAvatar :src="ca.avatar_url" :name="ca.display_name" size="xs" />
                <span class="text-xs font-medium text-foreground">{{ ca.display_name }}</span>
                <span v-if="ca.affiliation" class="text-xs text-muted">({{ ca.affiliation }})</span>
              </div>
            </div>
          </div>

          <!-- Citations sections -->
          <div v-if="citedBy.length > 0 || citing.length > 0" class="mb-3 space-y-2">
            <!-- Cited by -->
            <div v-if="citedBy.length > 0">
              <button
                type="button"
                class="flex items-center gap-1.5 text-sm font-medium text-brand-600 hover:text-brand-700"
                @click="toggleCitedBy"
              >
                <Quote class="w-3.5 h-3.5" />
                {{ t('post.detail.citedByCount', { count: citedBy.length }) }}
                <ChevronDown v-if="!showCitedBy" class="w-3.5 h-3.5" />
                <ChevronUp v-else class="w-3.5 h-3.5" />
              </button>
              <div v-if="showCitedBy" class="mt-1.5 pl-5 space-y-1">
                <div v-for="c in citedBy" :key="c.id" class="text-sm">
                  <router-link
                    :to="`/forum/${c.post_id}`"
                    class="text-foreground hover:text-brand-600 hover:underline"
                  >
                    {{ c.post_title }}
                  </router-link>
                  <span class="text-xs text-muted ml-1">{{ t('common.by') }} {{ c.author_name }}</span>
                  <BaseBadge
                    v-if="c.is_self_citation"
                    variant="neutral"
                    class="!text-[10px] !px-1 !py-0 ml-1"
                  >
                    {{ t('citations.selfCitation') }}
                  </BaseBadge>
                </div>
              </div>
            </div>

            <!-- References (citing) -->
            <div v-if="citing.length > 0">
              <button
                type="button"
                class="flex items-center gap-1.5 text-sm font-medium text-brand-600 hover:text-brand-700"
                @click="toggleReferences"
              >
                <Quote class="w-3.5 h-3.5" />
                {{ t('post.detail.referencesCount', { count: citing.length }) }}
                <ChevronDown v-if="!showReferences" class="w-3.5 h-3.5" />
                <ChevronUp v-else class="w-3.5 h-3.5" />
              </button>
              <div v-if="showReferences" class="mt-1.5 pl-5 space-y-1">
                <div v-for="c in citing" :key="c.id" class="text-sm">
                  <router-link
                    :to="`/forum/${c.post_id}`"
                    class="text-foreground hover:text-brand-600 hover:underline"
                  >
                    {{ c.post_title }}
                  </router-link>
                  <span class="text-xs text-muted ml-1">{{ t('common.by') }} {{ c.author_name }}</span>
                  <BaseBadge
                    v-if="c.is_self_citation"
                    variant="neutral"
                    class="!text-[10px] !px-1 !py-0 ml-1"
                  >
                    {{ t('citations.selfCitation') }}
                  </BaseBadge>
                </div>
              </div>
            </div>
          </div>

          <!-- Post Reactions -->
          <div class="mb-3">
            <ReactionPicker
              :reactions="post.reactions ?? null"
              :user-id="auth.user?.id ?? null"
              :readonly="!auth.isAuthenticated || auth.isGuest"
              @toggle="togglePostReactionHandler"
            />
          </div>

          <!-- Action Bar -->
          <div class="flex items-center justify-between border-t border-border pt-3">
            <div class="flex items-center gap-4">
              <span class="text-sm text-muted">
                {{ t('post.detail.commentCount', post.comment_count, { count: post.comment_count }) }}
              </span>
              <span class="text-sm text-muted flex items-center gap-1">
                <svg
                  class="w-3.5 h-3.5"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                >
                  <path
                    d="M2.062 12.348a1 1 0 0 1 0-.696 10.75 10.75 0 0 1 19.876 0 1 1 0 0 1 0 .696 10.75 10.75 0 0 1-19.876 0"
                  />
                  <circle cx="12" cy="12" r="3" />
                </svg>
                {{ t('post.detail.viewCount', { count: post.view_count }) }}
              </span>
              <span v-if="post.last_comment_at" class="text-xs text-muted">
                {{ t('post.detail.lastReply', { time: formatRelativeTime(post.last_comment_at) }) }}
              </span>
            </div>
            <button
              v-if="post.version > 1"
              class="text-xs text-brand-600 hover:underline"
              @click="fetchHistory"
            >
              {{ t('post.detail.viewEditHistory') }}
            </button>
          </div>
        </BaseCard>

        <!-- Co-Author Manager (owner only) -->
        <BaseCard v-if="isAuthor" padding="lg" class="mb-6">
          <CoAuthorManager :post-id="postId" />
        </BaseCard>

        <!-- Comments Section -->
        <BaseCard padding="lg">
          <h3 class="text-lg font-semibold text-foreground mb-4">
            {{ t('post.detail.commentsTitle', { count: commentsTotal }) }}
          </h3>

          <div v-if="!post.allow_comments" class="text-sm text-muted mb-4">
            {{ t('post.detail.commentsDisabled') }}
          </div>

          <!-- Threaded comments -->
          <div class="space-y-4">
            <EmptyState v-if="commentTree.length === 0" :message="t('post.detail.noComments')" />
            <div
              v-for="node in commentTree"
              :key="node.root.id"
              class="border-b border-border last:border-0 pb-4 last:pb-0"
            >
              <!-- Root comment -->
              <div class="flex items-start gap-2 mb-1">
                <router-link :to="`/users/${node.root.author.id}`">
                  <BaseAvatar
                    :src="node.root.author.avatar_url"
                    :name="node.root.author.display_name"
                    size="sm"
                  />
                </router-link>
                <div class="flex-1 min-w-0">
                  <div class="flex items-center gap-2">
                    <router-link
                      :to="`/users/${node.root.author.id}`"
                      class="text-sm font-medium text-foreground hover:text-brand-600 hover:underline"
                    >
                      {{ node.root.author.display_name }}
                    </router-link>
                    <span class="text-xs text-muted">{{
                      formatDateTime(node.root.created_at, locale)
                    }}</span>
                  </div>
                  <template v-if="editingComment === node.root.id">
                    <textarea
                      v-model="editCommentContent"
                      rows="3"
                      class="w-full min-h-[80px] px-3 py-2 border border-border rounded-lg text-sm mb-2 text-foreground focus:ring-2 focus:ring-brand-500 focus:border-transparent outline-none mt-1"
                    ></textarea>
                    <div class="flex gap-2">
                      <BaseButton
                        size="sm"
                        :loading="editCommentSaving"
                        @click="saveEditComment(node.root.id)"
                      >
                        {{ t('post.comment.save') }}
                      </BaseButton>
                      <BaseButton size="sm" variant="secondary" @click="cancelEditComment">{{
                        t('post.comment.cancel')
                      }}</BaseButton>
                    </div>
                  </template>
                  <template v-else>
                    <p
                      class="text-sm text-foreground/80 break-words mb-2"
                      v-html="
                        renderMentions(DOMPurify.sanitize(node.root.content), node.root.mentions)
                      "
                    ></p>
                    <div class="flex items-center gap-3">
                      <ReactionPicker
                        :reactions="node.root.reactions"
                        :user-id="auth.user?.id ?? null"
                        :readonly="!auth.isAuthenticated || auth.isGuest"
                        @toggle="(r) => toggleReactionHandler(node.root.id, r)"
                      />
                      <button
                        v-if="post.allow_comments && auth.isAuthenticated && !auth.isGuest"
                        @click="handleReply(node.root.id)"
                        class="text-xs text-muted hover:text-brand-600"
                      >
                        {{ t('post.comment.reply') }}
                      </button>
                      <button
                        v-if="canEditComment(node.root)"
                        @click="startEditComment(node.root)"
                        class="text-xs text-muted hover:text-brand-600"
                      >
                        {{ t('post.comment.edit') }}
                      </button>
                      <button
                        v-if="canDeleteComment(node.root)"
                        @click="confirmDeleteComment(node.root.id)"
                        class="text-xs text-danger-500 hover:text-danger-600"
                      >
                        {{ t('post.comment.delete') }}
                      </button>
                    </div>
                  </template>

                  <!-- Inline reply input -->
                  <div v-if="inlineReplyTo === node.root.id" class="mt-2">
                    <textarea
                      v-model="inlineReplyContent"
                      rows="2"
                      :placeholder="t('post.comment.writeReply')"
                      class="w-full min-h-[80px] px-3 py-2 border border-border rounded-lg focus:ring-2 focus:ring-brand-500 focus:border-transparent outline-none text-sm mb-2 text-foreground"
                    ></textarea>
                    <div class="flex gap-2">
                      <BaseButton
                        size="sm"
                        :loading="commentSaving"
                        :disabled="!inlineReplyContent.trim()"
                        @click="submitInlineReply"
                      >
                        {{ t('post.comment.replyButton') }}
                      </BaseButton>
                      <BaseButton size="sm" variant="secondary" @click="inlineReplyTo = null">
                        {{ t('post.comment.cancel') }}
                      </BaseButton>
                    </div>
                  </div>
                </div>
              </div>

              <!-- Reply comments -->
              <div
                v-for="reply in node.replies"
                :key="reply.id"
                class="pl-4 sm:pl-8 border-l-2 border-brand-100 mt-3"
              >
                <div class="flex items-start gap-2 mb-1">
                  <router-link :to="`/users/${reply.author.id}`">
                    <BaseAvatar
                      :src="reply.author.avatar_url"
                      :name="reply.author.display_name"
                      size="sm"
                    />
                  </router-link>
                  <div class="flex-1 min-w-0">
                    <div class="flex items-center gap-2">
                      <router-link
                        :to="`/users/${reply.author.id}`"
                        class="text-sm font-medium text-foreground hover:text-brand-600 hover:underline"
                      >
                        {{ reply.author.display_name }}
                      </router-link>
                      <span class="text-xs text-muted">{{
                        formatDateTime(reply.created_at, locale)
                      }}</span>
                    </div>
                    <template v-if="editingComment === reply.id">
                      <textarea
                        v-model="editCommentContent"
                        rows="3"
                        class="w-full min-h-[80px] px-3 py-2 border border-border rounded-lg text-sm mb-2 text-foreground focus:ring-2 focus:ring-brand-500 focus:border-transparent outline-none mt-1"
                      ></textarea>
                      <div class="flex gap-2">
                        <BaseButton
                          size="sm"
                          :loading="editCommentSaving"
                          @click="saveEditComment(reply.id)"
                        >
                          {{ t('post.comment.save') }}
                        </BaseButton>
                        <BaseButton size="sm" variant="secondary" @click="cancelEditComment">{{
                          t('post.comment.cancel')
                        }}</BaseButton>
                      </div>
                    </template>
                    <template v-else>
                      <p
                        class="text-sm text-foreground/80 break-words mb-2"
                        v-html="renderMentions(DOMPurify.sanitize(reply.content), reply.mentions)"
                      ></p>
                      <div class="flex items-center gap-3">
                        <ReactionPicker
                          :reactions="reply.reactions"
                          :user-id="auth.user?.id ?? null"
                          :readonly="!auth.isAuthenticated || auth.isGuest"
                          @toggle="(r) => toggleReactionHandler(reply.id, r)"
                        />
                        <button
                          v-if="canEditComment(reply)"
                          @click="startEditComment(reply)"
                          class="text-xs text-muted hover:text-brand-600"
                        >
                          {{ t('post.comment.edit') }}
                        </button>
                        <button
                          v-if="canDeleteComment(reply)"
                          @click="confirmDeleteComment(reply.id)"
                          class="text-xs text-danger-500 hover:text-danger-600"
                        >
                          {{ t('post.comment.delete') }}
                        </button>
                      </div>
                    </template>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <BasePagination
            v-if="commentTotalPages > 1"
            :current-page="commentPage"
            :total-pages="commentTotalPages"
            @update:current-page="goToCommentPage"
            class="mt-4"
          />

          <!-- Always-visible comment input -->
          <div
            v-if="post.allow_comments && auth.isAuthenticated && !auth.isGuest"
            class="mt-6 border-t border-border pt-4"
          >
            <BaseAlert v-if="commentMessage" type="error" class="mb-2">{{
              commentMessage
            }}</BaseAlert>
            <textarea
              v-model="newComment"
              rows="3"
              :placeholder="t('post.comment.writeComment')"
              class="w-full min-h-[80px] px-3 py-2 border border-border rounded-lg focus:ring-2 focus:ring-brand-500 focus:border-transparent outline-none text-sm mb-2 text-foreground"
            ></textarea>
            <BaseButton
              size="sm"
              :loading="commentSaving"
              :disabled="!newComment.trim()"
              @click="submitComment"
              >{{ t('post.comment.postComment') }}</BaseButton
            >
          </div>
        </BaseCard>
      </div>
    </template>

    <!-- History Modal -->
    <BaseModal v-model="showHistory" :title="t('post.history.title')" size="xl">
      <div v-if="history.length === 0" class="text-muted text-sm text-center py-4">
        {{ t('post.history.empty') }}
      </div>
      <div v-for="item in history" :key="item.id" class="border-b border-border last:border-0 py-4">
        <div class="flex justify-between items-center mb-2">
          <span class="text-sm font-medium text-foreground/80">{{
            t('post.history.version', { version: item.version })
          }}</span>
          <span class="text-xs text-muted">{{ formatDateTime(item.edited_at, locale) }}</span>
        </div>
        <h4 class="text-sm font-semibold text-foreground mb-1">{{ item.title }}</h4>
        <div
          class="text-sm text-muted prose prose-sm max-w-none"
          v-html="DOMPurify.sanitize(item.content)"
        ></div>
      </div>
    </BaseModal>

    <!-- Report Modal -->
    <BaseModal v-model="showReportModal" :title="t('post.reportDialog.title')">
      <BaseAlert v-if="reportMessage" type="error" class="mb-3">{{ reportMessage }}</BaseAlert>
      <textarea
        v-model="reportReason"
        rows="4"
        :placeholder="t('post.reportDialog.placeholder')"
        class="w-full px-3 py-2 border border-border rounded-lg focus:ring-2 focus:ring-brand-500 focus:border-transparent outline-none text-sm text-foreground mb-3"
      ></textarea>
      <template #footer>
        <BaseButton variant="secondary" @click="showReportModal = false">{{
          t('common.cancel')
        }}</BaseButton>
        <BaseButton
          class="bg-orange-600 hover:bg-orange-700 text-white"
          :loading="reportSaving"
          :disabled="!reportReason.trim()"
          @click="submitReport"
          >{{ t('post.reportDialog.submit') }}</BaseButton
        >
      </template>
    </BaseModal>

    <!-- Delete Post Confirmation -->
    <BaseModal v-model="showDeletePostConfirm" :title="t('post.deleteDialog.title')" size="sm">
      <p class="text-sm text-muted">
        {{ t('post.deleteDialog.message') }}
      </p>
      <template #footer>
        <BaseButton variant="secondary" @click="showDeletePostConfirm = false">{{
          t('common.cancel')
        }}</BaseButton>
        <BaseButton variant="danger" @click="deletePostHandler">{{
          t('common.delete')
        }}</BaseButton>
      </template>
    </BaseModal>

    <!-- Delete Comment Confirmation -->
    <BaseModal
      v-model="showDeleteCommentConfirm"
      :title="t('post.deleteCommentDialog.title')"
      size="sm"
    >
      <p class="text-sm text-muted">
        {{ t('post.deleteCommentDialog.message') }}
      </p>
      <template #footer>
        <BaseButton variant="secondary" @click="showDeleteCommentConfirm = false">{{
          t('common.cancel')
        }}</BaseButton>
        <BaseButton variant="danger" @click="deleteCommentHandler">{{
          t('common.delete')
        }}</BaseButton>
      </template>
    </BaseModal>

    <!-- Leave Page Confirmation (unsaved edits) -->
    <BaseModal
      v-model="showLeaveConfirm"
      :title="t('post.detail.unsavedChangesTitle')"
      size="sm"
      persistent
    >
      <p class="text-sm text-muted">
        {{ t('post.detail.unsavedChangesMessage') }}
      </p>
      <template #footer>
        <BaseButton variant="secondary" @click="cancelLeave">{{ t('common.cancel') }}</BaseButton>
        <BaseButton variant="danger" @click="confirmLeave">{{
          t('post.detail.leaveBtn')
        }}</BaseButton>
      </template>
    </BaseModal>

    <FloatingCreateButton to="/forum/create" />
  </div>
</template>

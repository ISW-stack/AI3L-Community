<script setup lang="ts">
import { computed, defineAsyncComponent } from 'vue'
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

const { t } = useI18n()
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
  showReportModal,
  reportReason,
  reportSaving,
  reportMessage,
  canReport,
  pinSaving,
  canModify,
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
  getPostReactionCount,
  hasPostReacted,
  getReactionCount,
  hasReacted,
  canEditComment,
  startEditComment,
  cancelEditComment,
  saveEditComment,
  handleReply,
} = usePostDetail({ postId, auth, router })
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
          <BaseButton variant="secondary" @click="editing = false">{{
            t('common.cancel')
          }}</BaseButton>
        </div>
      </div>

      <!-- View mode -->
      <div v-else>
        <div class="mb-6">
          <router-link to="/forum" class="text-sm text-brand-600 hover:underline"
            >&larr; {{ t('post.detail.backToForum') }}</router-link
          >
        </div>

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
                <span>{{ new Date(post.created_at).toLocaleString() }}</span>
                <BaseBadge v-if="post.category_name">{{ post.category_name }}</BaseBadge>
                <span
                  v-if="post.is_pinned"
                  class="inline-flex items-center gap-1 text-xs font-medium text-amber-600"
                >
                  <svg
                    class="w-3 h-3"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    stroke-width="2"
                    stroke-linecap="round"
                    stroke-linejoin="round"
                  >
                    <path d="M12 17v5" />
                    <path
                      d="M9 10.76a2 2 0 0 1-1.11 1.79l-1.78.9A2 2 0 0 0 5 15.24V16a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-.76a2 2 0 0 0-1.11-1.79l-1.78-.9A2 2 0 0 1 15 10.76V7a1 1 0 0 1 1-1 1 1 0 0 0 1-1V4a2 2 0 0 0-2-2H9a2 2 0 0 0-2 2v1a1 1 0 0 0 1 1 1 1 0 0 1 1 1z"
                    />
                  </svg>
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

          <div ref="postContentRef" class="prose prose-sm max-w-none text-foreground/80 mb-4">
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

          <!-- Post Reactions -->
          <div v-if="auth.isAuthenticated && !auth.isGuest" class="flex items-center gap-1.5 mb-3">
            <button
              v-for="r in ['LIKE', 'SMILE', 'CRY']"
              :key="r"
              type="button"
              :aria-label="`React with ${r}`"
              class="text-xs px-2 py-1 rounded-full transition-colors inline-flex items-center gap-1"
              :class="
                hasPostReacted(r)
                  ? 'bg-brand-100 text-brand-700'
                  : 'bg-surface-alt text-muted hover:bg-gray-100'
              "
              @click="togglePostReactionHandler(r)"
            >
              {{ r === 'LIKE' ? '&#128077;' : r === 'SMILE' ? '&#128522;' : '&#128546;' }}
              {{ getPostReactionCount(r) || '' }}
            </button>
          </div>
          <div
            v-else-if="post.reactions && Object.keys(post.reactions).length"
            class="flex items-center gap-1.5 mb-3"
          >
            <span
              v-for="r in ['LIKE', 'SMILE', 'CRY']"
              :key="r"
              class="text-xs px-2 py-1 rounded-full bg-surface-alt text-muted inline-flex items-center gap-1"
              :class="{ hidden: !getPostReactionCount(r) }"
            >
              {{ r === 'LIKE' ? '&#128077;' : r === 'SMILE' ? '&#128522;' : '&#128546;' }}
              {{ getPostReactionCount(r) }}
            </span>
          </div>

          <!-- Action Bar -->
          <div class="flex items-center justify-between border-t border-border pt-3">
            <div class="flex items-center gap-4">
              <span class="text-sm text-muted">
                {{ post.comment_count }} comment{{ post.comment_count !== 1 ? 's' : '' }}
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
                      new Date(node.root.created_at).toLocaleString()
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
                      class="text-sm text-foreground/80 mb-2"
                      v-html="
                        renderMentions(DOMPurify.sanitize(node.root.content), node.root.mentions)
                      "
                    ></p>
                    <div class="flex items-center gap-3">
                      <template v-if="auth.isAuthenticated && !auth.isGuest">
                        <button
                          v-for="r in ['LIKE', 'SMILE', 'CRY']"
                          :key="r"
                          @click="toggleReactionHandler(node.root.id, r)"
                          class="text-xs px-2 py-0.5 rounded-full transition"
                          :class="
                            hasReacted(node.root, r)
                              ? 'bg-brand-100 text-brand-700'
                              : 'bg-surface-alt text-muted hover:bg-gray-100'
                          "
                        >
                          {{
                            r === 'LIKE' ? '&#128077;' : r === 'SMILE' ? '&#128522;' : '&#128546;'
                          }}
                          {{ getReactionCount(node.root, r) || '' }}
                        </button>
                      </template>
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
                class="pl-8 border-l-2 border-brand-100 mt-3"
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
                        new Date(reply.created_at).toLocaleString()
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
                        class="text-sm text-foreground/80 mb-2"
                        v-html="renderMentions(DOMPurify.sanitize(reply.content), reply.mentions)"
                      ></p>
                      <div class="flex items-center gap-3">
                        <template v-if="auth.isAuthenticated && !auth.isGuest">
                          <button
                            v-for="r in ['LIKE', 'SMILE', 'CRY']"
                            :key="r"
                            @click="toggleReactionHandler(reply.id, r)"
                            class="text-xs px-2 py-0.5 rounded-full transition"
                            :class="
                              hasReacted(reply, r)
                                ? 'bg-brand-100 text-brand-700'
                                : 'bg-surface-alt text-muted hover:bg-gray-100'
                            "
                          >
                            {{
                              r === 'LIKE' ? '&#128077;' : r === 'SMILE' ? '&#128522;' : '&#128546;'
                            }}
                            {{ getReactionCount(reply, r) || '' }}
                          </button>
                        </template>
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

    <FloatingCreateButton to="/forum/create" />
  </div>
</template>

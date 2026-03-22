<script setup lang="ts">
import { ref, watch, onMounted, onUnmounted, computed, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useDMStore } from '@/stores/dm'
import { useAuthStore } from '@/stores/auth'
import { useToastStore } from '@/stores/toast'
import { usePagination } from '@/composables/usePagination'
import { getErrorMessage } from '@/utils/error'
import { getPreferences, updatePreferences } from '@/api/users'
import * as dmApi from '@/api/dm'
import ConversationList from '@/components/dm/ConversationList.vue'
import MessageThread from '@/components/dm/MessageThread.vue'
import MessageInput from '@/components/dm/MessageInput.vue'
import BaseBreadcrumb from '@/components/base/BaseBreadcrumb.vue'
import BaseModal from '@/components/base/BaseModal.vue'
import { MessageSquare, ArrowLeft, Lock, Unlock } from 'lucide-vue-next'

const route = useRoute()
const router = useRouter()
const dmStore = useDMStore()
const auth = useAuthStore()
const toast = useToastStore()

const convPagination = usePagination(30)
const msgPagination = usePagination(30)

const messageThreadRef = ref<InstanceType<typeof MessageThread> | null>(null)
const sending = ref(false)
const recalling = ref(false)
const recallTargetId = ref<string | null>(null)
const editingMessageId = ref<string | null>(null)
const editingContent = ref('')
const activeOtherUserId = ref<string | null>(null)
const currentMsgPage = ref(1)

const currentUserId = computed(() => auth.user?.id ?? '')
const hasMoreMessages = computed(() => dmStore.messages.length < dmStore.messagesTotal)

const dmFriendsOnly = ref(false)
const dmFriendsOnlyLoading = ref(false)

async function toggleDmFriendsOnly() {
  const newValue = !dmFriendsOnly.value
  dmFriendsOnly.value = newValue
  dmFriendsOnlyLoading.value = true
  try {
    await updatePreferences({ dm_friends_only: newValue })
  } catch {
    dmFriendsOnly.value = !newValue
  } finally {
    dmFriendsOnlyLoading.value = false
  }
}

const breadcrumbs = [{ label: 'Home', to: '/' }, { label: 'Messages' }]

// Load conversations on mount
onMounted(async () => {
  dmStore.setCurrentUserId(auth.user?.id ?? '')

  // Load DM privacy preference
  try {
    const prefs = await getPreferences()
    dmFriendsOnly.value = prefs.dm_friends_only
  } catch {
    // Non-critical
  }

  await dmStore.fetchConversations(1, convPagination.pageSize)
  convPagination.updateFromResponse(dmStore.conversationsTotal)

  // If route has userId param, open that conversation
  const userId = route.params.userId as string | undefined
  if (userId) {
    openConversationByUserId(userId)
  }
})

onUnmounted(() => {
  dmStore.setActiveConversation(null)
  dmStore.clearMessages()
})

// Watch route changes for userId param
watch(
  () => route.params.userId,
  (userId) => {
    if (userId && typeof userId === 'string') {
      openConversationByUserId(userId)
    }
  },
)

function openConversationByUserId(userId: string) {
  activeOtherUserId.value = userId
  const conv = dmStore.conversations.find((c) => c.other_user.id === userId)
  if (conv) {
    selectConversation(conv.id, userId)
  } else {
    // No existing conversation yet — just set active user, messages will start on first send
    dmStore.setActiveConversation(null)
    dmStore.messages = []
    dmStore.messagesTotal = 0
  }
}

async function selectConversation(conversationId: string, otherUserId: string) {
  activeOtherUserId.value = otherUserId
  dmStore.setActiveConversation(conversationId)
  editingMessageId.value = null
  editingContent.value = ''
  currentMsgPage.value = 1
  msgPagination.resetPage()

  await dmStore.fetchMessages(conversationId, 1, msgPagination.pageSize)
  msgPagination.updateFromResponse(dmStore.messagesTotal)

  // Show toast if messages failed to load (e.g. conversation was deleted)
  if (dmStore.error) {
    toast.show(dmStore.error, 'error')
    return
  }

  // Mark as read — skip API call if already read
  const convIdx = dmStore.conversations.findIndex((c) => c.id === conversationId)
  if (convIdx >= 0 && dmStore.conversations[convIdx].unread_count > 0) {
    try {
      await dmApi.markConversationRead(conversationId)
      const prevUnread = dmStore.conversations[convIdx].unread_count
      dmStore.unreadCount = Math.max(0, dmStore.unreadCount - prevUnread)
      dmStore.conversations[convIdx] = {
        ...dmStore.conversations[convIdx],
        unread_count: 0,
      }
    } catch {
      // Non-critical, ignore
    }
  }

  await nextTick()
  if (typeof messageThreadRef.value?.scrollToBottom === 'function') {
    messageThreadRef.value.scrollToBottom()
  }
}

function handleSelectConversation(conversationId: string, otherUserId: string) {
  router.push(`/messages/${otherUserId}`)
  selectConversation(conversationId, otherUserId)
}

async function handleLoadMore() {
  if (!dmStore.activeConversationId || !hasMoreMessages.value || dmStore.messagesLoading) return
  currentMsgPage.value += 1
  await dmStore.fetchMessages(
    dmStore.activeConversationId,
    currentMsgPage.value,
    msgPagination.pageSize,
  )
}

async function handleSend(content: string, file?: File) {
  if (!activeOtherUserId.value) return
  sending.value = true
  try {
    if (editingMessageId.value) {
      // Edit mode
      await dmApi.editMessage(editingMessageId.value, content)
      editingMessageId.value = null
      editingContent.value = ''
      // Refresh messages
      if (dmStore.activeConversationId) {
        await dmStore.fetchMessages(dmStore.activeConversationId, 1, msgPagination.pageSize)
      }
    } else {
      // Send new message
      const msg = await dmApi.sendMessage(activeOtherUserId.value, content || undefined, file)
      // If no active conversation, set it from the response
      if (!dmStore.activeConversationId) {
        dmStore.setActiveConversation(msg.conversation_id)
        // Refresh conversations to get the new one
        await dmStore.fetchConversations(1, convPagination.pageSize)
      }
      // Add message to list
      const exists = dmStore.messages.some((m) => m.id === msg.id)
      if (!exists) {
        dmStore.messages.push(msg)
      }
      // Update conversation
      const conv = dmStore.conversations.find((c) => c.id === msg.conversation_id)
      if (conv) {
        conv.last_message = msg
        conv.updated_at = msg.created_at
      }
    }
  } catch (e: unknown) {
    toast.show(parseDMError(e, 'Failed to send message.'), 'error')
  } finally {
    sending.value = false
  }
}

function handleEditMessage(messageId: string, currentContent: string) {
  editingMessageId.value = messageId
  editingContent.value = currentContent
}

function parseDMError(e: unknown, fallback: string): string {
  if (e && typeof e === 'object' && 'response' in e) {
    const resp = (e as { response?: { data?: { detail?: { code?: string; message?: string } } } })
      .response
    const code = resp?.data?.detail?.code
    if (code === 'DM_001') {
      const msg = resp?.data?.detail?.message ?? ''
      if (msg.toLowerCase().includes('friend'))
        return 'This user only accepts messages from friends.'
      return 'You cannot message this user.'
    }
    if (code === 'DM_002') return 'The edit/recall window (12 hours) has expired.'
    if (code === 'DM_003') return 'You cannot message yourself.'
    if (code === 'DM_004') return 'Storage quota exceeded (1 GB limit).'
    if (code === 'DM_005') return 'File too large (max 10 MB).'
    if (code === 'SYS_422') {
      const msg = resp?.data?.detail?.message ?? ''
      if (msg.includes('already recalled')) return 'This message has already been recalled.'
      if (msg.includes('recalled message')) return 'Cannot edit a recalled message.'
    }
    if (code === 'SYS_403') {
      const msg = resp?.data?.detail?.message ?? ''
      if (msg.includes('edit')) return 'You can only edit your own messages.'
      if (msg.includes('recall')) return 'You can only recall your own messages.'
      return 'You do not have permission to perform this action.'
    }
  }
  return getErrorMessage(e, fallback)
}

function handleRecallMessage(messageId: string) {
  recallTargetId.value = messageId
}

function cancelRecall() {
  recallTargetId.value = null
}

async function confirmRecall() {
  if (!recallTargetId.value) return
  const messageId = recallTargetId.value
  recalling.value = true

  // Save original for rollback
  const idx = dmStore.messages.findIndex((m) => m.id === messageId)
  const original = idx >= 0 ? { ...dmStore.messages[idx] } : null

  // Optimistic update
  if (idx >= 0) {
    dmStore.messages[idx] = {
      ...dmStore.messages[idx],
      is_recalled: true,
      content: null,
      attachment_url: null,
      attachment_name: null,
      attachment_size: null,
      attachment_expires_at: null,
    }
  }

  try {
    await dmApi.recallMessage(messageId)
    recallTargetId.value = null
  } catch (e: unknown) {
    // Rollback — re-find by ID since WS events may have shifted indices
    if (original) {
      const rollbackIdx = dmStore.messages.findIndex((m) => m.id === messageId)
      if (rollbackIdx >= 0) {
        dmStore.messages[rollbackIdx] = original
      }
    }
    toast.show(parseDMError(e, 'Failed to recall message.'), 'error')
  } finally {
    recalling.value = false
  }
}

function handleCancelEdit() {
  editingMessageId.value = null
  editingContent.value = ''
}

function handleBackToList() {
  dmStore.setActiveConversation(null)
  activeOtherUserId.value = null
  router.push('/messages')
}

const activeConvUser = computed(() => {
  if (dmStore.activeConversationId) {
    const conv = dmStore.conversations.find((c) => c.id === dmStore.activeConversationId)
    return conv?.other_user ?? null
  }
  return null
})
</script>

<template>
  <div class="max-w-6xl mx-auto px-3 sm:px-4 py-4 sm:py-6 overflow-x-hidden w-full">
    <BaseBreadcrumb :items="breadcrumbs" />
    <div class="flex items-center justify-between mb-4 sm:mb-6">
      <h1 class="text-xl sm:text-2xl font-bold text-foreground">Messages</h1>
      <button
        :disabled="dmFriendsOnlyLoading"
        :title="
          dmFriendsOnly
            ? 'Friends-only mode ON — only friends can message you'
            : 'Anyone can message you'
        "
        class="flex items-center gap-1.5 sm:gap-2 px-2.5 sm:px-3 py-1.5 text-xs sm:text-sm font-medium rounded-lg border transition"
        :class="
          dmFriendsOnly
            ? 'border-brand-300 bg-brand-50 text-brand-700 hover:bg-brand-100'
            : 'border-border text-muted hover:bg-surface-alt'
        "
        @click="toggleDmFriendsOnly"
        data-testid="dm-friends-only-toggle"
      >
        <Lock v-if="dmFriendsOnly" class="w-4 h-4" aria-hidden="true" />
        <Unlock v-else class="w-4 h-4" aria-hidden="true" />
        {{ dmFriendsOnly ? 'Friends only' : 'Open to all' }}
      </button>
    </div>

    <div
      class="flex bg-surface border border-border rounded-lg shadow overflow-hidden"
      style="height: calc(100vh - 200px); height: calc(100dvh - 200px)"
    >
      <!-- Left: Conversation List -->
      <div
        class="w-full md:w-80 md:border-r border-border shrink-0 overflow-y-auto"
        :class="{ 'hidden md:block': dmStore.activeConversationId || activeOtherUserId }"
      >
        <ConversationList
          :conversations="dmStore.conversations"
          :active-id="dmStore.activeConversationId"
          :loading="dmStore.loading"
          @select="handleSelectConversation"
        />
      </div>

      <!-- Right: Messages or Empty State -->
      <div
        class="w-full md:flex-1 flex flex-col min-w-0 min-h-0"
        :class="{ 'hidden md:flex': !dmStore.activeConversationId && !activeOtherUserId }"
      >
        <template v-if="dmStore.activeConversationId || activeOtherUserId">
          <!-- Thread header -->
          <div class="flex items-center gap-3 px-3 sm:px-4 py-3 border-b border-border bg-surface">
            <button
              class="md:hidden p-2 -ml-2 text-muted hover:text-foreground active:bg-surface-alt rounded-lg transition touch-manipulation"
              @click="handleBackToList"
              aria-label="Back to conversations"
            >
              <ArrowLeft class="w-5 h-5" aria-hidden="true" />
            </button>
            <router-link
              v-if="activeConvUser"
              :to="`/users/${activeConvUser.id}`"
              class="flex items-center gap-2 hover:opacity-75 transition min-w-0"
              :title="`View ${activeConvUser.display_name}'s profile`"
              data-testid="thread-header-profile-link"
            >
              <div
                class="w-8 h-8 rounded-full bg-gray-200 flex items-center justify-center overflow-hidden shrink-0"
              >
                <img
                  v-if="activeConvUser.avatar_url"
                  :src="activeConvUser.avatar_url"
                  class="w-8 h-8 rounded-full object-cover"
                  :alt="`${activeConvUser.display_name}'s avatar`"
                />
                <span v-else class="text-xs font-semibold text-muted">
                  {{ activeConvUser.display_name.charAt(0).toUpperCase() }}
                </span>
              </div>
              <span class="text-sm font-medium text-foreground truncate">
                {{ activeConvUser.display_name }}
              </span>
            </router-link>
            <span v-else class="text-sm font-medium text-foreground"> New Conversation </span>
          </div>

          <!-- Message thread -->
          <MessageThread
            ref="messageThreadRef"
            :messages="dmStore.messages"
            :current-user-id="currentUserId"
            :loading="dmStore.loading"
            :has-more="hasMoreMessages"
            @load-more="handleLoadMore"
            @edit="handleEditMessage"
            @recall="handleRecallMessage"
          />

          <!-- Message input -->
          <MessageInput
            :disabled="sending"
            :edit-mode="editingMessageId != null"
            :edit-content="editingContent"
            @send="handleSend"
            @cancel-edit="handleCancelEdit"
          />
        </template>

        <template v-else>
          <div class="flex-1 flex items-center justify-center">
            <div class="text-center px-4">
              <MessageSquare class="mx-auto h-12 w-12 text-gray-300 mb-4" aria-hidden="true" />
              <h3 class="text-sm font-medium text-foreground mb-1">Select a conversation</h3>
              <p class="text-sm text-muted">
                Choose a conversation from the list to start messaging.
              </p>
            </div>
          </div>
        </template>
      </div>
    </div>

    <BaseModal
      :model-value="recallTargetId != null"
      title="Recall Message"
      size="sm"
      @update:model-value="cancelRecall"
    >
      <p class="text-sm text-muted mb-4">
        Are you sure you want to recall this message? The other party will see "Message recalled".
      </p>
      <div class="flex justify-end gap-3">
        <button
          @click="cancelRecall"
          class="px-4 py-2 text-sm font-medium text-foreground bg-surface-alt border border-border rounded-lg hover:bg-gray-100 transition"
        >
          Cancel
        </button>
        <button
          @click="confirmRecall"
          :disabled="recalling"
          class="px-4 py-2 text-sm font-medium text-white bg-danger-600 rounded-lg hover:bg-danger-700 transition disabled:opacity-50"
        >
          {{ recalling ? 'Recalling...' : 'Recall' }}
        </button>
      </div>
    </BaseModal>
  </div>
</template>

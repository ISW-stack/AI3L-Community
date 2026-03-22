import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { Conversation, DMMessage } from '@/types/dm'
import * as dmApi from '@/api/dm'
import { getErrorMessage } from '@/utils/error'

export const useDMStore = defineStore('dm', () => {
  const conversations = ref<Conversation[]>([])
  const conversationsTotal = ref(0)
  const unreadCount = ref(0)
  const activeConversationId = ref<string | null>(null)
  const messages = ref<DMMessage[]>([])
  const messagesTotal = ref(0)
  const conversationsLoading = ref(false)
  const messagesLoading = ref(false)
  const loading = computed(() => conversationsLoading.value || messagesLoading.value)
  const error = ref<string | null>(null)
  const currentUserId = ref('')

  // BUG-1: fetchId guards to discard stale responses
  let _convFetchId = 0
  let _msgFetchId = 0

  function setCurrentUserId(id: string) {
    currentUserId.value = id
  }

  async function fetchUnreadCount() {
    try {
      const res = await dmApi.getUnreadCount()
      unreadCount.value = res.unread_count
    } catch (e: unknown) {
      if (import.meta.env.DEV) console.error('Failed to fetch DM unread count:', getErrorMessage(e))
    }
  }

  async function fetchConversations(page = 1, pageSize = 30) {
    const fetchId = ++_convFetchId
    conversationsLoading.value = true
    error.value = null
    try {
      const res = await dmApi.listConversations({ page, page_size: pageSize })
      if (fetchId !== _convFetchId) return // stale response, discard
      conversations.value = res.conversations
      conversationsTotal.value = res.total
    } catch (e: unknown) {
      if (fetchId !== _convFetchId) return
      error.value = getErrorMessage(e, 'Failed to load conversations.')
    } finally {
      if (fetchId === _convFetchId) conversationsLoading.value = false
    }
  }

  async function fetchMessages(conversationId: string, page = 1, pageSize = 30) {
    const fetchId = ++_msgFetchId
    messagesLoading.value = true
    error.value = null
    try {
      const res = await dmApi.listMessages(conversationId, { page, page_size: pageSize })
      if (fetchId !== _msgFetchId) return // stale response, discard
      // Backend returns messages ORDER BY created_at DESC (newest first).
      // Reverse to chronological order: oldest first → newest last (chat convention).
      const chronological = res.messages.slice().reverse()
      if (page === 1) {
        messages.value = chronological
      } else {
        // Prepend older messages (pagination loads older pages)
        const existingIds = new Set(messages.value.map((m) => m.id))
        const newMessages = chronological.filter((m) => !existingIds.has(m.id))
        messages.value = [...newMessages, ...messages.value]
      }
      messagesTotal.value = res.total
    } catch (e: unknown) {
      if (fetchId !== _msgFetchId) return
      const errMsg = getErrorMessage(e, 'Failed to load messages.')
      error.value = errMsg
      // BUG-5: If 404, clear active conversation and set user-friendly message
      if (e && typeof e === 'object' && 'response' in e) {
        const axiosErr = e as { response?: { status?: number } }
        if (axiosErr.response?.status === 404) {
          error.value = 'This conversation no longer exists.'
          activeConversationId.value = null
          messages.value = []
          messagesTotal.value = 0
        }
      }
    } finally {
      if (fetchId === _msgFetchId) messagesLoading.value = false
    }
  }

  function addFromWebSocket(message: DMMessage) {
    // Update conversation list
    const convIdx = conversations.value.findIndex((c) => c.id === message.conversation_id)

    // BUG-5: Unknown conversation — refetch list
    if (convIdx < 0) {
      fetchConversations(1, 30)
      if (message.sender.id !== currentUserId.value) {
        unreadCount.value += 1
      }
      // Still add to messages if viewing this conversation
      if (activeConversationId.value === message.conversation_id) {
        const exists = messages.value.some((m) => m.id === message.id)
        if (!exists) {
          messages.value = [...messages.value, message]
        }
      }
      return
    }

    // BUG-2: Own message echoed back via WS — dedup only, no unread increment
    if (message.sender.id === currentUserId.value) {
      // Update conversation list (move to top, update last_message) but don't touch unread
      const updated = {
        ...conversations.value[convIdx],
        last_message: message,
        updated_at: message.created_at,
      }
      conversations.value = [updated, ...conversations.value.filter((_, i) => i !== convIdx)]
      // Only add to messages if viewing this conversation and not already present
      if (activeConversationId.value === message.conversation_id) {
        const exists = messages.value.some((m) => m.id === message.id)
        if (!exists) {
          messages.value = [...messages.value, message]
        }
      }
      return
    }

    // Other user's message — immutable array update
    const updated = {
      ...conversations.value[convIdx],
      last_message: message,
      updated_at: message.created_at,
      unread_count:
        activeConversationId.value !== message.conversation_id
          ? (conversations.value[convIdx].unread_count || 0) + 1
          : conversations.value[convIdx].unread_count,
    }
    conversations.value = [updated, ...conversations.value.filter((_, i) => i !== convIdx)]

    // If viewing this conversation, add message to messages array
    if (activeConversationId.value === message.conversation_id) {
      const exists = messages.value.some((m) => m.id === message.id)
      if (!exists) {
        messages.value = [...messages.value, message]
      }
    } else {
      // Increment global unread count
      unreadCount.value += 1
    }
  }

  function updateFromWebSocket(message: DMMessage) {
    const idx = messages.value.findIndex((m) => m.id === message.id)
    if (idx >= 0) {
      messages.value[idx] = message
    }
    // Update last_message in conversations if applicable
    const conv = conversations.value.find((c) => c.id === message.conversation_id)
    if (conv && conv.last_message?.id === message.id) {
      conv.last_message = message
    }
  }

  function recallFromWebSocket(messageId: string, conversationId: string) {
    const idx = messages.value.findIndex((m) => m.id === messageId)
    if (idx >= 0) {
      messages.value[idx] = {
        ...messages.value[idx],
        is_recalled: true,
        content: null,
        attachment_url: null,
        attachment_name: null,
      }
    }
    // Update last_message in conversations if applicable
    const conv = conversations.value.find((c) => c.id === conversationId)
    if (conv && conv.last_message?.id === messageId) {
      conv.last_message = {
        ...conv.last_message,
        is_recalled: true,
        content: null,
        attachment_url: null,
        attachment_name: null,
      }
    }
  }

  // BUG-4: Immutable update pattern for reactivity
  function readReceiptFromWebSocket(conversationId: string, readAt: string) {
    if (activeConversationId.value === conversationId) {
      messages.value = messages.value.map((msg) =>
        !msg.read_at ? { ...msg, read_at: readAt } : msg,
      )
    }
    // Calculate delta before updating conversations (no side-effects in .map)
    const conv = conversations.value.find((c) => c.id === conversationId)
    const prevUnread = conv?.unread_count ?? 0
    conversations.value = conversations.value.map((c) =>
      c.id === conversationId ? { ...c, unread_count: 0 } : c,
    )
    unreadCount.value = Math.max(0, unreadCount.value - prevUnread)
  }

  function setActiveConversation(id: string | null) {
    activeConversationId.value = id
  }

  function resetState() {
    conversations.value = []
    conversationsTotal.value = 0
    messages.value = []
    messagesTotal.value = 0
    unreadCount.value = 0
    activeConversationId.value = null
    conversationsLoading.value = false
    messagesLoading.value = false
    error.value = null
    currentUserId.value = ''
  }

  return {
    conversations,
    conversationsTotal,
    unreadCount,
    activeConversationId,
    messages,
    messagesTotal,
    conversationsLoading,
    messagesLoading,
    loading,
    error,
    currentUserId,
    fetchUnreadCount,
    fetchConversations,
    fetchMessages,
    addFromWebSocket,
    updateFromWebSocket,
    recallFromWebSocket,
    readReceiptFromWebSocket,
    setActiveConversation,
    setCurrentUserId,
    resetState,
  }
})

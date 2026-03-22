import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { Conversation, DMMessage } from '@/types/dm'
import * as dmApi from '@/api/dm'
import { getErrorMessage } from '@/utils/error'

const MAX_MESSAGES = 200

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
        if (newMessages.length > 0) {
          messages.value.unshift(...newMessages)
        }
        _trimMessages()
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

  function _trimMessages() {
    const overflow = messages.value.length - MAX_MESSAGES
    if (overflow > 0) {
      messages.value.splice(0, overflow)
    }
  }

  function _appendMessage(message: DMMessage) {
    if (!messages.value.some((m) => m.id === message.id)) {
      messages.value.push(message)
      _trimMessages()
    }
  }

  function _moveConversationToTop(convIdx: number) {
    if (convIdx > 0) {
      const conv = conversations.value[convIdx]
      conversations.value.splice(convIdx, 1)
      conversations.value.unshift(conv)
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
        _appendMessage(message)
      }
      return
    }

    const conv = conversations.value[convIdx]
    conv.last_message = message
    conv.updated_at = message.created_at

    // BUG-2: Own message echoed back via WS — dedup only, no unread increment
    if (message.sender.id === currentUserId.value) {
      _moveConversationToTop(convIdx)
      if (activeConversationId.value === message.conversation_id) {
        _appendMessage(message)
      }
      return
    }

    // Other user's message
    if (activeConversationId.value !== message.conversation_id) {
      conv.unread_count = (conv.unread_count || 0) + 1
    }
    _moveConversationToTop(convIdx)

    if (activeConversationId.value === message.conversation_id) {
      _appendMessage(message)
    } else {
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
      const msg = messages.value[idx]
      msg.is_recalled = true
      msg.content = null
      msg.attachment_url = null
      msg.attachment_name = null
    }
    // Update last_message in conversations if applicable
    const conv = conversations.value.find((c) => c.id === conversationId)
    if (conv?.last_message?.id === messageId) {
      conv.last_message.is_recalled = true
      conv.last_message.content = null
      conv.last_message.attachment_url = null
      conv.last_message.attachment_name = null
    }
  }

  function readReceiptFromWebSocket(conversationId: string, readAt: string) {
    if (activeConversationId.value === conversationId) {
      // Only mark own sent messages as read
      for (const msg of messages.value) {
        if (!msg.read_at && msg.sender.id === currentUserId.value) {
          msg.read_at = readAt
        }
      }
    }
    // Calculate delta before updating conversation
    const conv = conversations.value.find((c) => c.id === conversationId)
    const prevUnread = conv?.unread_count ?? 0
    if (conv) conv.unread_count = 0
    unreadCount.value = Math.max(0, unreadCount.value - prevUnread)
  }

  function setActiveConversation(id: string | null) {
    activeConversationId.value = id
  }

  function clearMessages() {
    messages.value = []
    messagesTotal.value = 0
  }

  function resetState() {
    conversations.value = []
    conversationsTotal.value = 0
    clearMessages()
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
    clearMessages,
    resetState,
  }
})

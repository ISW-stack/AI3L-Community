import { defineStore } from 'pinia'
import { ref } from 'vue'
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
  const loading = ref(false)
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
      console.error('Failed to fetch DM unread count:', getErrorMessage(e))
    }
  }

  async function fetchConversations(page = 1, pageSize = 30) {
    const fetchId = ++_convFetchId
    loading.value = true
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
      if (fetchId === _convFetchId) loading.value = false
    }
  }

  async function fetchMessages(conversationId: string, page = 1, pageSize = 30) {
    const fetchId = ++_msgFetchId
    loading.value = true
    error.value = null
    try {
      const res = await dmApi.listMessages(conversationId, { page, page_size: pageSize })
      if (fetchId !== _msgFetchId) return // stale response, discard
      if (page === 1) {
        messages.value = res.messages
      } else {
        // Prepend older messages (pagination loads older first)
        const existingIds = new Set(messages.value.map((m) => m.id))
        const newMessages = res.messages.filter((m) => !existingIds.has(m.id))
        messages.value = [...newMessages, ...messages.value]
      }
      messagesTotal.value = res.total
    } catch (e: unknown) {
      if (fetchId !== _msgFetchId) return
      const errMsg = getErrorMessage(e, 'Failed to load messages.')
      error.value = errMsg
      // BUG-5: If 404, clear active conversation
      if (e && typeof e === 'object' && 'response' in e) {
        const axiosErr = e as { response?: { status?: number } }
        if (axiosErr.response?.status === 404) {
          activeConversationId.value = null
          messages.value = []
          messagesTotal.value = 0
        }
      }
    } finally {
      if (fetchId === _msgFetchId) loading.value = false
    }
  }

  function addFromWebSocket(message: DMMessage) {
    // Update conversation list
    const convIdx = conversations.value.findIndex(
      (c) => c.id === message.conversation_id,
    )

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
          messages.value.push(message)
        }
      }
      return
    }

    // BUG-2: Own message echoed back via WS — dedup only, no unread increment
    if (message.sender.id === currentUserId.value) {
      // Update conversation list (move to top, update last_message) but don't touch unread
      const conv = { ...conversations.value[convIdx] }
      conv.last_message = message
      conv.updated_at = message.created_at
      conversations.value.splice(convIdx, 1)
      conversations.value.unshift(conv)
      // Only add to messages if viewing this conversation and not already present
      if (activeConversationId.value === message.conversation_id) {
        const exists = messages.value.some((m) => m.id === message.id)
        if (!exists) {
          messages.value.push(message)
        }
      }
      return
    }

    // Other user's message
    const conv = { ...conversations.value[convIdx] }
    conv.last_message = message
    conv.updated_at = message.created_at
    if (activeConversationId.value !== message.conversation_id) {
      conv.unread_count += 1
    }
    conversations.value.splice(convIdx, 1)
    conversations.value.unshift(conv)

    // If viewing this conversation, add message to messages array
    if (activeConversationId.value === message.conversation_id) {
      const exists = messages.value.some((m) => m.id === message.id)
      if (!exists) {
        messages.value.push(message)
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
    // Update conversation unread count (immutable pattern)
    conversations.value = conversations.value.map((c) => {
      if (c.id !== conversationId) return c
      const prevUnread = c.unread_count
      unreadCount.value = Math.max(0, unreadCount.value - prevUnread)
      return { ...c, unread_count: 0 }
    })
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
    loading.value = false
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

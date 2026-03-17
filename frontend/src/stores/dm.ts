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

  async function fetchUnreadCount() {
    try {
      const res = await dmApi.getUnreadCount()
      unreadCount.value = res.unread_count
    } catch (e: unknown) {
      console.error('Failed to fetch DM unread count:', getErrorMessage(e))
    }
  }

  async function fetchConversations(page = 1, pageSize = 30) {
    loading.value = true
    error.value = null
    try {
      const res = await dmApi.listConversations({ page, page_size: pageSize })
      conversations.value = res.conversations
      conversationsTotal.value = res.total
    } catch (e: unknown) {
      error.value = getErrorMessage(e, 'Failed to load conversations.')
    } finally {
      loading.value = false
    }
  }

  async function fetchMessages(conversationId: string, page = 1, pageSize = 30) {
    loading.value = true
    error.value = null
    try {
      const res = await dmApi.listMessages(conversationId, { page, page_size: pageSize })
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
      error.value = getErrorMessage(e, 'Failed to load messages.')
    } finally {
      loading.value = false
    }
  }

  function addFromWebSocket(message: DMMessage) {
    // Update conversation list
    const convIdx = conversations.value.findIndex(
      (c) => c.id === message.conversation_id,
    )
    if (convIdx >= 0) {
      const conv = { ...conversations.value[convIdx] }
      conv.last_message = message
      conv.updated_at = message.created_at
      if (activeConversationId.value !== message.conversation_id) {
        conv.unread_count += 1
      }
      conversations.value.splice(convIdx, 1)
      conversations.value.unshift(conv)
    }

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

  function readReceiptFromWebSocket(conversationId: string, readAt: string) {
    if (activeConversationId.value === conversationId) {
      for (const msg of messages.value) {
        if (!msg.read_at) {
          msg.read_at = readAt
        }
      }
    }
    // Clear unread count for this conversation
    const conv = conversations.value.find((c) => c.id === conversationId)
    if (conv) {
      const prevUnread = conv.unread_count
      conv.unread_count = 0
      unreadCount.value = Math.max(0, unreadCount.value - prevUnread)
    }
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
    fetchUnreadCount,
    fetchConversations,
    fetchMessages,
    addFromWebSocket,
    updateFromWebSocket,
    recallFromWebSocket,
    readReceiptFromWebSocket,
    setActiveConversation,
    resetState,
  }
})

import api from '@/composables/api'
import { assertShape } from '@/utils/apiValidation'
import type { ConversationListResponse, MessageListResponse, DMMessage } from '@/types/dm'

export async function listConversations(params: {
  page?: number
  page_size?: number
}): Promise<ConversationListResponse> {
  const { data } = await api.get('/dm/conversations', { params })
  return assertShape<ConversationListResponse>(
    data,
    ['conversations', 'total'],
    'listConversations',
  )
}

export async function listMessages(
  conversationId: string,
  params: { page?: number; page_size?: number },
): Promise<MessageListResponse> {
  const { data } = await api.get(`/dm/conversations/${conversationId}/messages`, { params })
  return assertShape<MessageListResponse>(data, ['messages', 'total'], 'listMessages')
}

export async function sendMessage(
  userId: string,
  content?: string,
  file?: File,
): Promise<DMMessage> {
  const formData = new FormData()
  if (content) formData.append('content', content)
  if (file) formData.append('file', file)
  const { data } = await api.post(`/dm/conversations/${userId}/messages`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return assertShape<DMMessage>(data, ['id', 'sender', 'content'], 'sendMessage')
}

export async function editMessage(messageId: string, content: string): Promise<DMMessage> {
  const { data } = await api.put(`/dm/messages/${messageId}`, { content })
  return data as DMMessage
}

export async function recallMessage(messageId: string): Promise<DMMessage> {
  const { data } = await api.delete(`/dm/messages/${messageId}`)
  return data as DMMessage
}

export async function markConversationRead(conversationId: string): Promise<void> {
  await api.put(`/dm/conversations/${conversationId}/read`)
}

export async function getUnreadCount(): Promise<{ unread_count: number }> {
  const { data } = await api.get('/dm/unread-count')
  return data as { unread_count: number }
}

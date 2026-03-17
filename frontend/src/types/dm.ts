export interface DMSender {
  id: string
  display_name: string
  avatar_url: string | null
}

export interface DMMessage {
  id: string
  conversation_id: string
  sender: DMSender
  content: string | null
  attachment_url: string | null
  attachment_name: string | null
  attachment_size: number | null
  attachment_expires_at: string | null
  is_recalled: boolean
  is_edited: boolean
  read_at: string | null
  created_at: string
  updated_at: string
}

export interface Conversation {
  id: string
  other_user: DMSender
  last_message: DMMessage | null
  unread_count: number
  updated_at: string
}

export interface ConversationListResponse {
  conversations: Conversation[]
  total: number
}

export interface MessageListResponse {
  messages: DMMessage[]
  total: number
}

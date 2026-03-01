export interface TriggerUser {
  id: string
  display_name: string
  avatar_url: string | null
}

export interface Notification {
  id: string
  action_type: string
  entity_type: string | null
  entity_id: string | null
  message: string
  is_read: boolean
  created_at: string
  trigger_user: TriggerUser | null
}

import type { Author } from './user'

export interface Event {
  id: string
  title: string
  content: string
  author: Author
  sig_id: string | null
  sig_name: string | null
  visibility: string[]
  allow_comments: boolean
  comment_count: number
  reaction_counts: Record<string, number> | null
  user_reactions: string[] | null
  version: number
  created_at: string
  updated_at: string
}

export interface EventListResponse {
  events: Event[]
  total: number
  page: number
  total_pages: number
}

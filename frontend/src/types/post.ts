import type { Author } from './user'

export interface Post {
  id: string
  title: string
  content: string
  author: Author
  category_id: string | null
  category_name: string | null
  sig_id: string | null
  sig_name: string | null
  keywords: string[] | null
  allow_comments: boolean
  version: number
  comment_count: number
  is_pinned: boolean
  view_count: number
  reaction_counts: Record<string, number> | null
  user_reactions: string[] | null
  last_comment_at: string | null
  type: 'post' | 'question'
  citation_count: number
  answer_count: number
  best_answer_id: string | null
  created_at: string
  updated_at: string
}

export interface PostListResponse {
  posts: Post[]
  // Page-based (legacy):
  total?: number
  total_pages?: number
  page?: number
  // Cursor-based:
  next_cursor?: string | null
  has_more?: boolean
}

export interface HistoryItem {
  id: string
  version: number
  title: string
  content: string
  edited_at: string
}

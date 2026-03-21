import type { Author } from './user'

export interface Comment {
  id: string
  post_id: string
  content: string
  author: Author
  parent_id: string | null
  mentions: string[] | null
  reactions: Record<string, string[]> | null
  vote_score: number
  is_best_answer: boolean
  created_at: string
  updated_at: string
}

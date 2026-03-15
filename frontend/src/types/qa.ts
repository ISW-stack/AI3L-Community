import type { Post } from './post'

export interface Question extends Post {
  type: 'question'
  best_answer_id: string | null
  answer_count: number
}

export interface CommentVote {
  comment_id: string
  user_vote: -1 | 0 | 1
}

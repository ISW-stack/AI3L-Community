import type { Post } from './post'

export interface QAQuestion extends Post {
  type: 'question'
  best_answer_id: string | null
  answer_count: number
}

export interface CommentVote {
  comment_id: string
  vote: -1 | 0 | 1
}

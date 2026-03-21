import api from '@/composables/api'

export function markBestAnswer(postId: string, commentId: string) {
  return api.post(`/qa/${postId}/best-answer`, { comment_id: commentId })
}

export function unmarkBestAnswer(postId: string) {
  return api.delete(`/qa/${postId}/best-answer`)
}

export function voteOnAnswer(commentId: string, vote: -1 | 0 | 1) {
  return api.post(`/qa/comments/${commentId}/vote`, { vote })
}

export function getUserVotes(postId: string) {
  return api.get<{ comment_id: string; vote: -1 | 1 }[]>(`/qa/${postId}/votes`)
}

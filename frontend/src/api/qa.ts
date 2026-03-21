import api from '@/composables/api'

export async function markBestAnswer(postId: string, commentId: string) {
  const { data } = await api.post(`/qa/${postId}/best-answer`, { comment_id: commentId })
  return data
}

export async function unmarkBestAnswer(postId: string) {
  const { data } = await api.delete(`/qa/${postId}/best-answer`)
  return data
}

export async function voteOnAnswer(commentId: string, vote: -1 | 0 | 1) {
  const { data } = await api.post(`/qa/comments/${commentId}/vote`, { vote })
  return data
}

export async function getUserVotes(postId: string) {
  const { data } = await api.get<{ comment_id: string; vote: -1 | 1 }[]>(`/qa/${postId}/votes`)
  return data
}

import api from '@/composables/api'
import type { Comment } from '@/types'

export interface CommentsListResponse {
  comments: Comment[]
  total: number
}

export async function listComments(postId: string, params?: { page?: number; page_size?: number }) {
  const { data } = await api.get(`/posts/${postId}/comments`, { params })
  return data as CommentsListResponse
}

export async function createComment(
  postId: string,
  payload: {
    content: string
    parent_id?: string
    mentions?: string[]
  },
) {
  const { data } = await api.post(`/posts/${postId}/comments`, payload)
  return data as Comment
}

export async function deleteComment(postId: string, commentId: string) {
  await api.delete(`/posts/${postId}/comments/${commentId}`)
}

export async function updateComment(
  postId: string,
  commentId: string,
  payload: { content: string },
) {
  const { data } = await api.put(`/posts/${postId}/comments/${commentId}`, payload)
  return data as Comment
}

export async function toggleReaction(postId: string, commentId: string, reaction: string) {
  const { data } = await api.post(`/posts/${postId}/comments/${commentId}/reactions`, { reaction })
  return data as Comment
}

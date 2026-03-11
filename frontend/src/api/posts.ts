import api from '@/composables/api'
import type { Post, PostListResponse, HistoryItem } from '@/types'

export async function listPosts(params: {
  cursor?: string
  page?: number
  page_size?: number
  category_id?: string
  author_id?: string
  sort?: string
}) {
  const { data } = await api.get('/posts', { params })
  return data as PostListResponse
}

export async function getPost(postId: string) {
  const { data } = await api.get(`/posts/${postId}`)
  return data as Post
}

export async function createPost(payload: {
  title: string
  content: string
  category_id?: string
  sig_id?: string
  keywords?: string[]
  allow_comments?: boolean
}) {
  const { data } = await api.post('/posts', payload)
  return data as Post
}

export async function updatePost(
  postId: string,
  payload: {
    title?: string
    content?: string
    category_id?: string
    keywords?: string[]
    allow_comments?: boolean
    version: number
  },
) {
  const { data } = await api.put(`/posts/${postId}`, payload)
  return data as Post
}

export async function deletePost(postId: string) {
  await api.delete(`/posts/${postId}`)
}

export async function searchPosts(payload: {
  keyword?: string
  category_id?: string
  keywords?: string[]
  date_from?: string
  date_to?: string
  logic?: string
  sort?: string
  cursor?: string
  page_size?: number
}) {
  const { data } = await api.post('/posts/search', payload)
  return data as PostListResponse
}

export async function getPostHistory(postId: string) {
  const { data } = await api.get(`/posts/${postId}/history`)
  return data.history as HistoryItem[]
}

export async function getTrendingPosts() {
  const { data } = await api.get('/posts/trending')
  return data as Post[]
}

export async function togglePinPost(postId: string, isPinned: boolean) {
  const { data } = await api.patch(`/posts/${postId}/pin`, { is_pinned: isPinned })
  return data as { is_pinned: boolean }
}

export async function getPublicStats() {
  const { data } = await api.get('/public/stats')
  return data as { member_count: number; post_count: number; sig_count: number }
}

export async function togglePostReaction(postId: string, reactionType: string) {
  const { data } = await api.post(`/posts/${postId}/reactions`, { reaction: reactionType })
  return data as Post
}

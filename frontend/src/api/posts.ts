import api from '@/composables/api'
import type { Post, PostListResponse, HistoryItem } from '@/types'

export async function listPosts(params: {
  page?: number
  page_size?: number
  category_id?: string
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
  page?: number
  page_size?: number
}) {
  const { data } = await api.post('/posts/search', payload)
  return data as PostListResponse
}

export async function getPostHistory(postId: string) {
  const { data } = await api.get(`/posts/${postId}/history`)
  return data.history as HistoryItem[]
}

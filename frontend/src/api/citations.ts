import api from '@/composables/api'
import type { CitationListResponse } from '@/types/citation'

export function getCitedBy(postId: string) {
  return api.get<CitationListResponse>(`/posts/${postId}/citations`)
}

export function getCiting(postId: string) {
  return api.get<CitationListResponse>(`/posts/${postId}/citing`)
}

export function searchForCitation(query: string, limit = 10) {
  return api.post('/posts/search-for-citation', { query, limit })
}

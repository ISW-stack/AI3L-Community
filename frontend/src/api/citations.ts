import api from '@/composables/api'
import type { CitationListResponse } from '@/types/citation'

export async function getCitedBy(postId: string): Promise<CitationListResponse> {
  const { data } = await api.get<CitationListResponse>(`/citations/posts/${postId}/cited-by`)
  return data
}

export async function getCiting(postId: string): Promise<CitationListResponse> {
  const { data } = await api.get<CitationListResponse>(`/citations/posts/${postId}/citing`)
  return data
}

export interface CitationSearchResult {
  id: string
  title: string
  author_name: string
}

export async function searchForCitation(
  query: string,
  limit = 10,
): Promise<CitationSearchResult[]> {
  const { data } = await api.post<CitationSearchResult[]>('/citations/posts/search-for-citation', {
    query,
    limit,
  })
  return data
}

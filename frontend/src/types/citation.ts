export interface CitationEntry {
  id: string
  post_id: string
  post_title: string
  author_name: string
  is_self_citation: boolean
  created_at: string
}

export interface CitationListResponse {
  citations: CitationEntry[]
  total: number
}

import type { Author } from './user'

export interface Post {
  id: string
  title: string
  content: string
  author: Author
  category_id: string | null
  category_name: string | null
  keywords: string[] | null
  allow_comments: boolean
  version: number
  comment_count: number
  created_at: string
  updated_at: string
}

export interface PostListResponse {
  posts: Post[]
  total: number
  total_pages: number
}

export interface HistoryItem {
  id: string
  version: number
  title: string
  content: string
  edited_at: string
}

export interface Album {
  id: string
  title: string
  description: string | null
  cover_photo_url: string | null
  created_by: string | null
  created_by_name: string | null
  is_archived: boolean
  photo_count: number
  member_count: number
  created_at: string
  updated_at: string
}

export interface AlbumListResponse {
  albums: Album[]
  total: number
}

export interface AlbumMember {
  id: string
  album_id: string
  user_id: string
  display_name: string
  username: string
  avatar_url: string | null
  role: 'ADMIN' | 'MEMBER'
  status: 'PENDING' | 'ACCEPTED' | 'REJECTED'
  joined_at: string
}

export interface AlbumMemberListResponse {
  members: AlbumMember[]
  total: number
}

export interface AlbumPhoto {
  id: string
  album_id: string
  uploaded_by: string | null
  uploaded_by_name: string | null
  storage_url: string | null
  thumbnail_url: string | null
  original_filename: string | null
  file_size_bytes: number
  content_type: string | null
  description: string | null
  width: number | null
  height: number | null
  is_zip: boolean
  created_at: string
  updated_at: string
}

export interface AlbumPhotoListResponse {
  photos: AlbumPhoto[]
  total: number
}

export interface AlbumComment {
  id: string
  album_id: string
  photo_id: string | null
  user_id: string
  display_name: string
  avatar_url: string | null
  parent_id: string | null
  content: string
  is_deleted: boolean
  created_at: string
  updated_at: string
}

export interface AlbumCommentListResponse {
  comments: AlbumComment[]
  total: number
}

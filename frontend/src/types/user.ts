export interface Author {
  id: string
  username: string
  display_name: string
  avatar_url: string | null
}

export interface UserProfile {
  id: string
  username: string
  display_name: string
  role: string
  bio: string | null
  affiliation: string | null
  orcid: string | null
  avatar_url: string | null
  preferred_language: string
  is_banned: boolean
  ban_reason: string | null
  created_at: string
  preferences?: Record<string, unknown> | null
}

export interface PublicUser {
  id: string
  username: string
  display_name: string
  role: string
  avatar_url: string | null
  bio: string | null
  affiliation: string | null
  orcid: string | null
  profile_view_count_unique: number
  profile_view_count_total: number
  created_at: string
  can_dm: boolean
}

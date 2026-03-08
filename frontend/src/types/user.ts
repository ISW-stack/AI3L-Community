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
  created_at: string
}

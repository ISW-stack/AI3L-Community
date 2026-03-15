export interface CoAuthor {
  id: string
  post_id: string
  user_id: string | null
  display_name: string
  affiliation: string | null
  orcid: string | null
  is_external: boolean
  status: 'PENDING' | 'ACCEPTED' | 'REJECTED'
  avatar_url: string | null
  invited_at: string
  responded_at: string | null
}

export interface CoAuthorListResponse {
  co_authors: CoAuthor[]
}

export interface CoAuthorInvitation {
  id: string
  post_id: string
  post_title: string
  invited_by_name: string
  invited_at: string
  status: string
}

export interface CoAuthorInvitationListResponse {
  invitations: CoAuthorInvitation[]
  total: number
}

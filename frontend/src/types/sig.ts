export interface Sig {
  id: string
  name: string
  description: string | null
  created_by: string
  creator_display_name: string | null
  member_count: number
  created_at: string
}

export interface SigMember {
  id: string
  sig_id: string
  user_id: string
  role: string
  display_name: string
  username: string
  avatar_url: string | null
  created_at: string
}

export interface SigForm {
  id: string
  sig_id: string
  title: string
  description: string | null
  deadline: string | null
  max_respondents: number | null
  response_count: number
  is_active: boolean
  created_by_name: string
  created_at: string
  user_is_sig_admin: boolean
}

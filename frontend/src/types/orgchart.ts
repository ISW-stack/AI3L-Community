export interface OrgChartMember {
  user_id: string
  display_name: string
  username: string
  avatar_url: string | null
  role: string
  org_chart_bio: string | null
  member_override: OrgChartOverride | null
}

export interface OrgChartOverride {
  entity_type: string
  entity_id: string
  custom_title: string | null
  custom_description: string | null
  display_order: number
  is_visible: boolean
}

export interface OrgChartSig {
  id: string
  name: string
  description: string | null
  org_chart_description: string | null
  member_count: number
  members: OrgChartMember[]
  override: OrgChartOverride | null
}

export interface OrgChartCategory {
  id: string
  name: string
  description: string | null
  creator_id: string | null
  creator_display_name: string | null
  creator_avatar_url: string | null
  override: OrgChartOverride | null
}

export interface OrgChartResponse {
  sigs: OrgChartSig[]
  categories: OrgChartCategory[]
}

export interface MemberCard {
  id: string
  username: string
  display_name: string
  avatar_url: string | null
  role: string
  affiliation: string | null
  bio: string | null
}

export interface MembersListResponse {
  members: MemberCard[]
  total: number
}

// ── Member Classifications ──

export interface ClassifiedMember {
  user_id: string
  username: string
  display_name: string
  avatar_url: string | null
}

export interface MemberCategory {
  key: string
  label: string
  count: number
  members: ClassifiedMember[]
}

export interface ClassifiedMembersResponse {
  categories: MemberCategory[]
}

export interface CategoryDetailResponse {
  key: string
  label: string
  members: ClassifiedMember[]
}

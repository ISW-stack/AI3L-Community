export interface RecommendationReason {
  type: 'common_sig' | 'mutual_friends' | 'same_affiliation' | 'activity_recency'
  count?: number
  affiliation?: string
}

export interface FriendRecommendation {
  id: string
  user_id: string
  display_name: string
  username: string
  avatar_url: string | null
  affiliation: string | null
  score: number
  reasons: RecommendationReason[]
  created_at: string
}

export interface RecommendationsListResponse {
  recommendations: FriendRecommendation[]
}

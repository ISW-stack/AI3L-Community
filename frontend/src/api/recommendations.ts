import api from '@/composables/api'
import type { RecommendationsListResponse } from '@/types/recommendation'

export function getRecommendations() {
  return api.get<RecommendationsListResponse>('/recommendations/friends')
}

export function dismissRecommendation(userId: string) {
  return api.post('/recommendations/friends/dismiss', { user_id: userId })
}

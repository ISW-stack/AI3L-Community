import api from '@/composables/api'
import type { RecommendationsListResponse } from '@/types/recommendation'

export async function getRecommendations(): Promise<RecommendationsListResponse> {
  const { data } = await api.get<RecommendationsListResponse>('/recommendations/friends')
  return data
}

export async function dismissRecommendation(userId: string): Promise<void> {
  await api.post('/recommendations/friends/dismiss', { user_id: userId })
}

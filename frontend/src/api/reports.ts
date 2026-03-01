import api from '@/composables/api'

export async function createReport(postId: string, reason: string) {
  await api.post(`/posts/${postId}/report`, { reason })
}

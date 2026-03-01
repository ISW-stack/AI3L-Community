import api from '@/composables/api'

export interface TaskStatus {
  status: string
  download_url?: string
}

export async function getTaskStatus(taskId: string) {
  const { data } = await api.get(`/tasks/${taskId}/status`)
  return data as TaskStatus
}

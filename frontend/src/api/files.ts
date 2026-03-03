import api from '@/composables/api'

export interface UploadResponse {
  url: string
  key?: string
  scan_task_id?: string | null
}

export interface TaskStatusResponse {
  task_id: string
  status: string
  result?: { status?: string; malicious?: number; suspicious?: number } | null
}

export async function getTaskStatus(taskId: string) {
  const { data } = await api.get(`/tasks/${taskId}/status`)
  return data as TaskStatusResponse
}

export async function uploadEditorFile(file: File) {
  const formData = new FormData()
  formData.append('file', file)
  const { data } = await api.post('/files/upload/editor', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data as UploadResponse
}

export async function getPresignedUrl(key: string) {
  const { data } = await api.get('/files/presigned-url', { params: { key } })
  return data as { url: string }
}

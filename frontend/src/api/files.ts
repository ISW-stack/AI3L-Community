import api from '@/composables/api'

export interface UploadResponse {
  url: string
  key?: string
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

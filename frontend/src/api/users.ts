import api from '@/composables/api'
import type { UserProfile } from '@/types'

export async function getProfile() {
  const { data } = await api.get('/users/me')
  return data as UserProfile
}

export async function updateProfile(payload: {
  display_name?: string
  bio?: string
  affiliation?: string
  orcid?: string
}) {
  const { data } = await api.put('/users/me', payload)
  return data as UserProfile
}

export async function uploadAvatar(file: File) {
  const formData = new FormData()
  formData.append('file', file)
  const { data } = await api.put('/users/me/avatar', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data as UserProfile
}

export async function changePassword(payload: { current_password: string; new_password: string }) {
  await api.put('/users/me/password', payload)
}

export async function acceptConsent() {
  await api.post('/users/me/consent')
}

export async function deleteAccount() {
  await api.delete('/users/me')
}

import api from '@/composables/api'
import type { UserProfile, PublicUser } from '@/types'

export async function getProfile() {
  const { data } = await api.get('/users/me')
  return data as UserProfile
}

export async function updateProfile(payload: {
  display_name?: string
  bio?: string | null
  affiliation?: string | null
  orcid?: string | null
  preferred_language?: string
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

export async function getPublicProfile(userId: string) {
  const { data } = await api.get(`/users/${userId}`)
  return data as PublicUser
}

export async function applyForMembership(payload: {
  username: string
  password: string
  display_name: string
  description: string
}) {
  const { data } = await api.post('/users/apply-member', payload)
  return data as { message: string }
}

export interface MyApplication {
  id: string
  status: 'PENDING' | 'APPROVED' | 'REJECTED'
  created_at: string
  reviewed_at: string | null
}

export async function getMyApplication(): Promise<{ application: MyApplication | null }> {
  const { data } = await api.get('/users/my-application')
  return data as { application: MyApplication | null }
}

export interface UserPreferences {
  theme: string
  notify_mentions: boolean
  notify_replies: boolean
  notify_sig_posts: boolean
  dm_friends_only: boolean
}

export async function getPreferences(): Promise<UserPreferences> {
  const { data } = await api.get('/users/me/preferences')
  return data as UserPreferences
}

export async function updatePreferences(
  payload: Partial<UserPreferences>,
): Promise<UserPreferences> {
  const { data } = await api.patch('/users/me/preferences', payload)
  return data as UserPreferences
}

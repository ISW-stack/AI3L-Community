import api from '@/composables/api'
import type { Sig, SigMember, SigForm, Post } from '@/types'

export interface SigsListResponse {
  sigs: Sig[]
  total: number
}

export interface SigPostsResponse {
  posts: Post[]
  total: number
  total_pages?: number
}

export interface SigMembersResponse {
  members: SigMember[]
  total: number
}

export interface SigFormsResponse {
  forms: SigForm[]
  total: number
}

export async function listSigs(params?: { page?: number; page_size?: number }) {
  let query: Record<string, number> | undefined
  if (params?.page != null && params?.page_size != null) {
    query = {
      offset: (params.page - 1) * params.page_size,
      limit: params.page_size,
    }
  }
  const { data } = await api.get('/sigs', { params: query })
  return data as SigsListResponse
}

export async function getSig(sigId: string) {
  const { data } = await api.get(`/sigs/${sigId}`)
  return data as Sig
}

export async function updateSig(
  sigId: string,
  payload: {
    name: string
    description: string | null
  },
) {
  const { data } = await api.put(`/sigs/${sigId}`, payload)
  return data as Sig
}

export async function deleteSig(sigId: string) {
  await api.delete(`/sigs/${sigId}`)
}

export async function getSigPosts(sigId: string, params?: { page?: number; page_size?: number }) {
  const { data } = await api.get(`/sigs/${sigId}/posts`, { params })
  return data as SigPostsResponse
}

export async function getSigMembers(sigId: string, params?: { page?: number; page_size?: number }) {
  let query: Record<string, number> | undefined
  if (params?.page != null && params?.page_size != null) {
    query = {
      offset: (params.page - 1) * params.page_size,
      limit: params.page_size,
    }
  }
  const { data } = await api.get(`/sigs/${sigId}/members`, { params: query })
  return data as SigMembersResponse
}

export async function getSigForms(sigId: string, params?: { page?: number; page_size?: number }) {
  const { data } = await api.get(`/sigs/${sigId}/forms`, { params })
  return data as SigFormsResponse
}

export async function getMySigRole(sigId: string): Promise<string | null> {
  try {
    const { data } = await api.get(`/sigs/${sigId}/members/me`)
    return (data as { role: string }).role
  } catch {
    return null
  }
}

export async function leaveSig(sigId: string) {
  await api.delete(`/sigs/${sigId}/members/me`)
}

export async function removeMember(sigId: string, userId: string) {
  await api.delete(`/sigs/${sigId}/members/${userId}`)
}

export async function assignSubAdmin(sigId: string, userId: string) {
  const { data } = await api.post(`/sigs/${sigId}/sub-admin`, { user_id: userId })
  return data as SigMember
}

export async function demoteSubAdmin(sigId: string, userId: string) {
  const { data } = await api.post(`/sigs/${sigId}/sub-admin/demote`, { user_id: userId })
  return data as SigMember
}

export async function createSig(payload: { name: string; description: string | null }) {
  const { data } = await api.post('/sigs', payload)
  return data as Sig
}

export async function listMySigs() {
  const { data } = await api.get('/sigs/my')
  return (data as { sigs: Sig[] }).sigs
}

export async function joinSig(sigId: string) {
  const { data } = await api.post(`/sigs/${sigId}/members/me`)
  return data as SigMember
}

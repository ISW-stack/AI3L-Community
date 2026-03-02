import api from '@/composables/api'
import type { Sig, SigMember, SigForm, Post } from '@/types'

export interface SigsListResponse {
  sigs: Sig[]
  total: number
}

export interface SigPostsResponse {
  posts: Post[]
  total: number
}

export interface SigMembersResponse {
  members: SigMember[]
  total: number
}

export interface SigFormsResponse {
  forms: SigForm[]
  total: number
}

export async function listSigs() {
  const { data } = await api.get('/sigs')
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

export async function getSigPosts(sigId: string) {
  const { data } = await api.get(`/sigs/${sigId}/posts`)
  return data as SigPostsResponse
}

export async function getSigMembers(sigId: string) {
  const { data } = await api.get(`/sigs/${sigId}/members`)
  return data as SigMembersResponse
}

export async function getSigForms(sigId: string) {
  const { data } = await api.get(`/sigs/${sigId}/forms`)
  return data as SigFormsResponse
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

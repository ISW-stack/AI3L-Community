import api from '@/composables/api'
import type { CoAuthorListResponse, CoAuthorInvitationListResponse } from '@/types/coauthor'

export async function listCoAuthors(postId: string): Promise<CoAuthorListResponse> {
  const { data } = await api.get<CoAuthorListResponse>(`/posts/${postId}/co-authors`)
  return data
}

export async function inviteCoAuthor(
  postId: string,
  inviteData: { user_id: string; display_name?: string },
): Promise<void> {
  await api.post(`/posts/${postId}/co-authors/invite`, inviteData)
}

export async function addExternalCoAuthor(
  postId: string,
  authorData: { display_name: string; affiliation?: string; orcid?: string },
): Promise<void> {
  await api.post(`/posts/${postId}/co-authors/external`, authorData)
}

export async function removeCoAuthor(postId: string, coAuthorId: string): Promise<void> {
  await api.delete(`/posts/${postId}/co-authors/${coAuthorId}`)
}

export async function listMyInvitations(
  page = 1,
  pageSize = 20,
): Promise<CoAuthorInvitationListResponse> {
  const { data } = await api.get<CoAuthorInvitationListResponse>(
    '/users/me/co-author-invitations',
    {
      params: { page, page_size: pageSize },
    },
  )
  return data
}

export async function acceptInvitation(invitationId: string): Promise<void> {
  await api.put(`/users/me/co-author-invitations/${invitationId}/accept`)
}

export async function rejectInvitation(invitationId: string): Promise<void> {
  await api.put(`/users/me/co-author-invitations/${invitationId}/reject`)
}

export async function searchUsers(query: string, limit = 5): Promise<unknown> {
  const { data } = await api.get('/users/search', { params: { q: query, limit } })
  return data
}

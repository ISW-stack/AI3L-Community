import api from '@/composables/api'
import type { CoAuthorListResponse, CoAuthorInvitationListResponse } from '@/types/coauthor'

export function listCoAuthors(postId: string) {
  return api.get<CoAuthorListResponse>(`/posts/${postId}/co-authors`)
}

export function inviteCoAuthor(postId: string, data: { user_id: string; display_name?: string }) {
  return api.post(`/posts/${postId}/co-authors/invite`, data)
}

export function addExternalCoAuthor(
  postId: string,
  data: { display_name: string; affiliation?: string; orcid?: string },
) {
  return api.post(`/posts/${postId}/co-authors/external`, data)
}

export function removeCoAuthor(postId: string, coAuthorId: string) {
  return api.delete(`/posts/${postId}/co-authors/${coAuthorId}`)
}

export function listMyInvitations(page = 1, pageSize = 20) {
  return api.get<CoAuthorInvitationListResponse>('/users/me/co-author-invitations', {
    params: { page, page_size: pageSize },
  })
}

export function acceptInvitation(invitationId: string) {
  return api.put(`/users/me/co-author-invitations/${invitationId}/accept`)
}

export function rejectInvitation(invitationId: string) {
  return api.put(`/users/me/co-author-invitations/${invitationId}/reject`)
}

export function searchUsers(query: string, limit = 5) {
  return api.get('/users/search', { params: { q: query, limit } })
}

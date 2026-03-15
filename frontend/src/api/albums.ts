import api from '@/composables/api'
import type {
  AlbumListResponse,
  Album,
  AlbumMemberListResponse,
  AlbumPhotoListResponse,
  AlbumPhoto,
  AlbumCommentListResponse,
} from '@/types/album'

export function listAlbums(page = 1, pageSize = 20) {
  return api.get<AlbumListResponse>('/albums', { params: { page, page_size: pageSize } })
}

export function getAlbum(id: string) {
  return api.get<Album>(`/albums/${id}`)
}

export function createAlbum(data: { title: string; description?: string }) {
  return api.post<Album>('/albums', data)
}

export function updateAlbum(id: string, data: { title?: string; description?: string }) {
  return api.put<Album>(`/albums/${id}`, data)
}

export function deleteAlbum(id: string) {
  return api.delete(`/albums/${id}`)
}

export function listAlbumMembers(albumId: string, page = 1, pageSize = 20) {
  return api.get<AlbumMemberListResponse>(`/albums/${albumId}/members`, {
    params: { page, page_size: pageSize },
  })
}

export function addAlbumMember(albumId: string, userId: string) {
  return api.post(`/albums/${albumId}/members`, { user_id: userId })
}

export function joinAlbum(albumId: string) {
  return api.post(`/albums/${albumId}/join`)
}

export function approveAlbumMember(albumId: string, memberId: string) {
  return api.put(`/albums/${albumId}/members/${memberId}/approve`)
}

export function removeAlbumMember(albumId: string, userId: string) {
  return api.delete(`/albums/${albumId}/members/${userId}`)
}

export function listAlbumPhotos(albumId: string, page = 1, pageSize = 20) {
  return api.get<AlbumPhotoListResponse>(`/albums/${albumId}/photos`, {
    params: { page, page_size: pageSize },
  })
}

export function getAlbumPhoto(albumId: string, photoId: string) {
  return api.get<AlbumPhoto>(`/albums/${albumId}/photos/${photoId}`)
}

export function uploadAlbumPhoto(albumId: string, formData: FormData) {
  return api.post<AlbumPhoto>(`/albums/${albumId}/photos`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

export function uploadAlbumFile(albumId: string, formData: FormData) {
  return api.post(`/albums/${albumId}/files`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

export function updateAlbumPhoto(albumId: string, photoId: string, data: { description?: string }) {
  return api.put(`/albums/${albumId}/photos/${photoId}`, data)
}

export function deleteAlbumPhoto(albumId: string, photoId: string) {
  return api.delete(`/albums/${albumId}/photos/${photoId}`)
}

export function listAlbumComments(albumId: string, page = 1, pageSize = 20) {
  return api.get<AlbumCommentListResponse>(`/albums/${albumId}/comments`, {
    params: { page, page_size: pageSize },
  })
}

export function createAlbumComment(
  albumId: string,
  data: { content: string; photo_id?: string; parent_id?: string },
) {
  return api.post(`/albums/${albumId}/comments`, data)
}

export function deleteAlbumComment(albumId: string, commentId: string) {
  return api.delete(`/albums/${albumId}/comments/${commentId}`)
}

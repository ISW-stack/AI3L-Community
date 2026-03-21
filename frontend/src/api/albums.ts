import api from '@/composables/api'
import type {
  AlbumListResponse,
  Album,
  AlbumMemberListResponse,
  AlbumPhotoListResponse,
  AlbumPhoto,
  AlbumCommentListResponse,
} from '@/types/album'

export async function listAlbums(page = 1, pageSize = 20): Promise<AlbumListResponse> {
  const { data } = await api.get<AlbumListResponse>('/albums', {
    params: { page, page_size: pageSize },
  })
  return data
}

export async function getAlbum(id: string): Promise<Album> {
  const { data } = await api.get<Album>(`/albums/${id}`)
  return data
}

export async function createAlbum(albumData: {
  title: string
  description?: string
}): Promise<Album> {
  const { data } = await api.post<Album>('/albums', albumData)
  return data
}

export async function updateAlbum(
  id: string,
  albumData: { title?: string; description?: string },
): Promise<Album> {
  const { data } = await api.put<Album>(`/albums/${id}`, albumData)
  return data
}

export async function deleteAlbum(id: string): Promise<void> {
  await api.delete(`/albums/${id}`)
}

export async function listAlbumMembers(
  albumId: string,
  page = 1,
  pageSize = 20,
): Promise<AlbumMemberListResponse> {
  const { data } = await api.get<AlbumMemberListResponse>(`/albums/${albumId}/members`, {
    params: { page, page_size: pageSize },
  })
  return data
}

export async function addAlbumMember(albumId: string, userId: string): Promise<void> {
  await api.post(`/albums/${albumId}/members`, { user_id: userId })
}

export async function joinAlbum(albumId: string): Promise<void> {
  await api.post(`/albums/${albumId}/join`)
}

export async function approveAlbumMember(albumId: string, memberId: string): Promise<void> {
  await api.put(`/albums/${albumId}/members/${memberId}/approve`)
}

export async function removeAlbumMember(albumId: string, userId: string): Promise<void> {
  await api.delete(`/albums/${albumId}/members/${userId}`)
}

export async function listAlbumPhotos(
  albumId: string,
  page = 1,
  pageSize = 20,
): Promise<AlbumPhotoListResponse> {
  const { data } = await api.get<AlbumPhotoListResponse>(`/albums/${albumId}/photos`, {
    params: { page, page_size: pageSize },
  })
  return data
}

export async function getAlbumPhoto(albumId: string, photoId: string): Promise<AlbumPhoto> {
  const { data } = await api.get<AlbumPhoto>(`/albums/${albumId}/photos/${photoId}`)
  return data
}

export async function uploadAlbumPhoto(albumId: string, formData: FormData): Promise<AlbumPhoto> {
  const { data } = await api.post<AlbumPhoto>(`/albums/${albumId}/photos`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}

export async function uploadAlbumFile(albumId: string, formData: FormData): Promise<AlbumPhoto> {
  const { data } = await api.post<AlbumPhoto>(`/albums/${albumId}/files`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}

export async function updateAlbumPhoto(
  albumId: string,
  photoId: string,
  albumData: { description?: string },
): Promise<void> {
  await api.put(`/albums/${albumId}/photos/${photoId}`, albumData)
}

export async function deleteAlbumPhoto(albumId: string, photoId: string): Promise<void> {
  await api.delete(`/albums/${albumId}/photos/${photoId}`)
}

export async function setAlbumCoverFromPhoto(albumId: string, photoId: string): Promise<Album> {
  const { data } = await api.put<Album>(`/albums/${albumId}/cover`, { photo_id: photoId })
  return data
}

export async function uploadAlbumCover(albumId: string, formData: FormData): Promise<Album> {
  const { data } = await api.post<Album>(`/albums/${albumId}/cover`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}

export async function listAlbumComments(
  albumId: string,
  page = 1,
  pageSize = 20,
): Promise<AlbumCommentListResponse> {
  const { data } = await api.get<AlbumCommentListResponse>(`/albums/${albumId}/comments`, {
    params: { page, page_size: pageSize },
  })
  return data
}

export async function createAlbumComment(
  albumId: string,
  commentData: { content: string; photo_id?: string; parent_id?: string },
): Promise<void> {
  await api.post(`/albums/${albumId}/comments`, commentData)
}

export async function deleteAlbumComment(albumId: string, commentId: string): Promise<void> {
  await api.delete(`/albums/${albumId}/comments/${commentId}`)
}

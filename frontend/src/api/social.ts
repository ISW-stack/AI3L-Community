import api from '@/composables/api'
import type {
  FriendListResponse,
  FriendRequestListResponse,
  FollowUserListResponse,
  BlockListResponse,
  RelationshipStatus,
} from '@/types/social'

// Friends
export async function sendFriendRequest(userId: string): Promise<void> {
  await api.post('/social/friends/request', { user_id: userId })
}

export async function acceptFriendRequest(friendshipId: string): Promise<void> {
  await api.put(`/social/friends/${friendshipId}/accept`)
}

export async function rejectFriendRequest(friendshipId: string): Promise<void> {
  await api.put(`/social/friends/${friendshipId}/reject`)
}

export async function unfriend(userId: string): Promise<void> {
  await api.delete(`/social/friends/${userId}`)
}

export async function listFriends(page = 1, pageSize = 20): Promise<FriendListResponse> {
  const { data } = await api.get<FriendListResponse>('/social/friends', {
    params: { page, page_size: pageSize },
  })
  return data
}

export async function listFriendRequests(
  page = 1,
  pageSize = 20,
): Promise<FriendRequestListResponse> {
  const { data } = await api.get<FriendRequestListResponse>('/social/friends/requests', {
    params: { page, page_size: pageSize },
  })
  return data
}

// Follow
export async function followUser(userId: string): Promise<void> {
  await api.post(`/social/follow/${userId}`)
}

export async function unfollowUser(userId: string): Promise<void> {
  await api.delete(`/social/follow/${userId}`)
}

export async function listFollowers(page = 1, pageSize = 20): Promise<FollowUserListResponse> {
  const { data } = await api.get<FollowUserListResponse>('/social/followers', {
    params: { page, page_size: pageSize },
  })
  return data
}

export async function listFollowing(page = 1, pageSize = 20): Promise<FollowUserListResponse> {
  const { data } = await api.get<FollowUserListResponse>('/social/following', {
    params: { page, page_size: pageSize },
  })
  return data
}

// Block
export async function blockUser(userId: string): Promise<void> {
  await api.post(`/social/block/${userId}`)
}

export async function unblockUser(userId: string): Promise<void> {
  await api.delete(`/social/block/${userId}`)
}

export async function listBlocks(page = 1, pageSize = 20): Promise<BlockListResponse> {
  const { data } = await api.get<BlockListResponse>('/social/blocks', {
    params: { page, page_size: pageSize },
  })
  return data
}

// Relationship status
export async function getRelationshipStatus(userId: string): Promise<RelationshipStatus> {
  const { data } = await api.get<RelationshipStatus>(`/social/status/${userId}`)
  return data
}

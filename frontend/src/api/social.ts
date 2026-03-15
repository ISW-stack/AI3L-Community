import api from '@/composables/api'
import type {
  FriendListResponse,
  FriendRequestListResponse,
  FollowUserListResponse,
  BlockListResponse,
  RelationshipStatus,
} from '@/types/social'

// Friends
export function sendFriendRequest(userId: string) {
  return api.post('/social/friends/request', { user_id: userId })
}

export function acceptFriendRequest(friendshipId: string) {
  return api.put(`/social/friends/${friendshipId}/accept`)
}

export function rejectFriendRequest(friendshipId: string) {
  return api.put(`/social/friends/${friendshipId}/reject`)
}

export function unfriend(userId: string) {
  return api.delete(`/social/friends/${userId}`)
}

export function listFriends(page = 1, pageSize = 20) {
  return api.get<FriendListResponse>('/social/friends', {
    params: { page, page_size: pageSize },
  })
}

export function listFriendRequests(page = 1, pageSize = 20) {
  return api.get<FriendRequestListResponse>('/social/friends/requests', {
    params: { page, page_size: pageSize },
  })
}

// Follow
export function followUser(userId: string) {
  return api.post(`/social/follow/${userId}`)
}

export function unfollowUser(userId: string) {
  return api.delete(`/social/follow/${userId}`)
}

export function listFollowers(page = 1, pageSize = 20) {
  return api.get<FollowUserListResponse>('/social/followers', {
    params: { page, page_size: pageSize },
  })
}

export function listFollowing(page = 1, pageSize = 20) {
  return api.get<FollowUserListResponse>('/social/following', {
    params: { page, page_size: pageSize },
  })
}

// Block
export function blockUser(userId: string) {
  return api.post(`/social/block/${userId}`)
}

export function unblockUser(userId: string) {
  return api.delete(`/social/block/${userId}`)
}

export function listBlocks(page = 1, pageSize = 20) {
  return api.get<BlockListResponse>('/social/blocks', {
    params: { page, page_size: pageSize },
  })
}

// Relationship status
export function getRelationshipStatus(userId: string) {
  return api.get<RelationshipStatus>(`/social/status/${userId}`)
}

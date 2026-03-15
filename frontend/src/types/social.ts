export interface Friendship {
  id: string
  user_id: string
  display_name: string
  username: string
  avatar_url: string | null
  affiliation: string | null
  created_at: string
}

export interface FriendListResponse {
  friends: Friendship[]
  total: number
}

export interface FriendRequest {
  id: string
  requester_id: string
  requester_name: string
  requester_username: string
  requester_avatar_url: string | null
  addressee_id: string
  addressee_name: string
  addressee_username: string
  addressee_avatar_url: string | null
  status: string
  created_at: string
}

export interface FriendRequestListResponse {
  requests: FriendRequest[]
  total: number
}

export interface FollowUser {
  id: string
  user_id: string
  display_name: string
  username: string
  avatar_url: string | null
  created_at: string
}

export interface FollowUserListResponse {
  users: FollowUser[]
  total: number
}

export interface BlockedUser {
  id: string
  blocked_id: string
  display_name: string
  username: string
  avatar_url: string | null
  created_at: string
}

export interface BlockListResponse {
  blocks: BlockedUser[]
  total: number
}

export interface RelationshipStatus {
  is_friend: boolean
  is_following: boolean
  is_followed_by: boolean
  is_blocked: boolean
  pending_request: 'sent' | 'received' | null
  friendship_id: string | null
}

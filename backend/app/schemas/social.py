from __future__ import annotations

from pydantic import BaseModel, Field

_UUID_PATTERN = r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"


class FriendRequestCreateRequest(BaseModel):
    user_id: str = Field(..., pattern=_UUID_PATTERN)


class FriendshipResponse(BaseModel):
    id: str
    user_id: str
    display_name: str
    username: str
    avatar_url: str | None = None
    affiliation: str | None = None
    created_at: str


class FriendListResponse(BaseModel):
    friends: list[FriendshipResponse]
    total: int


class FriendRequestResponse(BaseModel):
    id: str
    requester_id: str
    requester_name: str
    requester_username: str
    requester_avatar_url: str | None = None
    addressee_id: str
    addressee_name: str
    addressee_username: str
    addressee_avatar_url: str | None = None
    status: str
    created_at: str


class FriendRequestListResponse(BaseModel):
    requests: list[FriendRequestResponse]
    total: int


class FollowUserResponse(BaseModel):
    id: str
    user_id: str
    display_name: str
    username: str
    avatar_url: str | None = None
    created_at: str


class FollowUserListResponse(BaseModel):
    users: list[FollowUserResponse]
    total: int


class BlockResponse(BaseModel):
    id: str
    blocked_id: str
    display_name: str
    username: str
    avatar_url: str | None = None
    created_at: str


class BlockListResponse(BaseModel):
    blocks: list[BlockResponse]
    total: int


class RelationshipStatusResponse(BaseModel):
    is_friend: bool = False
    is_following: bool = False
    is_followed_by: bool = False
    is_blocked: bool = False
    pending_request: str | None = None  # null | "sent" | "received"
    friendship_id: str | None = None

"""Converters for social feature responses."""

from app.converters.user_converter import async_resolve_avatar_url
from app.schemas.social import (
    BlockResponse,
    FollowUserResponse,
    FriendRequestResponse,
    FriendshipResponse,
    RelationshipStatusResponse,
)


async def to_friendship_response(row: dict, current_user_id: str) -> FriendshipResponse:
    """Convert a friends-list row (with JOINed user info) to FriendshipResponse."""
    return FriendshipResponse(
        id=str(row["id"]),
        user_id=str(row["friend_id"]),
        display_name=row["display_name"],
        username=row["username"],
        avatar_url=await async_resolve_avatar_url(row.get("avatar_url")),
        affiliation=row.get("affiliation"),
        created_at=(
            row["created_at"].isoformat()
            if hasattr(row["created_at"], "isoformat")
            else str(row["created_at"])
        ),
    )


async def to_friend_request_response(row: dict) -> FriendRequestResponse:
    """Convert a pending-request row (with both users JOINed) to FriendRequestResponse."""
    return FriendRequestResponse(
        id=str(row["id"]),
        requester_id=str(row["requester_id"]),
        requester_name=row["requester_display_name"],
        requester_username=row["requester_username"],
        requester_avatar_url=await async_resolve_avatar_url(row.get("requester_avatar_url")),
        addressee_id=str(row["addressee_id"]),
        addressee_name=row["addressee_display_name"],
        addressee_username=row["addressee_username"],
        addressee_avatar_url=await async_resolve_avatar_url(row.get("addressee_avatar_url")),
        status=row["status"],
        created_at=(
            row["created_at"].isoformat()
            if hasattr(row["created_at"], "isoformat")
            else str(row["created_at"])
        ),
    )


async def to_follow_user_response(row: dict) -> FollowUserResponse:
    """Convert a followers/following list row to FollowUserResponse."""
    return FollowUserResponse(
        id=str(row["id"]),
        user_id=str(row["user_id"]),
        display_name=row["display_name"],
        username=row["username"],
        avatar_url=await async_resolve_avatar_url(row.get("avatar_url")),
        created_at=(
            row["created_at"].isoformat()
            if hasattr(row["created_at"], "isoformat")
            else str(row["created_at"])
        ),
    )


async def to_block_response(row: dict) -> BlockResponse:
    """Convert a block-list row to BlockResponse."""
    return BlockResponse(
        id=str(row["id"]),
        blocked_id=str(row["blocked_id"]),
        display_name=row["display_name"],
        username=row["username"],
        avatar_url=await async_resolve_avatar_url(row.get("avatar_url")),
        created_at=(
            row["created_at"].isoformat()
            if hasattr(row["created_at"], "isoformat")
            else str(row["created_at"])
        ),
    )


def to_relationship_status_response(data: dict) -> RelationshipStatusResponse:
    """Convert relationship status dict to RelationshipStatusResponse."""
    return RelationshipStatusResponse(
        is_friend=data["is_friend"],
        is_following=data["is_following"],
        is_followed_by=data["is_followed_by"],
        is_blocked=data["is_blocked"],
        pending_request=data.get("pending_request"),
        friendship_id=data.get("friendship_id"),
    )

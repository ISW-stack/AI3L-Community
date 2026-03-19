"""Social endpoints — friendships, follows, blocks, relationship status."""

import uuid

from fastapi import APIRouter, Depends, Query

from app.converters.social_converter import (
    to_block_response,
    to_follow_user_response,
    to_friend_request_response,
    to_friendship_response,
    to_relationship_status_response,
)
from app.core.constants import (
    DEFAULT_PAGE_SIZE_FOLLOWERS,
    DEFAULT_PAGE_SIZE_FRIENDS,
    MAX_PAGE_NUMBER,
    MAX_PAGE_SIZE,
    RATE_LIMIT_FRIEND_REQUEST,
    RATE_LIMIT_SOCIAL,
)
from app.core.database import get_pool
from app.core.deps import require_role
from app.core.errors import AppError, ErrorCode
from app.core.rate_limit import check_rate_limit
from app.core.redis import get_redis
from app.schemas.auth import MessageResponse
from app.schemas.social import (
    BlockListResponse,
    FollowUserListResponse,
    FriendListResponse,
    FriendRequestCreateRequest,
    FriendRequestListResponse,
    RelationshipStatusResponse,
)
from app.services.social import (
    accept_friend_request,
    block_user,
    follow_user,
    get_relationship_status,
    list_blocks,
    list_followers,
    list_following,
    list_friend_requests,
    list_friends,
    reject_friend_request,
    send_friend_request,
    unblock_user,
    unfollow_user,
    unfriend,
)

router = APIRouter(prefix="/social", tags=["social"])


# ── Friends ─────────────────────────────────────────────────────────
# Route ordering: literal paths before parameterized paths


@router.post("/friends/request", response_model=MessageResponse)
async def send_friend_request_endpoint(
    req: FriendRequestCreateRequest,
    current_user: dict = Depends(require_role("MEMBER", "ADMIN", "SUPER_ADMIN")),
) -> MessageResponse:
    """Send a friend request to another user."""
    user_id = current_user["sub"]
    allowed = await check_rate_limit(
        f"social:friend_req:{user_id}",
        RATE_LIMIT_FRIEND_REQUEST[0],
        RATE_LIMIT_FRIEND_REQUEST[1],
    )
    if not allowed:
        raise AppError(ErrorCode.SYS_429, 429, "Too many friend requests. Try again later.")

    pool = get_pool()
    await send_friend_request(pool, uuid.UUID(user_id), uuid.UUID(req.user_id))
    return MessageResponse(message="Friend request sent.")


@router.get("/friends/requests", response_model=FriendRequestListResponse)
async def get_friend_requests(
    page: int = Query(1, ge=1, le=MAX_PAGE_NUMBER),
    page_size: int = Query(DEFAULT_PAGE_SIZE_FRIENDS, ge=1, le=MAX_PAGE_SIZE),
    current_user: dict = Depends(require_role("MEMBER", "ADMIN", "SUPER_ADMIN")),
) -> FriendRequestListResponse:
    """List pending friend requests (incoming and outgoing)."""
    pool = get_pool()
    rows, total = await list_friend_requests(pool, uuid.UUID(current_user["sub"]), page, page_size)
    return FriendRequestListResponse(
        requests=[to_friend_request_response(r) for r in rows],
        total=total,
    )


@router.put("/friends/{friendship_id}/accept", response_model=MessageResponse)
async def accept_friend_request_endpoint(
    friendship_id: uuid.UUID,
    current_user: dict = Depends(require_role("MEMBER", "ADMIN", "SUPER_ADMIN")),
) -> MessageResponse:
    """Accept a pending friend request."""
    user_id = current_user["sub"]
    allowed = await check_rate_limit(
        f"social:accept:{user_id}",
        RATE_LIMIT_SOCIAL[0],
        RATE_LIMIT_SOCIAL[1],
    )
    if not allowed:
        raise AppError(ErrorCode.SYS_429, 429, "Too many requests. Try again later.")

    pool = get_pool()
    await accept_friend_request(pool, friendship_id, uuid.UUID(user_id))
    return MessageResponse(message="Friend request accepted.")


@router.put("/friends/{friendship_id}/reject", response_model=MessageResponse)
async def reject_friend_request_endpoint(
    friendship_id: uuid.UUID,
    current_user: dict = Depends(require_role("MEMBER", "ADMIN", "SUPER_ADMIN")),
) -> MessageResponse:
    """Reject a pending friend request."""
    user_id = current_user["sub"]
    allowed = await check_rate_limit(
        f"social:reject:{user_id}",
        RATE_LIMIT_SOCIAL[0],
        RATE_LIMIT_SOCIAL[1],
    )
    if not allowed:
        raise AppError(ErrorCode.SYS_429, 429, "Too many requests. Try again later.")

    pool = get_pool()
    await reject_friend_request(pool, friendship_id, uuid.UUID(user_id))
    return MessageResponse(message="Friend request rejected.")


@router.delete("/friends/{user_id}", response_model=MessageResponse)
async def unfriend_endpoint(
    user_id: uuid.UUID,
    current_user: dict = Depends(require_role("MEMBER", "ADMIN", "SUPER_ADMIN")),
) -> MessageResponse:
    """Remove a friend."""
    pool = get_pool()
    await unfriend(pool, uuid.UUID(current_user["sub"]), user_id)
    return MessageResponse(message="Friend removed.")


@router.get("/friends", response_model=FriendListResponse)
async def get_friends(
    page: int = Query(1, ge=1, le=MAX_PAGE_NUMBER),
    page_size: int = Query(DEFAULT_PAGE_SIZE_FRIENDS, ge=1, le=MAX_PAGE_SIZE),
    current_user: dict = Depends(require_role("MEMBER", "ADMIN", "SUPER_ADMIN")),
) -> FriendListResponse:
    """List accepted friends (paginated)."""
    pool = get_pool()
    rows, total = await list_friends(pool, uuid.UUID(current_user["sub"]), page, page_size)
    return FriendListResponse(
        friends=[to_friendship_response(r, current_user["sub"]) for r in rows],
        total=total,
    )


# ── Follow ──────────────────────────────────────────────────────────


@router.post("/follow/{user_id}", response_model=MessageResponse)
async def follow_user_endpoint(
    user_id: uuid.UUID,
    current_user: dict = Depends(require_role("MEMBER", "ADMIN", "SUPER_ADMIN")),
) -> MessageResponse:
    """Follow a user."""
    cur_uid = current_user["sub"]
    allowed = await check_rate_limit(
        f"social:follow:{cur_uid}",
        RATE_LIMIT_SOCIAL[0],
        RATE_LIMIT_SOCIAL[1],
    )
    if not allowed:
        raise AppError(ErrorCode.SYS_429, 429, "Too many requests. Try again later.")

    pool = get_pool()
    await follow_user(pool, uuid.UUID(cur_uid), user_id)
    return MessageResponse(message="Followed.")


@router.delete("/follow/{user_id}", response_model=MessageResponse)
async def unfollow_user_endpoint(
    user_id: uuid.UUID,
    current_user: dict = Depends(require_role("MEMBER", "ADMIN", "SUPER_ADMIN")),
) -> MessageResponse:
    """Unfollow a user."""
    pool = get_pool()
    await unfollow_user(pool, uuid.UUID(current_user["sub"]), user_id)
    return MessageResponse(message="Unfollowed.")


@router.get("/followers", response_model=FollowUserListResponse)
async def get_followers(
    page: int = Query(1, ge=1, le=MAX_PAGE_NUMBER),
    page_size: int = Query(DEFAULT_PAGE_SIZE_FOLLOWERS, ge=1, le=MAX_PAGE_SIZE),
    current_user: dict = Depends(require_role("MEMBER", "ADMIN", "SUPER_ADMIN")),
) -> FollowUserListResponse:
    """List users who follow the current user."""
    pool = get_pool()
    redis = get_redis()
    rows, total = await list_followers(
        pool, uuid.UUID(current_user["sub"]), page, page_size, redis=redis
    )
    return FollowUserListResponse(
        users=[to_follow_user_response(r) for r in rows],
        total=total,
    )


@router.get("/following", response_model=FollowUserListResponse)
async def get_following(
    page: int = Query(1, ge=1, le=MAX_PAGE_NUMBER),
    page_size: int = Query(DEFAULT_PAGE_SIZE_FOLLOWERS, ge=1, le=MAX_PAGE_SIZE),
    current_user: dict = Depends(require_role("MEMBER", "ADMIN", "SUPER_ADMIN")),
) -> FollowUserListResponse:
    """List users the current user is following."""
    pool = get_pool()
    redis = get_redis()
    rows, total = await list_following(
        pool, uuid.UUID(current_user["sub"]), page, page_size, redis=redis
    )
    return FollowUserListResponse(
        users=[to_follow_user_response(r) for r in rows],
        total=total,
    )


# ── Block ───────────────────────────────────────────────────────────


@router.post("/block/{user_id}", response_model=MessageResponse)
async def block_user_endpoint(
    user_id: uuid.UUID,
    current_user: dict = Depends(require_role("MEMBER", "ADMIN", "SUPER_ADMIN")),
) -> MessageResponse:
    """Block a user. Cascades: removes friendship and follows."""
    cur_uid = current_user["sub"]
    allowed = await check_rate_limit(
        f"social:block:{cur_uid}",
        RATE_LIMIT_SOCIAL[0],
        RATE_LIMIT_SOCIAL[1],
    )
    if not allowed:
        raise AppError(ErrorCode.SYS_429, 429, "Too many requests. Try again later.")

    pool = get_pool()
    redis = get_redis()
    await block_user(pool, redis, uuid.UUID(cur_uid), user_id)
    return MessageResponse(message="User blocked.")


@router.delete("/block/{user_id}", response_model=MessageResponse)
async def unblock_user_endpoint(
    user_id: uuid.UUID,
    current_user: dict = Depends(require_role("MEMBER", "ADMIN", "SUPER_ADMIN")),
) -> MessageResponse:
    """Unblock a user."""
    pool = get_pool()
    redis = get_redis()
    await unblock_user(pool, redis, uuid.UUID(current_user["sub"]), user_id)
    return MessageResponse(message="User unblocked.")


@router.get("/blocks", response_model=BlockListResponse)
async def get_blocks(
    page: int = Query(1, ge=1, le=MAX_PAGE_NUMBER),
    page_size: int = Query(DEFAULT_PAGE_SIZE_FRIENDS, ge=1, le=MAX_PAGE_SIZE),
    current_user: dict = Depends(require_role("MEMBER", "ADMIN", "SUPER_ADMIN")),
) -> BlockListResponse:
    """List blocked users."""
    pool = get_pool()
    rows, total = await list_blocks(pool, uuid.UUID(current_user["sub"]), page, page_size)
    return BlockListResponse(
        blocks=[to_block_response(r) for r in rows],
        total=total,
    )


# ── Relationship Status ─────────────────────────────────────────────


@router.get("/status/{user_id}", response_model=RelationshipStatusResponse)
async def get_status(
    user_id: uuid.UUID,
    current_user: dict = Depends(require_role("MEMBER", "ADMIN", "SUPER_ADMIN")),
) -> RelationshipStatusResponse:
    """Get relationship status with another user."""
    pool = get_pool()
    data = await get_relationship_status(pool, uuid.UUID(current_user["sub"]), user_id)
    return to_relationship_status_response(data)

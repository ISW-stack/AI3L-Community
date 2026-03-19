"""Social service — friendships, follows, blocks business logic."""

import uuid
from typing import Any

import asyncpg
from loguru import logger

from app.core.blacklist import get_blocked_user_ids, update_block_cache
from app.core.constants import MAX_BLOCKS_PER_USER
from app.core.errors import AppError, ErrorCode
from app.core.event_bus import emit
from app.repositories import social_repo

# ── Friend Request Flow ─────────────────────────────────────────────


async def send_friend_request(
    pool: asyncpg.Pool, requester_id: uuid.UUID, addressee_id: uuid.UUID
) -> dict:
    """Send a friend request. Auto-accepts if reverse pending request exists."""
    if requester_id == addressee_id:
        raise AppError(ErrorCode.SYS_422, 400, "Cannot send a friend request to yourself.")

    async with pool.acquire() as conn:
        # Wrap all checks + insert in transaction to prevent TOCTOU races
        # where a block could be inserted between the check and the friend request
        async with conn.transaction():
            if await social_repo.is_blocked(conn, requester_id, addressee_id):
                raise AppError(ErrorCode.SOCIAL_003, 403, "Cannot interact with this user.")

            existing = await social_repo.find_friendship_between(
                conn, requester_id, addressee_id, for_update=True
            )
            if existing:
                if existing["status"] == "ACCEPTED":
                    raise AppError(ErrorCode.SOCIAL_001, 409, "Already friends.")
                # Reverse pending request → auto-accept
                if existing["status"] == "PENDING" and existing["addressee_id"] == requester_id:
                    friendship = await social_repo.accept_friendship(conn, existing["id"])
                    # Auto-follow both directions
                    await _ensure_follow(conn, requester_id, addressee_id)
                    await _ensure_follow(conn, addressee_id, requester_id)

                    # Notify both users: the original requester and the current requester
                    await emit(
                        "friend.accepted",
                        user_id=str(addressee_id),
                        friend_id=str(requester_id),
                        friendship_id=str(existing["id"]),
                    )
                    await emit(
                        "friend.accepted",
                        user_id=str(requester_id),
                        friend_id=str(addressee_id),
                        friendship_id=str(existing["id"]),
                    )
                    return friendship  # type: ignore[return-value]

                # Duplicate pending request
                raise AppError(ErrorCode.SOCIAL_001, 409, "Friend request already sent.")

            # Insert new PENDING friendship
            friendship_id = uuid.uuid4()
            friendship = await social_repo.insert_friendship(
                conn, friendship_id, requester_id, addressee_id
            )

    await emit(
        "friend.request",
        user_id=str(requester_id),
        target_id=str(addressee_id),
        friendship_id=str(friendship_id),
    )
    return friendship


async def accept_friend_request(
    pool: asyncpg.Pool, friendship_id: uuid.UUID, user_id: uuid.UUID
) -> dict:
    """Accept a friend request. Only the addressee can accept.

    Uses SELECT ... FOR UPDATE inside a transaction to prevent TOCTOU races
    where two concurrent accepts could both pass validation.
    """
    async with pool.acquire() as conn:
        async with conn.transaction():
            # Lock the friendship row to prevent concurrent modification
            friendship = await social_repo.find_friendship_by_id_for_update(conn, friendship_id)
            if not friendship:
                raise AppError(ErrorCode.SYS_404, 404, "Friend request not found.")
            if friendship["status"] != "PENDING":
                raise AppError(ErrorCode.SYS_422, 400, "Request is not pending.")
            if friendship["addressee_id"] != user_id:
                raise AppError(ErrorCode.SYS_403, 403, "Only the addressee can accept.")

            updated = await social_repo.accept_friendship(conn, friendship_id)
            if not updated:
                raise AppError(
                    ErrorCode.SYS_404,
                    404,
                    "Friend request not found or already processed.",
                )
            # Auto-follow both directions
            requester_id = friendship["requester_id"]
            await _ensure_follow(conn, user_id, requester_id)
            await _ensure_follow(conn, requester_id, user_id)

    await emit(
        "friend.accepted",
        user_id=str(friendship["requester_id"]),
        friend_id=str(user_id),
        friendship_id=str(friendship_id),
    )
    return updated


async def reject_friend_request(
    pool: asyncpg.Pool, friendship_id: uuid.UUID, user_id: uuid.UUID
) -> None:
    """Reject (delete) a friend request. Only the addressee can reject.

    Uses SELECT ... FOR UPDATE inside a transaction to prevent TOCTOU races
    where concurrent reject + accept could both pass validation.
    """
    async with pool.acquire() as conn:
        async with conn.transaction():
            # Lock the friendship row to prevent concurrent modification
            friendship = await social_repo.find_friendship_by_id_for_update(conn, friendship_id)
            if not friendship:
                raise AppError(ErrorCode.SYS_404, 404, "Friend request not found.")
            if friendship["status"] != "PENDING":
                raise AppError(ErrorCode.SYS_422, 400, "Request is not pending.")
            if friendship["addressee_id"] != user_id:
                raise AppError(ErrorCode.SYS_403, 403, "Only the addressee can reject.")
            await social_repo.reject_friendship(conn, friendship_id)


async def unfriend(pool: asyncpg.Pool, user_id: uuid.UUID, target_user_id: uuid.UUID) -> None:
    """Remove a friendship. Does NOT auto-unfollow."""
    async with pool.acquire() as conn:
        deleted = await social_repo.delete_friendship_between(conn, user_id, target_user_id)
        if not deleted:
            raise AppError(ErrorCode.SYS_404, 404, "Friendship not found.")


async def list_friends(
    pool: asyncpg.Pool, user_id: uuid.UUID, page: int = 1, page_size: int = 20
) -> tuple[list[dict], int]:
    async with pool.acquire() as conn:
        return await social_repo.find_friends(conn, user_id, page, page_size)


async def list_friend_requests(
    pool: asyncpg.Pool, user_id: uuid.UUID, page: int = 1, page_size: int = 20
) -> tuple[list[dict], int]:
    async with pool.acquire() as conn:
        return await social_repo.find_pending_requests(conn, user_id, page, page_size)


# ── Follow ──────────────────────────────────────────────────────────


async def follow_user(pool: asyncpg.Pool, follower_id: uuid.UUID, following_id: uuid.UUID) -> dict:
    """Follow a user.

    Uses a transaction to make block check + duplicate check + insert atomic,
    preventing TOCTOU races that could bypass the block restriction or create
    duplicate follows.
    """
    if follower_id == following_id:
        raise AppError(ErrorCode.SYS_422, 400, "Cannot follow yourself.")

    async with pool.acquire() as conn:
        async with conn.transaction():
            if await social_repo.is_blocked(conn, follower_id, following_id):
                raise AppError(ErrorCode.SOCIAL_003, 403, "Cannot interact with this user.")
            if await social_repo.is_following(conn, follower_id, following_id):
                raise AppError(ErrorCode.SYS_409, 409, "Already following this user.")

            follow_id = uuid.uuid4()
            return await social_repo.insert_follow(conn, follow_id, follower_id, following_id)


async def unfollow_user(
    pool: asyncpg.Pool, follower_id: uuid.UUID, following_id: uuid.UUID
) -> None:
    """Unfollow a user."""
    async with pool.acquire() as conn:
        deleted = await social_repo.delete_follow(conn, follower_id, following_id)
        if not deleted:
            raise AppError(ErrorCode.SYS_404, 404, "Not following this user.")


async def list_followers(
    pool: asyncpg.Pool,
    user_id: uuid.UUID,
    page: int = 1,
    page_size: int = 20,
    redis: Any = None,
) -> tuple[list[dict], int]:
    exclude: list[uuid.UUID] | None = None
    if redis:
        try:
            blocked_ids = await get_blocked_user_ids(redis, str(user_id), pool=pool)
            if blocked_ids:
                exclude = [uuid.UUID(uid) for uid in blocked_ids]
        except Exception:
            pass
    async with pool.acquire() as conn:
        return await social_repo.find_followers(
            conn, user_id, page, page_size, exclude_user_ids=exclude
        )


async def list_following(
    pool: asyncpg.Pool,
    user_id: uuid.UUID,
    page: int = 1,
    page_size: int = 20,
    redis: Any = None,
) -> tuple[list[dict], int]:
    exclude: list[uuid.UUID] | None = None
    if redis:
        try:
            blocked_ids = await get_blocked_user_ids(redis, str(user_id), pool=pool)
            if blocked_ids:
                exclude = [uuid.UUID(uid) for uid in blocked_ids]
        except Exception:
            pass
    async with pool.acquire() as conn:
        return await social_repo.find_following(
            conn, user_id, page, page_size, exclude_user_ids=exclude
        )


# ── Block (cascade logic) ──────────────────────────────────────────


async def block_user(
    pool: asyncpg.Pool, redis: Any, blocker_id: uuid.UUID, blocked_id: uuid.UUID
) -> dict:
    """Block a user. Cascades: removes friendship + follows between them."""
    if blocker_id == blocked_id:
        raise AppError(ErrorCode.SYS_422, 400, "Cannot block yourself.")

    async with pool.acquire() as conn:
        # Single transaction: count check + delete friendship + follows + insert block
        # Count check must be inside the transaction to prevent concurrent blocks
        # from both passing the limit check.
        async with conn.transaction():
            block_count = await social_repo.count_blocks(conn, blocker_id)
            if block_count >= MAX_BLOCKS_PER_USER:
                raise AppError(
                    ErrorCode.SOCIAL_002,
                    400,
                    f"Block limit reached (max {MAX_BLOCKS_PER_USER}).",
                )

            await social_repo.delete_friendship_between(conn, blocker_id, blocked_id)
            await social_repo.delete_follows_between(conn, blocker_id, blocked_id)
            block_id = uuid.uuid4()
            block = await social_repo.insert_block(conn, block_id, blocker_id, blocked_id)

    # Note: There is a brief timing window between the DB write and Redis cache
    # update where the block list may be stale. This is acceptable as it only
    # affects blacklist filtering for a few milliseconds.
    await update_block_cache(redis, str(blocker_id), str(blocked_id), added=True)

    logger.info(
        "User blocked",
        extra={"blocker_id": str(blocker_id), "blocked_id": str(blocked_id)},
    )
    return block


async def unblock_user(
    pool: asyncpg.Pool, redis: Any, blocker_id: uuid.UUID, blocked_id: uuid.UUID
) -> None:
    """Unblock a user."""
    async with pool.acquire() as conn:
        deleted = await social_repo.delete_block(conn, blocker_id, blocked_id)
        if not deleted:
            raise AppError(ErrorCode.SYS_404, 404, "Block not found.")

    # Update Redis AFTER successful DB commit
    await update_block_cache(redis, str(blocker_id), str(blocked_id), added=False)

    logger.info(
        "User unblocked",
        extra={"blocker_id": str(blocker_id), "blocked_id": str(blocked_id)},
    )


async def list_blocks(
    pool: asyncpg.Pool, user_id: uuid.UUID, page: int = 1, page_size: int = 20
) -> tuple[list[dict], int]:
    async with pool.acquire() as conn:
        return await social_repo.find_blocks(conn, user_id, page, page_size)


# ── Relationship Status ─────────────────────────────────────────────


async def get_relationship_status(
    pool: asyncpg.Pool, user_id: uuid.UUID, target_id: uuid.UUID
) -> dict:
    async with pool.acquire() as conn:
        return await social_repo.get_relationship_status(conn, user_id, target_id)


# ── Internal helpers ─────────────────────────────────────────────────


async def _ensure_follow(
    conn: asyncpg.Connection, follower_id: uuid.UUID, following_id: uuid.UUID
) -> None:
    """Insert follow if it doesn't already exist. Used for auto-follow on accept."""
    already = await social_repo.is_following(conn, follower_id, following_id)
    if not already:
        await social_repo.insert_follow(conn, uuid.uuid4(), follower_id, following_id)

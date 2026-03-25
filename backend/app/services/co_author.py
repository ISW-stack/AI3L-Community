"""Service layer for post co-author management."""

import re
import uuid
from datetime import datetime, timezone

from loguru import logger

from app.converters.co_author_converter import (
    to_co_author_invitation_response,
    to_co_author_response,
)
from app.core.blacklist import get_blocked_user_ids
from app.core.constants import MAX_CO_AUTHORS_PER_POST
from app.core.database import get_pool
from app.core.errors import AppError, ErrorCode, ForbiddenError, NotFoundError
from app.core.event_bus import emit
from app.core.redis import get_redis
from app.repositories import co_author_repo

_ORCID_PATTERN = re.compile(r"^\d{4}-\d{4}-\d{4}-\d{3}[\dX]$")


async def invite_co_author(
    post_id: uuid.UUID,
    user_id: str,
    target_user_id: str,
    display_name: str | None = None,
) -> dict:
    """Invite a platform user as co-author.

    Raises AppError on permission, limit, or duplicate issues.
    """
    # U5: Self-invite check first (cheap, no DB/Redis needed)
    if target_user_id == user_id:
        raise AppError(ErrorCode.SYS_422, 400, "Cannot invite yourself as a co-author.")

    # Block check: cannot invite a blocked user as co-author
    try:
        redis = get_redis()
        blocked_ids = await get_blocked_user_ids(redis, user_id)
        if target_user_id in blocked_ids:
            raise AppError(
                ErrorCode.SOCIAL_003,
                403,
                "Cannot invite this user as co-author.",
            )
        # H5: Bilateral block check — target may have blocked the inviter
        target_blocked_ids = await get_blocked_user_ids(redis, target_user_id)
        if user_id in target_blocked_ids:
            raise AppError(
                ErrorCode.SOCIAL_003,
                403,
                "Cannot invite this user as co-author.",
            )
    except AppError:
        raise
    except Exception:
        pass  # Redis failure → allow invitation

    pool = get_pool()
    async with pool.acquire() as conn:
        # Verify post exists and user is the owner
        post = await conn.fetchrow(
            "SELECT id, user_id, title FROM posts WHERE id = $1 AND is_deleted = false",
            post_id,
        )
        if not post:
            raise NotFoundError("Post", str(post_id))
        if str(post["user_id"]) != user_id:
            raise ForbiddenError("Only the post owner can invite co-authors.")

        # H3: Wrap count check + insert in transaction with advisory lock
        async with conn.transaction():
            # Advisory lock keyed on post_id to serialise concurrent invites
            await conn.execute(
                "SELECT pg_advisory_xact_lock(hashtext($1::text))",
                str(post_id),
            )

            # Check co-author count
            count = await co_author_repo.count_co_authors(conn, post_id)
            if count >= MAX_CO_AUTHORS_PER_POST:
                raise AppError(
                    ErrorCode.COAUTHOR_001,
                    400,
                    f"Maximum co-authors ({MAX_CO_AUTHORS_PER_POST}) reached.",
                )

            # Check target user exists
            target_uuid = uuid.UUID(target_user_id)
            target = await conn.fetchrow(
                "SELECT id, display_name, avatar_url FROM users "
                "WHERE id = $1 AND is_deleted = false",
                target_uuid,
            )
            if not target:
                raise NotFoundError("User", target_user_id)

            # B3: Check for existing co-author entry — allow re-invite after rejection
            existing = await co_author_repo.find_existing_by_user(conn, post_id, target_uuid)
            if existing:
                if existing["status"] == "REJECTED":
                    await co_author_repo.delete_co_author(conn, existing["id"])
                else:
                    raise AppError(
                        ErrorCode.COAUTHOR_002,
                        409,
                        "This user already has a co-author entry for this post.",
                    )

            co_author_id = uuid.uuid4()
            name = display_name or target["display_name"]
            row = await co_author_repo.insert_co_author(
                conn,
                co_author_id,
                post_id,
                target_uuid,
                name,
                None,
                None,
                False,
                "PENDING",
                uuid.UUID(user_id),
            )
            # Enrich row with user JOIN data for converter (avatar + display name)
            row["user_display_name"] = target["display_name"]
            row["user_avatar_url"] = target["avatar_url"]

    # Emit event for notification (best-effort)
    try:
        pool2 = get_pool()
        async with pool2.acquire() as conn2:
            inviter_row = await conn2.fetchrow(
                "SELECT display_name FROM users WHERE id = $1", uuid.UUID(user_id)
            )
        inviter_name = inviter_row["display_name"] if inviter_row else "Someone"
        await emit(
            "co_author.invited",
            post_id=str(post_id),
            target_user_id=target_user_id,
            inviter_id=user_id,
            inviter_name=inviter_name,
            post_title=post["title"],
        )
    except Exception as e:
        logger.warning(
            "Failed to emit co_author.invited event",
            extra={"error": str(e), "post_id": str(post_id)},
        )

    return await to_co_author_response(row)


async def add_external_co_author(
    post_id: uuid.UUID,
    user_id: str,
    display_name: str,
    affiliation: str | None = None,
    orcid: str | None = None,
) -> dict:
    """Add an external (non-platform) co-author."""
    pool = get_pool()
    async with pool.acquire() as conn:
        # Verify post exists and user is the owner
        post = await conn.fetchrow(
            "SELECT id, user_id FROM posts WHERE id = $1 AND is_deleted = false",
            post_id,
        )
        if not post:
            raise NotFoundError("Post", str(post_id))
        if str(post["user_id"]) != user_id:
            raise ForbiddenError("Only the post owner can add co-authors.")

        # ORCID format validation
        if orcid and not _ORCID_PATTERN.match(orcid):
            raise AppError(
                ErrorCode.SYS_422,
                400,
                "Invalid ORCID format. Expected: XXXX-XXXX-XXXX-XXXX.",
            )

        # Wrap count check + insert in transaction with advisory lock
        async with conn.transaction():
            # Advisory lock keyed on post_id to serialise concurrent additions
            await conn.execute(
                "SELECT pg_advisory_xact_lock(hashtext($1::text))",
                str(post_id),
            )

            # Check co-author count
            count = await co_author_repo.count_co_authors(conn, post_id)
            if count >= MAX_CO_AUTHORS_PER_POST:
                raise AppError(
                    ErrorCode.COAUTHOR_001,
                    400,
                    f"Maximum co-authors ({MAX_CO_AUTHORS_PER_POST}) reached.",
                )

            co_author_id = uuid.uuid4()
            try:
                row = await co_author_repo.insert_co_author(
                    conn,
                    co_author_id,
                    post_id,
                    None,
                    display_name,
                    affiliation,
                    orcid,
                    True,
                    "ACCEPTED",
                    uuid.UUID(user_id),
                )
            except Exception as exc:
                if "UniqueViolationError" in type(exc).__name__:
                    raise AppError(
                        ErrorCode.COAUTHOR_002,
                        409,
                        "An external co-author with this name and affiliation already exists.",
                    )
                raise

    return await to_co_author_response(row)


async def respond_to_invitation(
    co_author_id: uuid.UUID,
    user_id: str,
    accept: bool,
) -> bool:
    """Accept or reject a co-author invitation."""
    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            # Lock the row and check status atomically
            invitation = await conn.fetchrow(
                "SELECT * FROM post_co_authors WHERE id = $1 FOR UPDATE",
                co_author_id,
            )
            if not invitation:
                raise NotFoundError("Invitation", str(co_author_id))

            if invitation["status"] != "PENDING":
                raise AppError(ErrorCode.SYS_409, 409, "Invitation has already been responded to.")

            if str(invitation["user_id"]) != user_id:
                raise ForbiddenError("You are not the target of this invitation.")

            new_status = "ACCEPTED" if accept else "REJECTED"
            now = datetime.now(timezone.utc)
            await co_author_repo.update_status(conn, co_author_id, new_status, now)

    # Emit event for notification
    try:
        pool2 = get_pool()
        async with pool2.acquire() as conn2:
            post = await conn2.fetchrow(
                "SELECT user_id, title FROM posts WHERE id = $1",
                invitation["post_id"],
            )
            responder = await conn2.fetchrow(
                "SELECT display_name FROM users WHERE id = $1", uuid.UUID(user_id)
            )
        if post:
            await emit(
                "co_author.responded",
                post_id=str(invitation["post_id"]),
                post_owner_id=str(post["user_id"]),
                responder_id=user_id,
                responder_name=responder["display_name"] if responder else "Someone",
                accepted=accept,
            )
    except Exception as e:
        logger.warning(
            "Failed to emit co_author.responded event",
            extra={"error": str(e), "co_author_id": str(co_author_id)},
        )

    return True


async def remove_co_author(
    post_id: uuid.UUID,
    co_author_id: uuid.UUID,
    user_id: str,
    is_admin: bool = False,
) -> bool:
    """Remove a co-author. Post owner or ADMIN can remove."""
    pool = get_pool()
    async with pool.acquire() as conn:
        # L-02: Wrap permission check + delete in transaction to prevent TOCTOU race
        async with conn.transaction():
            # Verify post exists
            post = await conn.fetchrow(
                "SELECT id, user_id FROM posts WHERE id = $1 AND is_deleted = false",
                post_id,
            )
            if not post:
                raise NotFoundError("Post", str(post_id))

            # Only post owner or admin
            if str(post["user_id"]) != user_id and not is_admin:
                raise ForbiddenError("Only the post owner or an admin can remove co-authors.")

            # Verify co-author belongs to this post
            co_author = await co_author_repo.find_co_author_by_id(conn, co_author_id)
            if not co_author or co_author["post_id"] != post_id:
                raise NotFoundError("Co-author", str(co_author_id))

            return await co_author_repo.delete_co_author(conn, co_author_id)


async def leave_co_authorship(
    post_id: uuid.UUID,
    co_author_id: uuid.UUID,
    user_id: str,
) -> bool:
    """Allow a co-author to remove themselves from a post."""
    pool = get_pool()
    async with pool.acquire() as conn:
        # L-02: Wrap permission check + delete in transaction to prevent TOCTOU race
        async with conn.transaction():
            co_author = await co_author_repo.find_co_author_by_id(conn, co_author_id)
            if not co_author or co_author["post_id"] != post_id:
                raise NotFoundError("Co-author", str(co_author_id))

            # Only the co-author themselves can leave
            co_user_id = co_author.get("user_id")
            if co_user_id is None or str(co_user_id) != user_id:
                raise ForbiddenError("You can only remove yourself as a co-author.")

            return await co_author_repo.delete_co_author(conn, co_author_id)


async def list_co_authors(post_id: uuid.UUID) -> list[dict]:
    """List accepted co-authors for a post."""
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await co_author_repo.find_co_authors_by_post(conn, post_id)
    return [await to_co_author_response(r) for r in rows]


async def list_all_co_authors(
    post_id: uuid.UUID, user_id: str, is_admin: bool = False
) -> list[dict]:
    """List ALL co-authors for a post (all statuses).

    Only the post owner or an admin can see all statuses (including PENDING).
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        # Verify post exists and check ownership
        post = await conn.fetchrow(
            "SELECT id, user_id FROM posts WHERE id = $1 AND is_deleted = false",
            post_id,
        )
        if not post:
            raise NotFoundError("Post", str(post_id))
        if str(post["user_id"]) != user_id and not is_admin:
            raise ForbiddenError("Only the post owner or an admin can view all co-author statuses.")

        rows = await co_author_repo.find_all_co_authors_by_post(conn, post_id)
    return [await to_co_author_response(r) for r in rows]


async def list_co_authored_posts(
    user_id: str, page: int = 1, page_size: int = 20
) -> tuple[list[dict], int]:
    """List posts where the user is an accepted co-author."""
    pool = get_pool()
    async with pool.acquire() as conn:
        rows, total = await co_author_repo.find_co_authored_posts(
            conn, uuid.UUID(user_id), page, page_size
        )
    return rows, total


async def list_pending_invitations(
    user_id: str, page: int = 1, page_size: int = 20
) -> tuple[list[dict], int]:
    """List pending co-author invitations for a user."""
    pool = get_pool()
    async with pool.acquire() as conn:
        rows, total = await co_author_repo.find_pending_invitations(
            conn, uuid.UUID(user_id), page, page_size
        )
    invitations = [await to_co_author_invitation_response(r) for r in rows]
    return invitations, total

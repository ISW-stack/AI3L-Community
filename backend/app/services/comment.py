import asyncio
import uuid

from loguru import logger

from app.converters.comment_converter import async_row_to_comment
from app.core.blacklist import get_blocked_user_ids
from app.core.constants import MAX_COMMENT_LENGTH, MAX_COMMENTS_PER_POST
from app.core.database import get_pool
from app.core.event_bus import emit
from app.core.redis import get_redis
from app.repositories import comment_repo


async def create_comment(
    post_id: uuid.UUID,
    user_id: str,
    content: str,
    parent_id: str | None = None,
    mentions: list[str] | None = None,
) -> dict:
    if len(content) > MAX_COMMENT_LENGTH:
        raise ValueError(f"Comment exceeds maximum length of {MAX_COMMENT_LENGTH} characters.")

    # Block check: cannot comment if blocked by or blocking the post author
    from app.repositories import post_repo

    post_owner_id = await post_repo.find_owner_id(post_id)
    if post_owner_id and post_owner_id != user_id:
        redis = get_redis()
        blocked_ids = await get_blocked_user_ids(redis, user_id)
        if post_owner_id in blocked_ids:
            raise ValueError("Cannot comment on this post.")
        owner_blocked_ids = await get_blocked_user_ids(redis, post_owner_id)
        if user_id in owner_blocked_ids:
            raise ValueError("Cannot comment on this post.")

    pool = get_pool()
    comment_id = uuid.uuid4()
    parent_uuid = uuid.UUID(parent_id) if parent_id else None

    if parent_uuid and parent_uuid == comment_id:
        raise ValueError("A comment cannot reply to itself.")

    async with pool.acquire() as conn:
        async with conn.transaction():
            post = await comment_repo.find_post_for_comment(post_id, conn)
            if not post:
                raise ValueError("Post not found.")
            if not post["allow_comments"]:
                raise ValueError("Comments are disabled for this post.")
            if post["comment_count"] >= MAX_COMMENTS_PER_POST:
                raise ValueError(f"Comment limit ({MAX_COMMENTS_PER_POST}) reached for this post.")

            if parent_uuid:
                parent = await comment_repo.find_parent(parent_uuid, post_id, conn)
                if not parent:
                    raise ValueError("Parent comment not found.")

            row = await comment_repo.insert(
                comment_id, post_id, uuid.UUID(user_id), parent_uuid, content, mentions, conn
            )

            await conn.execute(
                "UPDATE posts SET comment_count = comment_count + 1, last_comment_at = NOW() WHERE id = $1",  # noqa: E501
                post_id,
            )

            # Increment answer_count for top-level comments on Q&A posts
            if not parent_uuid and post.get("type") == "question":
                await conn.execute(
                    "UPDATE posts SET answer_count = answer_count + 1 WHERE id = $1",
                    post_id,
                )

            comment_dict = await async_row_to_comment(row)
            commenter_name = (
                comment_dict["author"]["display_name"] or comment_dict["author"]["username"]
            )

            mention_targets: list[tuple[str, str]] = []
            reply_target: tuple[str, str] | None = None

            if mentions:
                mentioned_rows = await comment_repo.find_mentioned_users(mentions, conn)
                for mrow in mentioned_rows:
                    target_uid = str(mrow["id"])
                    if target_uid != user_id:
                        mention_targets.append((target_uid, str(post_id)))

            if parent_uuid:
                parent_user_id = await comment_repo.find_parent_user_id(parent_uuid, conn)
                if parent_user_id and parent_user_id != user_id:
                    reply_target = (parent_user_id, str(post_id))

    # Fire notifications via event bus (outside the transaction so handlers see committed data)
    try:
        await emit(
            "comment.created",
            user_id=user_id,
            post_owner_id=post_owner_id,
            post_id=str(post_id),
            commenter_name=commenter_name,
            mention_targets=mention_targets,
            reply_target=reply_target,
        )
    except Exception:
        logger.error("Failed to emit comment.created event", exc_info=True)

    logger.info("Comment created", extra={"comment_id": str(comment_id), "post_id": str(post_id)})
    return comment_dict


async def update_comment(
    comment_id: uuid.UUID,
    user_id: str,
    content: str,
    post_id: uuid.UUID | None = None,
) -> dict | None:
    """Update comment content. Only the owner can edit."""
    row = await comment_repo.update(comment_id, uuid.UUID(user_id), content, post_id)
    if not row:
        return None
    logger.info("Comment updated", extra={"comment_id": str(comment_id)})
    return await async_row_to_comment(row)


async def list_comments(
    post_id: uuid.UUID,
    page: int = 1,
    page_size: int = 50,
    viewer_id: str | None = None,
) -> tuple[list[dict], int]:
    exclude: list[uuid.UUID] | None = None
    if viewer_id:
        redis = get_redis()
        blocked_ids = await get_blocked_user_ids(redis, viewer_id)
        if blocked_ids:
            exclude = [uuid.UUID(uid) for uid in blocked_ids]
    offset = (page - 1) * page_size
    rows, total = await comment_repo.find_many(post_id, offset, page_size, exclude_user_ids=exclude)
    comments = list(await asyncio.gather(*[async_row_to_comment(r) for r in rows]))
    return comments, total


async def soft_delete_comment(
    comment_id: uuid.UUID,
    post_id: uuid.UUID,
    user_id: str,
    is_admin: bool = False,
) -> bool:
    """Soft-delete a comment and decrement the post's comment_count."""
    result = await comment_repo.soft_delete(
        comment_id,
        post_id=post_id,
        user_id=uuid.UUID(user_id) if not is_admin else None,
        is_admin=is_admin,
    )
    if result is None:
        return False
    logger.info("Comment deleted", extra={"comment_id": str(comment_id)})
    return True


async def add_reaction(
    comment_id: uuid.UUID,
    user_id: str,
    reaction: str,
) -> dict | None:
    """Toggle a reaction on a comment. Returns updated comment."""
    row = await comment_repo.update_reactions(comment_id, user_id, reaction)
    return await async_row_to_comment(row) if row else None

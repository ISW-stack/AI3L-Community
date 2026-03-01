import uuid

from loguru import logger

from app.converters.comment_converter import row_to_comment
from app.core.constants import MAX_COMMENTS_PER_POST
from app.core.database import get_pool
from app.core.event_bus import emit
from app.repositories import comment_repo


async def create_comment(
    post_id: uuid.UUID,
    user_id: str,
    content: str,
    parent_id: str | None = None,
    mentions: list[str] | None = None,
) -> dict:
    pool = get_pool()
    comment_id = uuid.uuid4()
    parent_uuid = uuid.UUID(parent_id) if parent_id else None

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
                "UPDATE posts SET comment_count = comment_count + 1 WHERE id = $1",
                post_id,
            )

            comment_dict = row_to_comment(row)
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
                        mention_targets.append((target_uid, str(comment_id)))

            if parent_uuid:
                parent_user_id = await comment_repo.find_parent_user_id(parent_uuid, conn)
                if parent_user_id and parent_user_id != user_id:
                    reply_target = (parent_user_id, str(comment_id))

    # Fire notifications via event bus (outside the transaction)
    await emit(
        "comment.created",
        user_id=user_id,
        commenter_name=commenter_name,
        mention_targets=mention_targets,
        reply_target=reply_target,
    )

    logger.info("Comment created", extra={"comment_id": str(comment_id), "post_id": str(post_id)})
    return comment_dict


async def update_comment(
    comment_id: uuid.UUID,
    user_id: str,
    content: str,
) -> dict | None:
    """Update comment content. Only the owner can edit."""
    row = await comment_repo.update(comment_id, uuid.UUID(user_id), content)
    if not row:
        return None
    logger.info("Comment updated", extra={"comment_id": str(comment_id)})
    return row_to_comment(row)


async def list_comments(
    post_id: uuid.UUID,
    offset: int = 0,
    limit: int = 50,
) -> tuple[list[dict], int]:
    rows, total = await comment_repo.find_many(post_id, offset, limit)
    return [row_to_comment(r) for r in rows], total


async def soft_delete_comment(
    comment_id: uuid.UUID,
    user_id: str,
    is_admin: bool = False,
) -> bool:
    """Soft-delete a comment and decrement the post's comment_count."""
    result = await comment_repo.soft_delete(
        comment_id,
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
    return row_to_comment(row) if row else None

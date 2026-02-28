import json
import uuid

from loguru import logger

from app.core.database import get_pool

_MAX_COMMENTS_PER_POST = 200

_COMMENT_SELECT = """
    SELECT cm.*,
           u.id AS author_id, u.username AS author_username,
           u.display_name AS author_display_name, u.avatar_url AS author_avatar_url
    FROM comments cm
    JOIN users u ON cm.user_id = u.id
"""


def _row_to_comment(row: dict) -> dict:
    return {
        "id": str(row["id"]),
        "post_id": str(row["post_id"]),
        "content": row["content"],
        "author": {
            "id": str(row["author_id"]),
            "username": row["author_username"],
            "display_name": row["author_display_name"],
            "avatar_url": row.get("author_avatar_url"),
        },
        "parent_id": str(row["parent_id"]) if row.get("parent_id") else None,
        "mentions": row.get("mentions"),
        "reactions": json.loads(row["reactions"]) if isinstance(row.get("reactions"), str) else row.get("reactions"),
        "created_at": row["created_at"].isoformat(),
        "updated_at": row["updated_at"].isoformat(),
    }


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
            # Check post exists and allows comments
            post = await conn.fetchrow(
                "SELECT id, allow_comments, comment_count FROM posts WHERE id = $1 AND is_deleted = false",
                post_id,
            )
            if not post:
                raise ValueError("Post not found.")
            if not post["allow_comments"]:
                raise ValueError("Comments are disabled for this post.")
            if post["comment_count"] >= _MAX_COMMENTS_PER_POST:
                raise ValueError(f"Comment limit ({_MAX_COMMENTS_PER_POST}) reached for this post.")

            # Validate parent comment if provided
            if parent_uuid:
                parent = await conn.fetchrow(
                    "SELECT id FROM comments WHERE id = $1 AND post_id = $2 AND is_deleted = false",
                    parent_uuid,
                    post_id,
                )
                if not parent:
                    raise ValueError("Parent comment not found.")

            row = await conn.fetchrow(
                f"""
                WITH inserted AS (
                    INSERT INTO comments (id, post_id, user_id, parent_id, content, mentions)
                    VALUES ($1, $2, $3, $4, $5, $6)
                    RETURNING *
                )
                {_COMMENT_SELECT.replace("FROM comments cm", "FROM inserted cm")}
                """,
                comment_id,
                post_id,
                uuid.UUID(user_id),
                parent_uuid,
                content,
                mentions,
            )

            # Increment post comment_count
            await conn.execute(
                "UPDATE posts SET comment_count = comment_count + 1 WHERE id = $1",
                post_id,
            )

            logger.info("Comment created", extra={"comment_id": str(comment_id), "post_id": str(post_id)})
            return _row_to_comment(dict(row))


async def list_comments(
    post_id: uuid.UUID,
    offset: int = 0,
    limit: int = 50,
) -> tuple[list[dict], int]:
    pool = get_pool()
    async with pool.acquire() as conn:
        total = await conn.fetchval(
            "SELECT COUNT(*) FROM comments WHERE post_id = $1 AND is_deleted = false",
            post_id,
        )
        rows = await conn.fetch(
            f"{_COMMENT_SELECT} WHERE cm.post_id = $1 AND cm.is_deleted = false ORDER BY cm.created_at ASC LIMIT $2 OFFSET $3",
            post_id,
            limit,
            offset,
        )
        return [_row_to_comment(dict(r)) for r in rows], total


async def soft_delete_comment(
    comment_id: uuid.UUID,
    user_id: str,
    is_admin: bool = False,
) -> bool:
    """Soft-delete a comment and decrement the post's comment_count."""
    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            if is_admin:
                row = await conn.fetchrow(
                    "UPDATE comments SET is_deleted = true, updated_at = NOW() "
                    "WHERE id = $1 AND is_deleted = false RETURNING post_id",
                    comment_id,
                )
            else:
                row = await conn.fetchrow(
                    "UPDATE comments SET is_deleted = true, updated_at = NOW() "
                    "WHERE id = $1 AND user_id = $2 AND is_deleted = false RETURNING post_id",
                    comment_id,
                    uuid.UUID(user_id),
                )

            if not row:
                return False

            await conn.execute(
                "UPDATE posts SET comment_count = GREATEST(comment_count - 1, 0) WHERE id = $1",
                row["post_id"],
            )
            logger.info("Comment deleted", extra={"comment_id": str(comment_id)})
            return True


async def add_reaction(
    comment_id: uuid.UUID,
    user_id: str,
    reaction: str,
) -> dict | None:
    """Toggle a reaction on a comment. Returns updated comment."""
    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                "SELECT * FROM comments WHERE id = $1 AND is_deleted = false FOR UPDATE",
                comment_id,
            )
            if not row:
                return None

            raw_reactions = row["reactions"]
            if isinstance(raw_reactions, str):
                reactions = json.loads(raw_reactions)
            elif raw_reactions:
                reactions = dict(raw_reactions)
            else:
                reactions = {}
            # Each reaction is a dict: {"LIKE": ["user_id1", ...], "SMILE": [...]}
            if reaction not in reactions:
                reactions[reaction] = []

            user_list = reactions[reaction]
            if user_id in user_list:
                user_list.remove(user_id)  # Toggle off
            else:
                user_list.append(user_id)  # Toggle on

            if not user_list:
                del reactions[reaction]

            await conn.execute(
                "UPDATE comments SET reactions = $1::jsonb, updated_at = NOW() WHERE id = $2",
                json.dumps(reactions),
                comment_id,
            )

            # Re-fetch with author join
            result = await conn.fetchrow(
                f"{_COMMENT_SELECT} WHERE cm.id = $1",
                comment_id,
            )
            return _row_to_comment(dict(result)) if result else None

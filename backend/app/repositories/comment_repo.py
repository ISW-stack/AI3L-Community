import json
import uuid
from typing import Any

from app.core.database import get_pool

_COMMENT_SELECT = """
    SELECT cm.*,
           u.id AS author_id, u.username AS author_username,
           u.display_name AS author_display_name, u.avatar_url AS author_avatar_url
    FROM comments cm
    JOIN users u ON cm.user_id = u.id
"""


async def insert(
    comment_id: uuid.UUID,
    post_id: uuid.UUID,
    user_id: uuid.UUID,
    parent_id: uuid.UUID | None,
    content: str,
    mentions: list[str] | None,
    conn: Any,
) -> dict:
    """Insert a comment within an existing transaction/connection."""
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
        user_id,
        parent_id,
        content,
        mentions,
    )
    return dict(row)


async def find_post_for_comment(post_id: uuid.UUID, conn: Any) -> dict | None:
    """Check post exists and get comment-relevant fields."""
    row = await conn.fetchrow(
        "SELECT id, allow_comments, comment_count FROM posts WHERE id = $1 AND is_deleted = false",
        post_id,
    )
    return dict(row) if row else None


async def find_parent(comment_id: uuid.UUID, post_id: uuid.UUID, conn: Any) -> dict | None:
    row = await conn.fetchrow(
        "SELECT id FROM comments WHERE id = $1 AND post_id = $2 AND is_deleted = false",
        comment_id,
        post_id,
    )
    return dict(row) if row else None


async def find_mentioned_users(usernames: list[str], conn: Any) -> list[dict]:
    rows = await conn.fetch(
        "SELECT id, username FROM users WHERE username = ANY($1) AND is_deleted = false",
        usernames,
    )
    return [dict(r) for r in rows]


async def find_parent_user_id(comment_id: uuid.UUID, conn: Any) -> str | None:
    row = await conn.fetchrow(
        "SELECT user_id FROM comments WHERE id = $1",
        comment_id,
    )
    return str(row["user_id"]) if row else None


async def find_many(
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
            f"{_COMMENT_SELECT} WHERE cm.post_id = $1 AND cm.is_deleted = false ORDER BY cm.created_at ASC LIMIT $2 OFFSET $3",  # noqa: E501
            post_id,
            limit,
            offset,
        )
        return [dict(r) for r in rows], total


async def update(
    comment_id: uuid.UUID,
    user_id: uuid.UUID,
    content: str,
) -> dict | None:
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            f"""
            WITH updated AS (
                UPDATE comments SET content = $1, updated_at = NOW()
                WHERE id = $2 AND user_id = $3 AND is_deleted = false
                RETURNING *
            )
            {_COMMENT_SELECT.replace("FROM comments cm", "FROM updated cm")}
            """,
            content,
            comment_id,
            user_id,
        )
        return dict(row) if row else None


async def soft_delete(
    comment_id: uuid.UUID,
    user_id: uuid.UUID | None = None,
    is_admin: bool = False,
) -> uuid.UUID | None:
    """Soft-delete and return post_id for count decrement. Returns None if not found."""
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
                    user_id,
                )

            if not row:
                return None

            await conn.execute(
                "UPDATE posts SET comment_count = GREATEST(comment_count - 1, 0) WHERE id = $1",
                row["post_id"],
            )
            return uuid.UUID(str(row["post_id"]))


async def find_by_id(comment_id: uuid.UUID) -> dict | None:
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            f"{_COMMENT_SELECT} WHERE cm.id = $1",
            comment_id,
        )
        return dict(row) if row else None


async def update_reactions(comment_id: uuid.UUID, user_id: str, reaction: str) -> dict | None:
    """Toggle a reaction on a comment. Returns updated comment row."""
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

            if reaction not in reactions:
                reactions[reaction] = []

            user_list = reactions[reaction]
            if user_id in user_list:
                user_list.remove(user_id)
            else:
                user_list.append(user_id)

            if not user_list:
                del reactions[reaction]

            await conn.execute(
                "UPDATE comments SET reactions = $1::jsonb, updated_at = NOW() WHERE id = $2",
                json.dumps(reactions),
                comment_id,
            )

            result = await conn.fetchrow(
                f"{_COMMENT_SELECT} WHERE cm.id = $1",
                comment_id,
            )
            return dict(result) if result else None

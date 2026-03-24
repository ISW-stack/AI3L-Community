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
        "SELECT id, allow_comments, comment_count, type "
        "FROM posts WHERE id = $1 AND is_deleted = false FOR UPDATE",
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
        "SELECT user_id FROM comments WHERE id = $1 AND is_deleted = false",
        comment_id,
    )
    return str(row["user_id"]) if row else None


async def find_many(
    post_id: uuid.UUID,
    offset: int = 0,
    limit: int = 50,
    exclude_user_ids: list[uuid.UUID] | None = None,
) -> tuple[list[dict], int]:
    _select_count = _COMMENT_SELECT.replace(
        "FROM comments cm", ", COUNT(*) OVER() AS _total\n    FROM comments cm", 1
    )
    pool = get_pool()

    exclusion_clause = ""
    params: list = [post_id, limit, offset]
    if exclude_user_ids:
        exclusion_clause = " AND cm.user_id != ALL($4::uuid[])"
        params.append(exclude_user_ids)

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"{_select_count} WHERE cm.post_id = $1 AND cm.is_deleted = false{exclusion_clause} ORDER BY cm.created_at ASC LIMIT $2 OFFSET $3",  # noqa: E501
            *params,
        )
        if rows:
            total = rows[0]["_total"]
            result = [{k: v for k, v in dict(r).items() if k != "_total"} for r in rows]
        else:
            count_clause = ""
            count_params: list = [post_id]
            if exclude_user_ids:
                count_clause = " AND user_id != ALL($2::uuid[])"
                count_params.append(exclude_user_ids)
            total = await conn.fetchval(
                "SELECT COUNT(*) FROM comments"
                f" WHERE post_id = $1 AND is_deleted = false{count_clause}",
                *count_params,
            )
            result = []
        return result, total


async def update(
    comment_id: uuid.UUID,
    user_id: uuid.UUID,
    content: str,
    post_id: uuid.UUID | None = None,
) -> dict | None:
    pool = get_pool()
    async with pool.acquire() as conn:
        where_clause = "WHERE id = $2 AND user_id = $3 AND is_deleted = false"
        params: list[Any] = [content, comment_id, user_id]
        if post_id is not None:
            where_clause += " AND post_id = $4"
            params.append(post_id)
        row = await conn.fetchrow(
            f"""
            WITH updated AS (
                UPDATE comments SET content = $1, updated_at = NOW()
                {where_clause}
                RETURNING *
            )
            {_COMMENT_SELECT.replace("FROM comments cm", "FROM updated cm")}
            """,
            *params,
        )
        return dict(row) if row else None


async def soft_delete(
    comment_id: uuid.UUID,
    post_id: uuid.UUID,
    user_id: uuid.UUID | None = None,
    is_admin: bool = False,
) -> uuid.UUID | None:
    """Soft-delete and return post_id for count decrement. Returns None if not found.

    When deleting a parent comment (parent_id IS NULL), also soft-deletes all
    child comments and adjusts comment_count/answer_count accordingly.
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            if is_admin:
                row = await conn.fetchrow(
                    "UPDATE comments SET is_deleted = true, updated_at = NOW() "
                    "WHERE id = $1 AND post_id = $2 AND is_deleted = false "
                    "RETURNING post_id, parent_id",
                    comment_id,
                    post_id,
                )
            else:
                row = await conn.fetchrow(
                    "UPDATE comments SET is_deleted = true, updated_at = NOW() "
                    "WHERE id = $1 AND post_id = $2 AND user_id = $3 AND is_deleted = false "
                    "RETURNING post_id, parent_id",
                    comment_id,
                    post_id,
                    user_id,
                )

            if not row:
                return None

            total_deleted = 1  # The parent/target comment itself

            # If this is a top-level comment, also soft-delete all child comments
            # and get the exact count atomically using RETURNING
            if row["parent_id"] is None:
                child_rows = await conn.fetch(
                    "UPDATE comments SET is_deleted = true, updated_at = NOW() "
                    "WHERE parent_id = $1 AND post_id = $2 AND is_deleted = false "
                    "RETURNING id",
                    comment_id,
                    post_id,
                )
                total_deleted += len(child_rows)

            # Decrement comment_count by total deleted (parent + children)
            await conn.execute(
                "UPDATE posts SET comment_count = GREATEST(comment_count - $1, 0) WHERE id = $2",
                total_deleted,
                row["post_id"],
            )

            # Decrement answer_count for top-level comments on Q&A posts
            if row["parent_id"] is None:
                await conn.execute(
                    "UPDATE posts SET answer_count = GREATEST(answer_count - 1, 0) "
                    "WHERE id = $1 AND type = 'question'",
                    row["post_id"],
                )

            # Clear best_answer_id if this comment was the best answer
            await conn.execute(
                "UPDATE posts SET best_answer_id = NULL WHERE best_answer_id = $1",
                comment_id,
            )

            return uuid.UUID(str(row["post_id"]))


async def find_by_id(comment_id: uuid.UUID) -> dict | None:
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            f"{_COMMENT_SELECT} WHERE cm.id = $1 AND cm.is_deleted = false",
            comment_id,
        )
        return dict(row) if row else None


async def update_reactions(comment_id: uuid.UUID, user_id: str, reaction: str) -> dict | None:
    """Toggle a reaction on a comment. Returns updated comment row."""
    from app.repositories.reaction_helpers import toggle_reaction_jsonb

    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            # Check comment exists and is not deleted
            check = await conn.fetchrow(
                "SELECT id FROM comments WHERE id = $1 AND is_deleted = false",
                comment_id,
            )
            if not check:
                return None

            await toggle_reaction_jsonb(conn, "comments", str(comment_id), user_id, reaction)

            result = await conn.fetchrow(
                f"{_COMMENT_SELECT} WHERE cm.id = $1",
                comment_id,
            )
            return dict(result) if result else None

import math
import uuid
from typing import Any

from app.core.database import get_pool

_POST_SELECT = """
    SELECT p.*,
           u.id AS author_id, u.username AS author_username,
           u.display_name AS author_display_name, u.avatar_url AS author_avatar_url,
           c.name AS category_name
    FROM posts p
    JOIN users u ON p.user_id = u.id
    LEFT JOIN categories c ON p.category_id = c.id
"""

_SORT_MAP = {
    "newest": "p.is_pinned DESC, p.created_at DESC",
    "oldest": "p.is_pinned DESC, p.created_at ASC",
    "most_comments": "p.is_pinned DESC, p.comment_count DESC, p.created_at DESC",
}


async def insert(
    post_id: uuid.UUID,
    user_id: uuid.UUID,
    title: str,
    content: str,
    category_id: uuid.UUID | None,
    sig_id: uuid.UUID | None,
    keywords: list[str] | None,
    allow_comments: bool,
) -> dict:
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            f"""
            WITH inserted AS (
                INSERT INTO posts (id, user_id, title, content, category_id, sig_id, keywords, allow_comments)  # noqa: E501
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                RETURNING *
            )
            {_POST_SELECT.replace("FROM posts p", "FROM inserted p")}
            """,
            post_id,
            user_id,
            title,
            content,
            category_id,
            sig_id,
            keywords,
            allow_comments,
        )
        return dict(row)


async def find_by_id(post_id: uuid.UUID) -> dict | None:
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            f"{_POST_SELECT} WHERE p.id = $1 AND p.is_deleted = false",
            post_id,
        )
        return dict(row) if row else None


async def find_for_update(post_id: uuid.UUID, conn: Any) -> dict | None:
    """Fetch post with FOR UPDATE lock. Must be called within a transaction."""
    row = await conn.fetchrow(
        "SELECT * FROM posts WHERE id = $1 AND is_deleted = false FOR UPDATE",
        post_id,
    )
    return dict(row) if row else None


async def insert_history(
    history_id: uuid.UUID,
    post_id: uuid.UUID,
    version: int,
    title: str,
    content: str,
    conn: Any,
) -> None:
    """Insert a post history record. Must be called within a transaction."""
    await conn.execute(
        """
        INSERT INTO post_history (id, post_id, version, title, content)
        VALUES ($1, $2, $3, $4, $5)
        """,
        history_id,
        post_id,
        version,
        title,
        content,
    )


async def update_in_transaction(
    conn: Any,
    post_id: uuid.UUID,
    title: str,
    content: str,
    category_id: uuid.UUID | None,
    keywords: list[str] | None,
    allow_comments: bool,
) -> dict:
    """Update post within an existing transaction/connection."""
    row = await conn.fetchrow(
        f"""
        WITH updated AS (
            UPDATE posts SET
                title = $1, content = $2, category_id = $3, keywords = $4,
                allow_comments = $5, version = version + 1, updated_at = NOW()
            WHERE id = $6
            RETURNING *
        )
        {_POST_SELECT.replace("FROM posts p", "FROM updated p")}
        """,
        title,
        content,
        category_id,
        keywords,
        allow_comments,
        post_id,
    )
    return dict(row)


async def soft_delete(post_id: uuid.UUID, user_id: uuid.UUID | None = None) -> bool:
    """Soft-delete a post. If user_id given, restrict to owner."""
    pool = get_pool()
    async with pool.acquire() as conn:
        if user_id:
            result = await conn.execute(
                "UPDATE posts SET is_deleted = true, updated_at = NOW() WHERE id = $1 AND user_id = $2 AND is_deleted = false",  # noqa: E501
                post_id,
                user_id,
            )
        else:
            result = await conn.execute(
                "UPDATE posts SET is_deleted = true, updated_at = NOW() WHERE id = $1 AND is_deleted = false",  # noqa: E501
                post_id,
            )
        return bool(result == "UPDATE 1")


async def find_owner_id(post_id: uuid.UUID) -> str | None:
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT user_id FROM posts WHERE id = $1 AND is_deleted = false",
            post_id,
        )
        return str(row["user_id"]) if row else None


async def find_history(post_id: uuid.UUID) -> list[dict]:
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM post_history WHERE post_id = $1 ORDER BY version DESC",
            post_id,
        )
        return [dict(r) for r in rows]


async def find_many(
    page: int = 1,
    page_size: int = 20,
    category_id: uuid.UUID | None = None,
    sig_id: uuid.UUID | None = None,
    author_id: uuid.UUID | None = None,
    sort: str = "newest",
) -> tuple[list[dict], int, int]:
    pool = get_pool()
    offset = (page - 1) * page_size
    order_by = _SORT_MAP.get(sort, _SORT_MAP["newest"])

    where = "WHERE p.is_deleted = false"
    params: list = []
    idx = 1

    if category_id:
        where += f" AND p.category_id = ${idx}"
        params.append(category_id)
        idx += 1

    if sig_id:
        where += f" AND p.sig_id = ${idx}"
        params.append(sig_id)
        idx += 1

    if author_id:
        where += f" AND p.user_id = ${idx}"
        params.append(author_id)
        idx += 1

    _select_count = _POST_SELECT.replace(
        "FROM posts p", ", COUNT(*) OVER() AS _total\n    FROM posts p", 1
    )

    # Save params before extending with LIMIT/OFFSET for potential fallback count query
    count_params = list(params)

    async with pool.acquire() as conn:
        params.extend([page_size, offset])
        rows = await conn.fetch(
            f"{_select_count} {where} ORDER BY {order_by} LIMIT ${idx} OFFSET ${idx + 1}",
            *params,
        )
        if rows:
            total = rows[0]["_total"]
            result = [{k: v for k, v in dict(r).items() if k != "_total"} for r in rows]
        else:
            # Page may be out of range — do a separate count to get real total
            total = await conn.fetchval(
                f"SELECT COUNT(*) FROM posts p {where}",
                *count_params,
            )
            result = []
        total_pages = max(1, math.ceil(total / page_size))
        return result, total, total_pages


async def search(
    keyword: str | None = None,
    category_id: uuid.UUID | None = None,
    keywords_filter: list[str] | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    logic: str = "AND",
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[dict], int, int]:
    pool = get_pool()
    offset = (page - 1) * page_size

    conditions = ["p.is_deleted = false"]
    params: list = []
    idx = 1

    if keyword:
        ts_query_op = " & " if logic == "AND" else " | "
        terms = keyword.strip().split()
        ts_query = ts_query_op.join(terms)
        conditions.append(f"p.search_vector @@ to_tsquery('english', ${idx})")
        params.append(ts_query)
        idx += 1

    if category_id:
        conditions.append(f"p.category_id = ${idx}")
        params.append(category_id)
        idx += 1

    if keywords_filter:
        conditions.append(f"p.keywords && ${idx}")
        params.append(keywords_filter)
        idx += 1

    if date_from:
        conditions.append(f"p.created_at >= ${idx}::timestamptz")
        params.append(date_from)
        idx += 1

    if date_to:
        conditions.append(f"p.created_at <= ${idx}::timestamptz")
        params.append(date_to)
        idx += 1

    where = "WHERE " + " AND ".join(conditions)

    _select_count = _POST_SELECT.replace(
        "FROM posts p", ", COUNT(*) OVER() AS _total\n    FROM posts p", 1
    )

    # Save params before extending with LIMIT/OFFSET for potential fallback count query
    count_params = list(params)

    async with pool.acquire() as conn:
        params.extend([page_size, offset])
        rows = await conn.fetch(
            f"{_select_count} {where} ORDER BY p.is_pinned DESC, p.created_at DESC LIMIT ${idx} OFFSET ${idx + 1}",  # noqa: E501
            *params,
        )
        if rows:
            total = rows[0]["_total"]
            result = [{k: v for k, v in dict(r).items() if k != "_total"} for r in rows]
        else:
            # Page may be out of range — do a separate count to get real total
            total = await conn.fetchval(
                f"SELECT COUNT(*) FROM posts p {where}",
                *count_params,
            )
            result = []
        total_pages = max(1, math.ceil(total / page_size))
        return result, total, total_pages


async def increment_comment_count(post_id: uuid.UUID, conn: Any) -> None:
    await conn.execute(
        "UPDATE posts SET comment_count = comment_count + 1 WHERE id = $1",
        post_id,
    )


async def decrement_comment_count(post_id: uuid.UUID, conn: Any) -> None:
    await conn.execute(
        "UPDATE posts SET comment_count = GREATEST(comment_count - 1, 0) WHERE id = $1",
        post_id,
    )


async def bulk_soft_delete(post_ids: list[uuid.UUID], conn: Any) -> int:
    """Soft-delete multiple posts. Returns count of deleted."""
    result = await conn.execute(
        "UPDATE posts SET is_deleted = true, updated_at = NOW() WHERE id = ANY($1::uuid[]) AND is_deleted = false",  # noqa: E501
        post_ids,
    )
    return int(result.split()[-1])


async def update_pin_status(post_id: uuid.UUID, is_pinned: bool) -> bool:
    pool = get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "UPDATE posts SET is_pinned = $1, updated_at = NOW() WHERE id = $2 AND is_deleted = false",  # noqa: E501
            is_pinned,
            post_id,
        )
        return bool(result == "UPDATE 1")


async def increment_view_count(post_id: uuid.UUID) -> None:
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE posts SET view_count = view_count + 1 WHERE id = $1",
            post_id,
        )


async def update_last_comment_at(post_id: uuid.UUID, conn: Any) -> None:
    """Update last_comment_at to NOW(). Must be called within a transaction."""
    await conn.execute(
        "UPDATE posts SET last_comment_at = NOW() WHERE id = $1",
        post_id,
    )


async def find_trending(limit: int = 5, days: int = 7) -> list[dict]:
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"""
            {_POST_SELECT}
            WHERE p.is_deleted = false
              AND p.created_at >= NOW() - make_interval(days => $1)
            ORDER BY p.comment_count DESC, p.created_at DESC
            LIMIT $2
            """,
            days,
            limit,
        )
        return [dict(r) for r in rows]

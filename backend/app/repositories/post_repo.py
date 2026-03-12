import base64
import math
import shlex
import uuid
from datetime import datetime
from typing import Any

from app.core.database import get_pool

_POST_SELECT = """
    SELECT p.*,
           u.id AS author_id, u.username AS author_username,
           u.display_name AS author_display_name, u.avatar_url AS author_avatar_url,
           c.name AS category_name,
           s.name AS sig_name
    FROM posts p
    JOIN users u ON p.user_id = u.id
    LEFT JOIN categories c ON p.category_id = c.id
    LEFT JOIN sigs s ON p.sig_id = s.id
"""

_SORT_MAP = {
    "newest": "p.is_pinned DESC, p.created_at DESC",
    "oldest": "p.is_pinned DESC, p.created_at ASC",
    "most_comments": "p.is_pinned DESC, p.comment_count DESC, p.created_at DESC",
    "popular": "p.is_pinned DESC, p.like_count DESC, p.created_at DESC",
}

# Sorts that support cursor pagination and the comparison direction they use
# "popular" maps to like_count; otherwise created_at is the primary key
_CURSOR_SORT_ASC = {"oldest"}  # use > comparison
_CURSOR_SORT_DESC = {"newest", "popular"}  # use < comparison


def _encode_cursor(primary_val: str, row_id: uuid.UUID, sort: str) -> str:
    """Encode a pagination cursor as URL-safe base64.

    Format of the raw string: ``"<sort>|<primary_val>|<id>"``.
    ``primary_val`` is an ISO-format datetime string for time-based sorts,
    or a stringified integer for ``popular`` (like_count).
    """
    raw = f"{sort}|{primary_val}|{row_id}"
    return base64.urlsafe_b64encode(raw.encode()).decode()


def _decode_cursor(cursor: str) -> tuple[str, str, uuid.UUID]:
    """Decode a cursor produced by ``_encode_cursor``.

    Returns ``(sort, primary_val, id)``.
    Raises ``ValueError`` on malformed input.
    """
    try:
        raw = base64.urlsafe_b64decode(cursor.encode()).decode()
        parts = raw.split("|", 2)
        if len(parts) != 3:
            raise ValueError("bad cursor format")
        sort, primary_val, id_str = parts
        return sort, primary_val, uuid.UUID(id_str)
    except Exception as exc:
        raise ValueError(f"Invalid cursor: {exc}") from exc


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
                INSERT INTO posts (
                    id, user_id, title, content, category_id, sig_id, keywords, allow_comments
                )
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


async def find_content_by_id(post_id: uuid.UUID) -> str | None:
    """Return the raw HTML content of a post (even if soft-deleted)."""
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT content FROM posts WHERE id = $1", post_id)
        return row["content"] if row else None


async def find_history(post_id: uuid.UUID, limit: int = 50) -> list[dict]:
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM post_history WHERE post_id = $1 ORDER BY version DESC LIMIT $2",
            post_id,
            limit,
        )
        return [dict(r) for r in rows]


async def find_many(
    page: int = 1,
    page_size: int = 20,
    category_id: uuid.UUID | None = None,
    sig_id: uuid.UUID | None = None,
    author_id: uuid.UUID | None = None,
    sort: str = "newest",
    cursor: str | None = None,
) -> dict:
    """Fetch posts with either OFFSET pagination (cursor=None) or keyset pagination.

    Returns a dict with keys:
      posts        – list of post dicts
      total        – int or None (OFFSET mode only)
      total_pages  – int or None (OFFSET mode only)
      next_cursor  – str or None (cursor mode only)
      has_more     – bool or None (cursor mode only)
    """
    pool = get_pool()
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

    # ------------------------------------------------------------------ cursor mode
    if cursor is not None:
        cursor_sort, primary_val, cursor_id = _decode_cursor(cursor)

        # Use the sort embedded in the cursor as the canonical sort.  This prevents
        # a mismatch between the ORDER BY direction and the keyset WHERE comparison
        # when the caller passes a different `sort` query-param alongside a cursor.
        cursor_order_by = _SORT_MAP.get(cursor_sort, _SORT_MAP["newest"])

        use_asc = cursor_sort in _CURSOR_SORT_ASC
        cmp = ">" if use_asc else "<"

        if cursor_sort == "popular":
            # primary key is like_count (integer)
            like_count_val = int(primary_val)
            where += f" AND (p.like_count, p.id::text) {cmp} (${idx}, ${idx + 1})"
            params.extend([like_count_val, str(cursor_id)])
        else:
            # primary key is created_at (timestamptz)
            created_at_val = datetime.fromisoformat(primary_val)
            where += f" AND (p.created_at, p.id::text) {cmp} (${idx}, ${idx + 1})"
            params.extend([created_at_val, str(cursor_id)])
        idx += 2

        fetch_limit = page_size + 1
        params.append(fetch_limit)

        async with pool.acquire() as conn:
            rows = await conn.fetch(
                f"{_POST_SELECT} {where} ORDER BY {cursor_order_by} LIMIT ${idx}",
                *params,
            )

        rows_list = [dict(r) for r in rows]
        has_more = len(rows_list) > page_size
        if has_more:
            rows_list = rows_list[:page_size]

        next_cursor: str | None = None
        if has_more and rows_list:
            last = rows_list[-1]
            if cursor_sort == "popular":
                like_count_raw = last.get("like_count")
                next_cursor = _encode_cursor(
                    str(like_count_raw if like_count_raw is not None else 0),
                    last["id"],
                    cursor_sort,
                )
            else:
                created_at: datetime = last["created_at"]
                next_cursor = _encode_cursor(created_at.isoformat(), last["id"], cursor_sort)

        return {
            "posts": rows_list,
            "next_cursor": next_cursor,
            "has_more": has_more,
            "total": None,
            "total_pages": None,
        }

    # ------------------------------------------------------------------ OFFSET mode
    offset = (page - 1) * page_size

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
            total: int = rows[0]["_total"]
            result = [{k: v for k, v in dict(r).items() if k != "_total"} for r in rows]
        else:
            # Page may be out of range — do a separate count to get real total
            total = await conn.fetchval(
                f"SELECT COUNT(*) FROM posts p {where}",
                *count_params,
            )
            result = []
        total_pages = max(1, math.ceil(total / page_size))
        return {
            "posts": result,
            "total": total,
            "total_pages": total_pages,
            "next_cursor": None,
            "has_more": None,
        }


async def search(
    keyword: str | None = None,
    category_id: uuid.UUID | None = None,
    keywords_filter: list[str] | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    logic: str = "AND",
    page: int = 1,
    page_size: int = 20,
    sort: str = "newest",
) -> tuple[list[dict], int, int]:
    pool = get_pool()
    offset = (page - 1) * page_size
    order_by = _SORT_MAP.get(sort, _SORT_MAP["newest"])

    conditions = ["p.is_deleted = false"]
    params: list = []
    idx = 1

    if keyword:
        search_input = keyword.strip()
        if logic == "OR":
            # Split respecting quoted phrases, then rejoin with OR for websearch_to_tsquery
            lex = shlex.shlex(search_input, posix=False)
            lex.whitespace_split = True
            try:
                terms = list(lex)
            except ValueError:
                terms = search_input.split()
            search_input = " OR ".join(terms)
        conditions.append(f"p.search_vector @@ websearch_to_tsquery('english', ${idx})")
        params.append(search_input)
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
        # Cast to date then add 1 day so the entire end date is included
        conditions.append(f"p.created_at < (${idx}::date + INTERVAL '1 day')")
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
            "UPDATE posts SET view_count = view_count + 1 WHERE id = $1 AND is_deleted = FALSE",
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


async def toggle_reaction(post_id: uuid.UUID, user_id: str, reaction: str) -> dict | None:
    """Toggle a reaction on a post. Returns updated post row."""
    from app.repositories.reaction_helpers import toggle_reaction_jsonb

    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            check = await conn.fetchrow(
                "SELECT id FROM posts WHERE id = $1 AND is_deleted = false",
                post_id,
            )
            if not check:
                return None

            await toggle_reaction_jsonb(conn, "posts", str(post_id), user_id, reaction)

            row = await conn.fetchrow(
                f"{_POST_SELECT} WHERE p.id = $1",
                post_id,
            )
            return dict(row) if row else None


async def get_search_suggestions(query: str, limit: int = 5) -> list[dict]:
    """Return posts whose title or keywords match the query (ILIKE)."""
    pool = get_pool()
    async with pool.acquire() as conn:
        sql = """
            SELECT DISTINCT title, id
            FROM posts
            WHERE is_deleted = FALSE
              AND (title ILIKE $1 OR EXISTS (
                  SELECT 1 FROM unnest(keywords) AS kw WHERE kw ILIKE $1
              ))
            ORDER BY title
            LIMIT $2
        """
        rows = await conn.fetch(sql, f"%{query}%", limit)
        return [dict(r) for r in rows]


async def get_keyword_suggestions(query: str, limit: int = 5) -> list[str]:
    """Return distinct keywords matching the query (ILIKE)."""
    pool = get_pool()
    async with pool.acquire() as conn:
        sql = """
            SELECT DISTINCT kw
            FROM posts, unnest(keywords) AS kw
            WHERE posts.is_deleted = FALSE AND kw ILIKE $1
            ORDER BY kw
            LIMIT $2
        """
        rows = await conn.fetch(sql, f"%{query}%", limit)
        return [r["kw"] for r in rows]

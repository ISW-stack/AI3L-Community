import math
import uuid
from datetime import datetime, timezone

from loguru import logger

from app.core.database import get_pool
from app.core.redis import get_redis


async def _check_daily_post_limit(user_id: str) -> bool:
    """Check if user has exceeded 50 posts/day limit. Returns True if within limit."""
    redis = get_redis()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    key = f"post_limit:{user_id}:{today}"
    count = await redis.get(key)
    if count is not None and int(count) >= 50:
        return False
    return True


async def _increment_daily_post_count(user_id: str) -> None:
    redis = get_redis()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    key = f"post_limit:{user_id}:{today}"
    pipe = redis.pipeline()
    pipe.incr(key)
    pipe.expire(key, 86400)
    await pipe.execute()


def _build_author_dict(row: dict) -> dict:
    return {
        "id": str(row["author_id"]),
        "username": row["author_username"],
        "display_name": row["author_display_name"],
        "avatar_url": row.get("author_avatar_url"),
    }


def _row_to_post(row: dict) -> dict:
    return {
        "id": str(row["id"]),
        "title": row["title"],
        "content": row["content"],
        "author": _build_author_dict(row),
        "category_id": str(row["category_id"]) if row.get("category_id") else None,
        "category_name": row.get("category_name"),
        "keywords": row.get("keywords"),
        "allow_comments": row["allow_comments"],
        "version": row["version"],
        "comment_count": row["comment_count"],
        "created_at": row["created_at"].isoformat(),
        "updated_at": row["updated_at"].isoformat(),
    }


_POST_SELECT = """
    SELECT p.*,
           u.id AS author_id, u.username AS author_username,
           u.display_name AS author_display_name, u.avatar_url AS author_avatar_url,
           c.name AS category_name
    FROM posts p
    JOIN users u ON p.user_id = u.id
    LEFT JOIN categories c ON p.category_id = c.id
"""


async def create_post(
    user_id: str,
    title: str,
    content: str,
    category_id: str | None = None,
    keywords: list[str] | None = None,
    allow_comments: bool = True,
) -> dict:
    if not await _check_daily_post_limit(user_id):
        raise ValueError("Daily post limit (50) exceeded.")

    pool = get_pool()
    post_id = uuid.uuid4()
    cat_uuid = uuid.UUID(category_id) if category_id else None

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            f"""
            WITH inserted AS (
                INSERT INTO posts (id, user_id, title, content, category_id, keywords, allow_comments)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                RETURNING *
            )
            {_POST_SELECT.replace("FROM posts p", "FROM inserted p")}
            """,
            post_id,
            uuid.UUID(user_id),
            title,
            content,
            cat_uuid,
            keywords,
            allow_comments,
        )
        await _increment_daily_post_count(user_id)
        logger.info("Post created", extra={"post_id": str(post_id), "user_id": user_id})
        return _row_to_post(dict(row))


async def get_post_by_id(post_id: uuid.UUID) -> dict | None:
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            f"{_POST_SELECT} WHERE p.id = $1 AND p.is_deleted = false",
            post_id,
        )
        return _row_to_post(dict(row)) if row else None


async def update_post(
    post_id: uuid.UUID,
    user_id: str,
    title: str | None = None,
    content: str | None = None,
    category_id: str | None = None,
    keywords: list[str] | None = None,
    allow_comments: bool | None = None,
    expected_version: int = 1,
) -> dict | None:
    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            # Fetch current post with lock
            current = await conn.fetchrow(
                "SELECT * FROM posts WHERE id = $1 AND is_deleted = false FOR UPDATE",
                post_id,
            )
            if not current:
                return None

            if str(current["user_id"]) != user_id:
                raise PermissionError("You can only edit your own posts.")

            if current["version"] != expected_version:
                raise ValueError("Version conflict. The post was modified by another request.")

            # Save history before update
            await conn.execute(
                """
                INSERT INTO post_history (id, post_id, version, title, content)
                VALUES ($1, $2, $3, $4, $5)
                """,
                uuid.uuid4(),
                post_id,
                current["version"],
                current["title"],
                current["content"],
            )

            # Build update
            new_title = title if title is not None else current["title"]
            new_content = content if content is not None else current["content"]
            new_category_id = (
                uuid.UUID(category_id)
                if category_id is not None
                else current["category_id"]
            )
            new_keywords = keywords if keywords is not None else current["keywords"]
            new_allow = (
                allow_comments if allow_comments is not None else current["allow_comments"]
            )

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
                new_title,
                new_content,
                new_category_id,
                new_keywords,
                new_allow,
                post_id,
            )
            logger.info("Post updated", extra={"post_id": str(post_id), "version": expected_version + 1})
            return _row_to_post(dict(row))


async def soft_delete_post(post_id: uuid.UUID, user_id: str, is_admin: bool = False) -> bool:
    pool = get_pool()
    async with pool.acquire() as conn:
        if is_admin:
            result = await conn.execute(
                "UPDATE posts SET is_deleted = true, updated_at = NOW() WHERE id = $1 AND is_deleted = false",
                post_id,
            )
        else:
            result = await conn.execute(
                "UPDATE posts SET is_deleted = true, updated_at = NOW() WHERE id = $1 AND user_id = $2 AND is_deleted = false",
                post_id,
                uuid.UUID(user_id),
            )
        deleted = result == "UPDATE 1"
        if deleted:
            logger.info("Post deleted", extra={"post_id": str(post_id)})
        return deleted


async def get_post_history(post_id: uuid.UUID) -> list[dict]:
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM post_history WHERE post_id = $1 ORDER BY version DESC",
            post_id,
        )
        return [
            {
                "id": str(r["id"]),
                "version": r["version"],
                "title": r["title"],
                "content": r["content"],
                "edited_at": r["edited_at"].isoformat(),
            }
            for r in rows
        ]


async def list_posts(
    page: int = 1,
    page_size: int = 20,
    category_id: str | None = None,
) -> tuple[list[dict], int, int]:
    """Returns (posts, total, total_pages)."""
    pool = get_pool()
    offset = (page - 1) * page_size

    where = "WHERE p.is_deleted = false"
    params: list = []
    idx = 1

    if category_id:
        where += f" AND p.category_id = ${idx}"
        params.append(uuid.UUID(category_id))
        idx += 1

    async with pool.acquire() as conn:
        total = await conn.fetchval(
            f"SELECT COUNT(*) FROM posts p {where}",
            *params,
        )
        total_pages = max(1, math.ceil(total / page_size))

        params.extend([page_size, offset])
        rows = await conn.fetch(
            f"{_POST_SELECT} {where} ORDER BY p.created_at DESC LIMIT ${idx} OFFSET ${idx + 1}",
            *params,
        )
        return [_row_to_post(dict(r)) for r in rows], total, total_pages


async def search_posts(
    keyword: str | None = None,
    category_id: str | None = None,
    keywords_filter: list[str] | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    logic: str = "AND",
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[dict], int, int]:
    """Full-text search with compound filters."""
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
        params.append(uuid.UUID(category_id))
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

    async with pool.acquire() as conn:
        total = await conn.fetchval(
            f"SELECT COUNT(*) FROM posts p {where}",
            *params,
        )
        total_pages = max(1, math.ceil(total / page_size))

        params.extend([page_size, offset])
        rows = await conn.fetch(
            f"{_POST_SELECT} {where} ORDER BY p.created_at DESC LIMIT ${idx} OFFSET ${idx + 1}",
            *params,
        )
        return [_row_to_post(dict(r)) for r in rows], total, total_pages

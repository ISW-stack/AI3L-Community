import uuid
from datetime import datetime, timezone

from loguru import logger

from app.converters.post_converter import row_to_history, row_to_post
from app.core.constants import MAX_POSTS_PER_DAY
from app.core.database import get_pool
from app.core.errors import RateLimitError
from app.core.event_bus import emit
from app.core.redis import get_redis
from app.repositories import post_repo


async def _atomic_check_and_increment_post_limit(user_id: str) -> bool:
    """Atomically increment daily post count and check limit. Returns True if within limit."""
    redis = get_redis()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    key = f"post_limit:{user_id}:{today}"
    count = await redis.incr(key)
    if count == 1:
        await redis.expire(key, 86400)
    if count > MAX_POSTS_PER_DAY:
        await redis.decr(key)
        return False
    return True


async def _rollback_daily_post_count(user_id: str) -> None:
    """Decrement counter if post creation fails after the atomic increment."""
    redis = get_redis()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    key = f"post_limit:{user_id}:{today}"
    await redis.decr(key)


async def create_post(
    user_id: str,
    title: str,
    content: str,
    category_id: str | None = None,
    sig_id: str | None = None,
    keywords: list[str] | None = None,
    allow_comments: bool = True,
) -> dict:
    if not await _atomic_check_and_increment_post_limit(user_id):
        raise RateLimitError(f"Daily post limit ({MAX_POSTS_PER_DAY}) exceeded.")

    post_id = uuid.uuid4()
    cat_uuid = uuid.UUID(category_id) if category_id else None
    sig_uuid = uuid.UUID(sig_id) if sig_id else None

    try:
        row = await post_repo.insert(
            post_id,
            uuid.UUID(user_id),
            title,
            content,
            cat_uuid,
            sig_uuid,
            keywords,
            allow_comments,
        )
    except Exception:
        await _rollback_daily_post_count(user_id)
        raise
    logger.info("Post created", extra={"post_id": str(post_id), "user_id": user_id})

    if sig_id:
        await emit(
            "post.created_in_sig",
            sig_id=sig_id,
            post_id=str(post_id),
            author_id=user_id,
            post_title=title,
        )

    return row_to_post(row)


async def get_post_by_id(post_id: uuid.UUID, increment_view: bool = False) -> dict | None:
    row = await post_repo.find_by_id(post_id)
    if not row:
        return None
    if increment_view:
        await post_repo.increment_view_count(post_id)
    return row_to_post(row)


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
            current = await post_repo.find_for_update(post_id, conn)
            if not current:
                return None

            if str(current["user_id"]) != user_id:
                raise PermissionError("You can only edit your own posts.")

            if current["version"] != expected_version:
                raise ValueError("Version conflict. The post was modified by another request.")

            # Save history before update
            await post_repo.insert_history(
                uuid.uuid4(),
                post_id,
                current["version"],
                current["title"],
                current["content"],
                conn,
            )

            new_title = title if title is not None else current["title"]
            new_content = content if content is not None else current["content"]
            new_category_id = (
                uuid.UUID(category_id) if category_id is not None else current["category_id"]
            )
            new_keywords = keywords if keywords is not None else current["keywords"]
            new_allow = allow_comments if allow_comments is not None else current["allow_comments"]

            row = await post_repo.update_in_transaction(
                conn, post_id, new_title, new_content, new_category_id, new_keywords, new_allow
            )
            logger.info(
                "Post updated", extra={"post_id": str(post_id), "version": expected_version + 1}
            )
            return row_to_post(row)


async def soft_delete_post(post_id: uuid.UUID, user_id: str, is_admin: bool = False) -> bool:
    post_owner_id: str | None = None
    if is_admin:
        post_owner_id = await post_repo.find_owner_id(post_id)
        deleted = await post_repo.soft_delete(post_id)
    else:
        deleted = await post_repo.soft_delete(post_id, uuid.UUID(user_id))

    if deleted:
        logger.info("Post deleted", extra={"post_id": str(post_id)})

    # Notify post owner when admin deletes their post
    if deleted and is_admin and post_owner_id and post_owner_id != user_id:
        await emit(
            "post.deleted",
            post_owner_id=post_owner_id,
            admin_user_id=user_id,
            post_id=str(post_id),
        )

    return deleted


async def get_post_history(post_id: uuid.UUID) -> list[dict]:
    rows = await post_repo.find_history(post_id)
    return [row_to_history(r) for r in rows]


async def list_posts(
    page: int = 1,
    page_size: int = 20,
    category_id: str | None = None,
    sig_id: str | None = None,
    author_id: str | None = None,
    sort: str = "newest",
) -> tuple[list[dict], int, int]:
    """Returns (posts, total, total_pages)."""
    cat_uuid = uuid.UUID(category_id) if category_id else None
    sig_uuid = uuid.UUID(sig_id) if sig_id else None
    author_uuid = uuid.UUID(author_id) if author_id else None
    rows, total, total_pages = await post_repo.find_many(
        page, page_size, cat_uuid, sig_uuid, author_uuid, sort
    )
    return [row_to_post(r) for r in rows], total, total_pages


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
    cat_uuid = uuid.UUID(category_id) if category_id else None
    rows, total, total_pages = await post_repo.search(
        keyword, cat_uuid, keywords_filter, date_from, date_to, logic, page, page_size
    )
    return [row_to_post(r) for r in rows], total, total_pages


async def pin_post(post_id: uuid.UUID, is_pinned: bool) -> bool:
    return await post_repo.update_pin_status(post_id, is_pinned)


async def get_trending_posts(limit: int = 5, days: int = 7) -> list[dict]:
    rows = await post_repo.find_trending(limit, days)
    return [row_to_post(r) for r in rows]

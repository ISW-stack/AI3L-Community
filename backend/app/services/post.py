import asyncio
import re
import uuid
from datetime import date, datetime, timezone

import asyncpg
from loguru import logger

from app.converters.post_converter import async_row_to_post, row_to_history
from app.core.blacklist import get_blocked_user_ids
from app.core.constants import MAX_POSTS_PER_DAY, POST_VIEW_DEDUP_TTL
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
    post_type: str = "post",
) -> dict:
    if not await _atomic_check_and_increment_post_limit(user_id):
        raise RateLimitError(f"Daily post limit ({MAX_POSTS_PER_DAY}) exceeded.")

    post_id = uuid.uuid4()
    cat_uuid = uuid.UUID(category_id) if category_id else None
    sig_uuid = uuid.UUID(sig_id) if sig_id else None

    if sig_uuid:
        from app.repositories import sig_repo

        member_role = await sig_repo.get_member_role(sig_uuid, uuid.UUID(user_id))
        if not member_role:
            await _rollback_daily_post_count(user_id)
            raise PermissionError("You must be a member of this SIG to post in it.")

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
            post_type=post_type,
        )
    except asyncpg.exceptions.ForeignKeyViolationError:
        await _rollback_daily_post_count(user_id)
        raise ValueError("Category not found or has been deleted.")
    except Exception:
        await _rollback_daily_post_count(user_id)
        raise
    logger.info("Post created", extra={"post_id": str(post_id), "user_id": user_id})

    if sig_id:
        try:
            await emit(
                "post.created_in_sig",
                sig_id=sig_id,
                post_id=str(post_id),
                author_id=user_id,
                post_title=title,
            )
        except Exception as e:
            logger.warning(
                "Failed to emit post.created_in_sig event",
                extra={"error": str(e), "post_id": str(post_id)},
            )

    # Sync citations from content
    try:
        from app.services.citation import sync_post_citations

        await sync_post_citations(post_id, content, user_id)
    except Exception as e:
        logger.warning(
            "Failed to sync citations after post creation",
            extra={"error": str(e), "post_id": str(post_id)},
        )

    # Emit question.created event for Q&A auto-assignment
    if post_type == "question":
        try:
            await emit(
                "question.created",
                post_id=str(post_id),
                author_id=user_id,
                keywords=keywords or [],
            )
        except Exception as e:
            logger.warning(
                "Failed to emit question.created event",
                extra={"error": str(e), "post_id": str(post_id)},
            )

    return await async_row_to_post(row)


async def get_post_by_id(
    post_id: uuid.UUID,
    increment_view: bool = False,
    viewer_id: str | None = None,
) -> dict | None:
    row = await post_repo.find_by_id(post_id)
    if not row:
        return None

    # Block check: if the viewer has blocked the author (or vice versa), treat as invisible
    if viewer_id:
        redis = get_redis()
        pool = get_pool()
        blocked_ids = await get_blocked_user_ids(redis, viewer_id, pool=pool)
        if str(row["user_id"]) in blocked_ids:
            return None

    if increment_view and viewer_id:
        redis = get_redis()
        view_key = f"viewed:{post_id}:{viewer_id}"
        # Only increment if not viewed in dedup window (24h)
        is_new = await redis.set(view_key, "1", ex=POST_VIEW_DEDUP_TTL, nx=True)
        if is_new:
            await post_repo.increment_view_count(post_id)
    elif increment_view:
        # Fallback: no viewer_id, always increment (backward compat)
        await post_repo.increment_view_count(post_id)
    return await async_row_to_post(row)


async def update_post(
    post_id: uuid.UUID,
    user_id: str,
    title: str | None = None,
    content: str | None = None,
    category_id: str | None = None,
    keywords: list[str] | None = None,
    allow_comments: bool | None = None,
    expected_version: int = 1,
    caller_role: str = "MEMBER",
) -> dict | None:
    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            current = await post_repo.find_for_update(post_id, conn)
            if not current:
                return None

            is_admin = caller_role in ("ADMIN", "SUPER_ADMIN")
            is_owner = str(current["user_id"]) == user_id

            # Check if user is an accepted co-author
            from app.repositories import co_author_repo

            is_co_author = await co_author_repo.is_accepted_co_author(
                conn, post_id, uuid.UUID(user_id)
            )
            if not is_owner and not is_admin and not is_co_author:
                raise PermissionError("Not authorized to edit this post")

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

    # Sync citations if content changed (outside transaction for event emission)
    if content is not None:
        try:
            from app.services.citation import sync_post_citations

            await sync_post_citations(post_id, content, user_id)
        except Exception as e:
            logger.warning(
                "Failed to sync citations after post update",
                extra={"error": str(e), "post_id": str(post_id)},
            )

    return await async_row_to_post(row)


async def _cleanup_post_files(post_id: uuid.UUID, user_id: str) -> None:
    """Best-effort cleanup of editor files embedded in a deleted post."""
    try:
        from app.core.async_storage import delete_file, get_file_size
        from app.repositories import user_repo

        post_content = await post_repo.find_content_by_id(post_id)
        if not post_content:
            return
        # Extract editor file keys from content HTML
        pattern = r'/api/v1/files/content/(editor/[^"\'<>\s]+)'
        keys = re.findall(pattern, post_content)
        if not keys:
            return
        total_freed = 0
        succeeded = 0
        failed_keys: list[str] = []
        for key in keys:
            try:
                size = await get_file_size(key)
                if size and size > 0:
                    await delete_file(key)
                    total_freed += size
                succeeded += 1
            except Exception:
                failed_keys.append(key)
                logger.warning("Failed to delete file during post cleanup", extra={"key": key})
        if failed_keys:
            logger.warning(
                "Post file cleanup summary",
                extra={
                    "post_id": str(post_id),
                    "succeeded": succeeded,
                    "failed": len(failed_keys),
                    "failed_keys": failed_keys,
                },
            )
        if total_freed > 0:
            await user_repo.decrement_storage_used(uuid.UUID(user_id), total_freed)
    except Exception:
        logger.warning("Post file cleanup failed", extra={"post_id": str(post_id)})


async def soft_delete_post(post_id: uuid.UUID, user_id: str, is_admin: bool = False) -> bool:
    post_owner_id: str | None = None
    if is_admin:
        post_owner_id = await post_repo.find_owner_id(post_id)
        deleted = await post_repo.soft_delete(post_id)
    else:
        deleted = await post_repo.soft_delete(post_id, uuid.UUID(user_id))

    if deleted:
        logger.info("Post deleted", extra={"post_id": str(post_id)})
        # Best-effort cleanup of embedded files
        actual_user = post_owner_id if is_admin and post_owner_id else user_id
        try:
            await _cleanup_post_files(post_id, actual_user)
        except Exception:
            logger.warning("Post file cleanup failed", extra={"post_id": str(post_id)})

        # Cleanup citations referencing this post (both directions)
        try:
            pool = get_pool()
            async with pool.acquire() as conn:
                await conn.execute(
                    "DELETE FROM post_citations WHERE citing_post_id = $1 OR cited_post_id = $1",
                    post_id,
                )
        except Exception:
            logger.warning("Post citation cleanup failed", extra={"post_id": str(post_id)})

    # Notify post owner when admin deletes their post
    if deleted and is_admin and post_owner_id and post_owner_id != user_id:
        await emit(
            "post.deleted",
            post_owner_id=post_owner_id,
            admin_user_id=user_id,
            post_id=str(post_id),
        )

    return deleted


async def get_post_history(post_id: uuid.UUID) -> tuple[list[dict], int]:
    """Return (history_items, total_count)."""
    rows, total = await post_repo.find_history(post_id)
    return [row_to_history(r) for r in rows], total


async def _get_exclude_user_ids(viewer_id: str | None) -> list[uuid.UUID] | None:
    """Get list of blocked user UUIDs for the viewer, or None if no viewer/blocks."""
    if not viewer_id:
        return None
    redis = get_redis()
    pool = get_pool()
    blocked_ids = await get_blocked_user_ids(redis, viewer_id, pool=pool)
    if not blocked_ids:
        return None
    return [uuid.UUID(uid) for uid in blocked_ids]


async def list_posts(
    page: int = 1,
    page_size: int = 20,
    category_id: str | None = None,
    sig_id: str | None = None,
    author_id: str | None = None,
    sort: str = "newest",
    cursor: str | None = None,
    post_type: str | None = None,
    viewer_id: str | None = None,
) -> dict:
    """Returns a dict with posts and pagination metadata.

    OFFSET mode (cursor=None): keys ``posts``, ``total``, ``total_pages``.
    Cursor mode: keys ``posts``, ``next_cursor``, ``has_more``.
    """
    cat_uuid = uuid.UUID(category_id) if category_id else None
    sig_uuid = uuid.UUID(sig_id) if sig_id else None
    author_uuid = uuid.UUID(author_id) if author_id else None
    exclude = await _get_exclude_user_ids(viewer_id)
    result = await post_repo.find_many(
        page,
        page_size,
        cat_uuid,
        sig_uuid,
        author_uuid,
        sort,
        cursor,
        post_type=post_type,
        exclude_user_ids=exclude,
    )
    result["posts"] = list(await asyncio.gather(*[async_row_to_post(r) for r in result["posts"]]))
    return result


async def search_posts(
    keyword: str | None = None,
    category_id: str | None = None,
    keywords_filter: list[str] | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    logic: str = "AND",
    page: int = 1,
    page_size: int = 20,
    sort: str = "newest",
    post_type: str | None = None,
    viewer_id: str | None = None,
) -> tuple[list[dict], int, int]:
    """Full-text search with compound filters."""
    cat_uuid = uuid.UUID(category_id) if category_id else None
    exclude = await _get_exclude_user_ids(viewer_id)
    rows, total, total_pages = await post_repo.search(
        keyword,
        cat_uuid,
        keywords_filter,
        date_from,
        date_to,
        logic,
        page,
        page_size,
        sort,
        post_type=post_type,
        exclude_user_ids=exclude,
    )
    posts = list(await asyncio.gather(*[async_row_to_post(r) for r in rows]))
    return posts, total, total_pages


async def pin_post(post_id: uuid.UUID, is_pinned: bool) -> bool:
    return await post_repo.update_pin_status(post_id, is_pinned)


async def get_trending_posts(
    limit: int = 5, days: int = 7, viewer_id: str | None = None
) -> list[dict]:
    exclude = await _get_exclude_user_ids(viewer_id)
    rows = await post_repo.find_trending(limit, days, exclude_user_ids=exclude)
    return list(await asyncio.gather(*[async_row_to_post(r) for r in rows]))


async def toggle_post_reaction(post_id: uuid.UUID, user_id: str, reaction: str) -> dict | None:
    """Toggle a reaction on a post. Returns updated post dict or None."""
    row = await post_repo.toggle_reaction(post_id, user_id, reaction)
    if not row:
        return None
    return await async_row_to_post(row)


async def bulk_soft_delete(post_ids: list[uuid.UUID]) -> int:
    """Soft-delete multiple posts in a single transaction.

    Also cleans up related citations, co-authors, and comments.
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            # Cascade cleanup before soft-deleting posts
            await conn.execute(
                "DELETE FROM post_citations "
                "WHERE citing_post_id = ANY($1::uuid[]) OR cited_post_id = ANY($1::uuid[])",
                post_ids,
            )
            await conn.execute(
                "DELETE FROM post_co_authors WHERE post_id = ANY($1::uuid[])",
                post_ids,
            )
            await conn.execute(
                "UPDATE comments SET is_deleted = true, updated_at = NOW() "
                "WHERE post_id = ANY($1::uuid[]) AND is_deleted = false",
                post_ids,
            )
            count = await post_repo.bulk_soft_delete(post_ids, conn)
    return count

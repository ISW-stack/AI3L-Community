"""Celery task: Orphan editor file cleanup.

Deletes files under the editor/ prefix in S3-compatible storage that are:
1. Not referenced in any post content, comment content, or form description.
2. Older than 7 days (to avoid deleting in-progress draft files).

Also removes their corresponding file_scans records.
"""

import asyncio
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Iterator

from loguru import logger

from app.celery_app import celery
from app.core.config import settings
from app.core.database import get_pool, init_db_pool
from app.core.redis import get_redis, init_redis
from app.tasks.async_runner import run_async as _run_async

# Matches /api/v1/files/content/editor/<user_id>/<filename>
_FILE_KEY_RE = re.compile(r"/api/v1/files/content/(editor/[^\s\"'<>]+)")

_ORPHAN_MAX_AGE_DAYS = 7
_ORPHAN_BATCH_SIZE = 1000


async def _ensure_pool() -> None:
    try:
        get_pool()
    except RuntimeError:
        await init_db_pool(settings.DATABASE_URL)


async def _ensure_redis() -> None:
    try:
        get_redis()
    except RuntimeError:
        await init_redis(settings.REDIS_URL)


async def _get_referenced_keys() -> set[str]:
    """Return all editor file keys referenced in posts, comments, or form descriptions."""
    await _ensure_pool()
    pool = get_pool()
    keys: set[str] = set()
    _BATCH_SIZE = 500

    async with pool.acquire() as conn:
        # Process posts in batches
        offset = 0
        while True:
            rows = await conn.fetch(
                "SELECT content AS html FROM posts "
                "WHERE is_deleted = FALSE AND content IS NOT NULL AND content <> '' "
                "ORDER BY id LIMIT $1 OFFSET $2",
                _BATCH_SIZE,
                offset,
            )
            if not rows:
                break
            for row in rows:
                html = row["html"] or ""
                for match in _FILE_KEY_RE.finditer(html):
                    keys.add(match.group(1))
            if len(rows) < _BATCH_SIZE:
                break
            offset += _BATCH_SIZE

        # Process comments in batches
        offset = 0
        while True:
            rows = await conn.fetch(
                "SELECT content AS html FROM comments "
                "WHERE is_deleted = FALSE AND content IS NOT NULL AND content <> '' "
                "ORDER BY id LIMIT $1 OFFSET $2",
                _BATCH_SIZE,
                offset,
            )
            if not rows:
                break
            for row in rows:
                html = row["html"] or ""
                for match in _FILE_KEY_RE.finditer(html):
                    keys.add(match.group(1))
            if len(rows) < _BATCH_SIZE:
                break
            offset += _BATCH_SIZE

        # Process forms in batches
        offset = 0
        while True:
            rows = await conn.fetch(
                "SELECT description AS html FROM forms "
                "WHERE is_deleted = FALSE AND description IS NOT NULL AND description <> '' "
                "ORDER BY id LIMIT $1 OFFSET $2",
                _BATCH_SIZE,
                offset,
            )
            if not rows:
                break
            for row in rows:
                html = row["html"] or ""
                for match in _FILE_KEY_RE.finditer(html):
                    keys.add(match.group(1))
            if len(rows) < _BATCH_SIZE:
                break
            offset += _BATCH_SIZE

        # Process post_history in batches
        offset = 0
        while True:
            rows = await conn.fetch(
                "SELECT content AS html FROM post_history "
                "WHERE content IS NOT NULL AND content <> '' "
                "ORDER BY id LIMIT $1 OFFSET $2",
                _BATCH_SIZE,
                offset,
            )
            if not rows:
                break
            for row in rows:
                html = row["html"] or ""
                for match in _FILE_KEY_RE.finditer(html):
                    keys.add(match.group(1))
            if len(rows) < _BATCH_SIZE:
                break
            offset += _BATCH_SIZE

    return keys


def _iter_editor_files() -> Iterator[tuple[str, Any]]:
    """Yield (key, last_modified) for objects under editor/ prefix without buffering all."""
    from app.core.storage import get_storage

    client = get_storage()
    bucket = settings.S3_BUCKET_NAME
    paginator = client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix="editor/"):
        for obj in page.get("Contents", []):
            yield (obj["Key"], obj["LastModified"])


async def _decrement_owner_storage(storage_key: str, file_size: int) -> None:
    """Parse user_id from storage key and decrement their storage counter.

    Key pattern: editor/{user_id}/{filename}
    """
    import uuid as _uuid

    from app.repositories import user_repo

    parts = storage_key.split("/")
    if len(parts) >= 2:
        try:
            owner_uuid = _uuid.UUID(parts[1])
            await user_repo.increment_storage_used(owner_uuid, -file_size)
            logger.info(
                "Decremented storage for user after orphan file deletion",
                extra={"user_id": parts[1], "key": storage_key, "size": file_size},
            )
        except (ValueError, Exception) as e:
            logger.warning(
                "Failed to decrement storage after orphan file deletion",
                extra={"key": storage_key, "error": str(e)},
            )


async def _delete_orphans(orphan_keys: list[str]) -> int:
    """Delete orphan files from MinIO and remove their file_scans records."""
    from app.core.async_storage import delete_file, get_file_size
    from app.repositories import file_scan_repo

    await _ensure_pool()
    deleted = 0
    for key in orphan_keys:
        try:
            file_size = await get_file_size(key)
            await file_scan_repo.delete_by_key(key)
            if file_size > 0:
                await _decrement_owner_storage(key, file_size)
            await delete_file(key)
            deleted += 1
        except Exception:
            logger.warning("Failed to delete orphan file key=%s", key, exc_info=True)
    return deleted


@celery.task(name="sync_guest_counter", bind=True, max_retries=1)
def sync_guest_counter_task(self: Any) -> dict[str, Any]:
    """Periodic task: reconcile guest counter with actual session keys in Redis."""

    async def _run() -> dict:
        from app.services.auth import sync_guest_counter

        await _ensure_redis()
        await sync_guest_counter()
        return {"status": "synced"}

    result: dict[str, Any] = _run_async(_run())
    logger.info("Guest counter sync complete: %s", result)
    return result


@celery.task(name="cleanup_old_file_scans", bind=True, max_retries=1)
def cleanup_old_file_scans(self: Any, days: int = 30) -> dict[str, Any]:
    """Daily task: remove completed file_scans records older than *days*."""

    async def _run() -> dict:
        await _ensure_pool()
        from app.repositories import file_scan_repo

        deleted = await file_scan_repo.delete_old_completed(days)
        return {"deleted": deleted, "retention_days": days}

    result: dict[str, Any] = _run_async(_run())
    logger.info("Old file scans cleanup complete: %s", result)
    return result


@celery.task(name="cleanup_old_audit_logs", bind=True, max_retries=1)
def cleanup_old_audit_logs(self: Any, days: int = 90) -> dict[str, Any]:
    """Daily task: delete audit log entries older than *days* days."""

    async def _run() -> dict:
        await _ensure_pool()
        from app.repositories import audit_repo

        deleted = await audit_repo.delete_old_logs(days)
        return {"deleted": deleted, "retention_days": days}

    result: dict[str, Any] = _run_async(_run())
    logger.info("Old audit logs cleanup complete: %s", result)
    return result


@celery.task(name="cleanup_old_read_notifications", bind=True, max_retries=1)
def cleanup_old_read_notifications(self: Any, days: int = 90) -> dict[str, Any]:
    """Weekly task: delete read notifications older than *days* days."""

    async def _run() -> dict:
        await _ensure_pool()
        from app.repositories import notification_repo

        deleted = await notification_repo.delete_old_read_notifications(days)
        return {"deleted": deleted, "retention_days": days}

    result: dict[str, Any] = _run_async(_run())
    logger.info("Old read notifications cleanup complete: %s", result)
    return result


@celery.task(name="cleanup_orphan_files", bind=True, max_retries=1)
def cleanup_orphan_files(self: Any) -> dict[str, Any]:
    """Weekly task: delete unreferenced editor files older than 7 days."""

    async def _run() -> dict:
        referenced = await _get_referenced_keys()
        logger.info("Orphan cleanup: %d referenced file keys found", len(referenced))

        cutoff = datetime.now(timezone.utc) - timedelta(days=_ORPHAN_MAX_AGE_DAYS)

        def _find_orphans() -> tuple[list[str], int]:
            """Process S3 files in batches to avoid loading all keys into memory."""
            orphan_keys: list[str] = []
            total = 0
            batch: list[tuple[str, Any]] = []
            for item in _iter_editor_files():
                batch.append(item)
                total += 1
                if len(batch) >= _ORPHAN_BATCH_SIZE:
                    orphan_keys.extend(
                        key
                        for key, modified in batch
                        if key not in referenced and modified < cutoff
                    )
                    batch = []
            if batch:
                orphan_keys.extend(
                    key for key, modified in batch if key not in referenced and modified < cutoff
                )
            return orphan_keys, total

        loop = asyncio.get_running_loop()
        orphans, total_files = await loop.run_in_executor(None, _find_orphans)

        logger.info(
            "Orphan cleanup: %d total files, %d orphans queued for deletion",
            total_files,
            len(orphans),
        )

        deleted = await _delete_orphans(orphans)
        return {
            "total_files": total_files,
            "orphans_found": len(orphans),
            "deleted": deleted,
        }

    result: dict[str, Any] = _run_async(_run())
    logger.info("Orphan file cleanup complete: %s", result)
    return result

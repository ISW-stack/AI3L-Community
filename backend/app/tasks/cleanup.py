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
from app.core.database import get_pool
from app.tasks.async_runner import run_async as _run_async
from app.tasks.utils import decrement_owner_storage as _decrement_owner_storage
from app.tasks.utils import ensure_pool as _ensure_pool
from app.tasks.utils import ensure_redis as _ensure_redis

# Matches /api/v1/files/content/editor/<user_id>/<filename>
_FILE_KEY_RE = re.compile(r"/api/v1/files/content/(editor/[^\s\"'<>]+)")

_ORPHAN_MAX_AGE_DAYS = 7
_ORPHAN_BATCH_SIZE = 1000


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


async def _delete_orphans(orphan_keys: list[str]) -> int:
    """Delete orphan files from MinIO and remove their file_scans records.

    Order of operations (M-17): decrement quota first (recoverable), then
    delete from MinIO. If MinIO delete fails, re-increment quota to avoid drift.
    """
    from app.core.async_storage import delete_file, get_file_size
    from app.repositories import file_scan_repo
    from app.tasks.utils import decrement_owner_storage

    await _ensure_pool()
    deleted = 0
    for key in orphan_keys:
        try:
            file_size = await get_file_size(key)
            await file_scan_repo.delete_by_key(key)
            # Decrement quota first (can be rolled back)
            quota_decremented = False
            if file_size > 0:
                await decrement_owner_storage(key, file_size)
                quota_decremented = True
            try:
                await delete_file(key)
            except Exception:
                # MinIO delete failed — re-increment quota to avoid drift
                if quota_decremented:
                    try:
                        await _reincrement_owner_storage(key, file_size)
                    except Exception:
                        logger.error(
                            "Failed to re-increment quota after MinIO delete failure",
                            extra={"key": key},
                            exc_info=True,
                        )
                raise
            deleted += 1
        except Exception:
            logger.warning("Failed to delete orphan file key=%s", key, exc_info=True)
    return deleted


async def _reincrement_owner_storage(storage_key: str, file_size: int) -> None:
    """Re-increment storage quota when MinIO deletion fails after quota was decremented."""
    import uuid as _uuid

    from app.repositories import user_repo

    parts = storage_key.split("/")
    for part in parts[1:]:
        try:
            owner_uuid = _uuid.UUID(part)
            await user_repo.increment_storage_used(owner_uuid, file_size)
            logger.info(
                "Re-incremented storage after MinIO delete failure",
                extra={"key": storage_key, "size": file_size},
            )
            return
        except ValueError:
            continue


@celery.task(name="sync_guest_counter", bind=True, max_retries=2, default_retry_delay=30)
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


@celery.task(name="cleanup_old_file_scans", bind=True, max_retries=2, default_retry_delay=30)
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


@celery.task(name="cleanup_old_audit_logs", bind=True, max_retries=2, default_retry_delay=30)
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


@celery.task(name="cleanup_old_read_notifications", bind=True, max_retries=2, default_retry_delay=30)
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


@celery.task(name="cleanup_orphan_files", bind=True, max_retries=2, default_retry_delay=30, soft_time_limit=3500, time_limit=3600)
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


@celery.task(name="cleanup_dm_orphan_quotas", bind=True, max_retries=2, default_retry_delay=30)
def cleanup_dm_orphan_quotas(self: Any) -> dict[str, Any]:
    """Weekly: find DM messages with no attachment_key but positive attachment_size (orphaned quota)
    and refund the storage."""

    async def _run() -> dict[str, Any]:
        pool = await _ensure_pool()
        if pool is None:
            pool = get_pool()

        async with pool.acquire() as conn:
            # Find messages with attachment_size > 0 but NULL attachment_key
            # These indicate failed uploads where quota wasn't refunded
            rows = await conn.fetch(
                "SELECT id, sender_id, attachment_size FROM dm_messages "
                "WHERE attachment_key IS NULL AND attachment_size IS NOT NULL "
                "AND attachment_size > 0 AND created_at < NOW() - INTERVAL '1 day' "
                "LIMIT 100"
            )
            refunded = 0
            for row in rows:
                try:
                    async with conn.transaction():
                        await conn.execute(
                            "UPDATE users SET storage_used_bytes = GREATEST(0, storage_used_bytes - $1) "
                            "WHERE id = $2",
                            row["attachment_size"],
                            row["sender_id"],
                        )
                        await conn.execute(
                            "UPDATE dm_messages SET attachment_size = NULL WHERE id = $1",
                            row["id"],
                        )
                    refunded += 1
                except Exception:
                    logger.warning("Failed to refund orphaned DM quota", exc_info=True)

        return {"refunded": refunded, "total_found": len(rows)}

    result: dict[str, Any] = _run_async(_run())
    logger.info("DM orphan quota cleanup: %s", result)
    return result


@celery.task(name="cleanup_empty_dm_conversations", bind=True, max_retries=2, default_retry_delay=30)
def cleanup_empty_dm_conversations(self: Any) -> dict[str, Any]:
    """Weekly: remove conversations with zero messages (orphaned from failed sends)."""

    async def _run() -> dict[str, Any]:
        pool = await _ensure_pool()
        if pool is None:
            pool = get_pool()

        async with pool.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM conversations c "
                "WHERE NOT EXISTS (SELECT 1 FROM dm_messages m WHERE m.conversation_id = c.id) "
                "AND c.created_at < NOW() - INTERVAL '1 hour'"
            )
            count = int(result.split()[-1]) if result else 0
        return {"deleted": count}

    result: dict[str, Any] = _run_async(_run())
    logger.info("Empty DM conversation cleanup: %s", result)
    return result

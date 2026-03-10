"""Celery task: Orphan editor file cleanup.

Deletes files under the editor/ prefix in MinIO that are:
1. Not referenced in any post content or form description.
2. Older than 7 days (to avoid deleting in-progress draft files).

Also removes their corresponding file_scans records.
"""

import asyncio
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from typing import Any

from loguru import logger

from app.celery_app import celery
from app.core.config import settings
from app.core.database import get_pool, init_db_pool

# Matches /api/v1/files/content/editor/<user_id>/<filename>
_FILE_KEY_RE = re.compile(r"/api/v1/files/content/(editor/[^\s\"'<>]+)")

_ORPHAN_MAX_AGE_DAYS = 7


def _run_async(coro: Any) -> Any:
    """Run an async coroutine from a sync Celery task context."""
    with ThreadPoolExecutor(1) as pool:
        return pool.submit(asyncio.run, coro).result()


async def _ensure_pool() -> None:
    try:
        get_pool()
    except RuntimeError:
        await init_db_pool(settings.DATABASE_URL)


async def _get_referenced_keys() -> set[str]:
    """Return all editor file keys referenced in active posts or form descriptions."""
    await _ensure_pool()
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT content AS html FROM posts
            WHERE is_deleted = FALSE AND content IS NOT NULL AND content <> ''
            UNION ALL
            SELECT description AS html FROM forms
            WHERE is_deleted = FALSE AND description IS NOT NULL AND description <> ''
            """)
    keys: set[str] = set()
    for row in rows:
        html = row["html"] or ""
        for match in _FILE_KEY_RE.finditer(html):
            keys.add(match.group(1))
    return keys


def _list_editor_files() -> list[tuple[str, datetime]]:
    """List all objects under the editor/ prefix. Returns [(key, last_modified)]."""
    from app.core.storage import get_storage

    client = get_storage()
    bucket = settings.MINIO_BUCKET_NAME
    files: list[tuple[str, datetime]] = []
    paginator = client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix="editor/"):
        for obj in page.get("Contents", []):
            files.append((obj["Key"], obj["LastModified"]))
    return files


async def _delete_orphans(orphan_keys: list[str]) -> int:
    """Delete orphan files from MinIO and remove their file_scans records."""
    from app.core.async_storage import delete_file
    from app.repositories import file_scan_repo

    deleted = 0
    for key in orphan_keys:
        try:
            await delete_file(key)
            await file_scan_repo.delete_by_key(key)
            deleted += 1
        except Exception:
            logger.warning("Failed to delete orphan file key=%s", key, exc_info=True)
    return deleted


@celery.task(name="cleanup_orphan_files", bind=True, max_retries=1)
def cleanup_orphan_files(self: Any) -> dict[str, Any]:
    """Weekly task: delete unreferenced editor files older than 7 days."""

    async def _run() -> dict:
        referenced = await _get_referenced_keys()
        logger.info("Orphan cleanup: %d referenced file keys found", len(referenced))

        loop = asyncio.get_running_loop()
        all_files = await loop.run_in_executor(None, _list_editor_files)

        cutoff = datetime.now(timezone.utc) - timedelta(days=_ORPHAN_MAX_AGE_DAYS)
        orphans = [
            key for key, modified in all_files if key not in referenced and modified < cutoff
        ]

        logger.info(
            "Orphan cleanup: %d total files, %d orphans queued for deletion",
            len(all_files),
            len(orphans),
        )

        deleted = await _delete_orphans(orphans)
        return {
            "total_files": len(all_files),
            "orphans_found": len(orphans),
            "deleted": deleted,
        }

    result: dict[str, Any] = _run_async(_run())
    logger.info("Orphan file cleanup complete: %s", result)
    return result

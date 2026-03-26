"""Celery task: Full site data export.

Exports all database tables (as JSON) and all S3/R2 objects into a single
ZIP archive, uploads it to MinIO/R2, and returns a presigned download URL.

Security:
- Only SUPER_ADMIN can trigger (enforced at endpoint layer).
- Distributed Redis lock prevents concurrent exports.
- Presigned URL has 15-minute TTL.
- All operations are audit-logged.
- Sensitive columns (password_hash) are excluded from export.

Memory safety:
- DB rows streamed in 1000-row batches, written to ZIP incrementally.
- S3 objects streamed in 64KB chunks directly into the ZIP file.
- ZIP written to a temporary file on disk, not held in memory.
- 10GB hard cap on ZIP size; partial export if exceeded.
"""

import asyncio
import json
import os
import tempfile
import uuid
import zipfile
from datetime import datetime, timezone
from typing import Any

from loguru import logger

from app.celery_app import celery
from app.core.config import settings
from app.core.constants import (
    EXPORT_DB_BATCH_SIZE,
    EXPORT_MAX_ZIP_BYTES,
    EXPORT_PRESIGNED_TTL_SECONDS,
    EXPORT_S3_BATCH_LOG_INTERVAL,
)
from app.core.storage import generate_presigned_url, get_storage, init_storage, upload_file
from app.tasks.async_runner import run_async as _run_async
from app.tasks.utils import ensure_pool as _ensure_pool
from app.tasks.utils import ensure_redis as _ensure_redis

# ── Error sanitisation ────────────────────────────────────────────────────
# L-14: Duplicate of the pattern in the export endpoint — sanitize at write
# time so raw exception text is never stored in Redis.
import re as _re

_INTERNAL_PATTERNS = _re.compile(
    r"((?:/[a-z_]+)+\.py|Traceback|asyncpg\.|postgresql://|redis://|File \"|"
    r"ConnectionRefusedError|OSError|socket\.gaierror)",
    _re.IGNORECASE,
)
_SAFE_ERROR_MSG = "Export failed due to an internal error. Please check server logs."


def _sanitize_error(raw: str) -> str:
    """Return a safe error message, stripping internal details."""
    if _INTERNAL_PATTERNS.search(raw):
        return _SAFE_ERROR_MSG
    return raw[:200]


# ── Distributed lock ──────────────────────────────────────────────────────

LOCK_KEY = "export:site:lock"

_LUA_RELEASE_LOCK = """
if redis.call("get", KEYS[1]) == ARGV[1] then
    return redis.call("del", KEYS[1])
else
    return 0
end
"""

# B2: Acquire lock — succeeds if key is absent OR value is "pending" (set by endpoint).
# ARGV[1] = task_id, ARGV[2] = TTL in seconds.
_LUA_ACQUIRE_LOCK = """
local val = redis.call("get", KEYS[1])
if val == false or val == "pending" then
    redis.call("set", KEYS[1], ARGV[1], "EX", ARGV[2])
    return 1
else
    return 0
end
"""

# ── Progress helpers ──────────────────────────────────────────────────────

PROGRESS_KEY_PREFIX = "export:progress:"
HISTORY_KEY = "export:site:history"

_PROGRESS_TTL = 86400


async def _set_progress(task_id: str, data: dict) -> None:
    from app.core.redis import get_redis

    redis = get_redis()
    key = f"{PROGRESS_KEY_PREFIX}{task_id}"
    await redis.hset(key, mapping={k: str(v) for k, v in data.items()})
    await redis.expire(key, _PROGRESS_TTL)


async def _set_progress_field(task_id: str, field: str, value: str | int) -> None:
    from app.core.redis import get_redis

    redis = get_redis()
    key = f"{PROGRESS_KEY_PREFIX}{task_id}"
    await redis.hset(key, field, str(value))
    await redis.expire(key, _PROGRESS_TTL)


# ── JSON serialisation ────────────────────────────────────────────────────

def _json_serial(obj: Any) -> Any:
    """JSON serialiser for types not handled by default."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, uuid.UUID):
        return str(obj)
    if isinstance(obj, bytes):
        import base64

        return base64.b64encode(obj).decode("ascii")
    if isinstance(obj, memoryview):
        import base64

        return base64.b64encode(bytes(obj)).decode("ascii")
    raise TypeError(f"Type {type(obj)} not JSON serializable")


# ── Tables to export ──────────────────────────────────────────────────────

# Order respects FK dependencies (parents first).
_EXPORT_TABLES: list[str] = [
    "users",
    "user_preferences",
    "categories",
    "sigs",
    "sig_members",
    "posts",
    "post_history",
    "post_reports",
    "comments",
    "comment_votes",
    "forms",
    "form_responses",
    "notifications",
    "friendships",
    "follows",
    "blocks",
    "friend_recommendations",
    "dismissed_recommendations",
    "post_citations",
    "post_co_authors",
    "profile_views",
    "albums",
    "album_members",
    "album_photos",
    "album_comments",
    "conversations",
    "dm_messages",
    "file_scans",
    "audit_logs",
    "ip_bans",
    "invite_codes",
    "membership_applications",
    "privacy_consents",
    "contributors",
    "site_settings",
    "org_chart_overrides",
]

# S1: Columns to exclude from export per table (security-sensitive data).
_EXCLUDED_COLUMNS: dict[str, set[str]] = {
    "users": {"password_hash"},
}


# ── Core export logic ─────────────────────────────────────────────────────

async def _get_export_columns(
    conn: Any,
    table_name: str,
) -> list[str]:
    """Return column names for a table, excluding sensitive columns."""
    rows = await conn.fetch(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema = 'public' AND table_name = $1 "
        "ORDER BY ordinal_position",
        table_name,
    )
    excluded = _EXCLUDED_COLUMNS.get(table_name, set())
    return [r["column_name"] for r in rows if r["column_name"] not in excluded]


async def _export_db_to_zip(
    zf: zipfile.ZipFile,
    task_id: str,
) -> dict[str, int]:
    """Export all database tables into database/*.json inside the ZIP.

    L-11: Rows are fetched in batches using LIMIT/OFFSET. The DB connection
    is acquired per batch and released between batches, preventing a single
    long-running connection from blocking the pool.

    Returns a dict of {table_name: row_count}.
    """
    from app.core.database import get_pool

    pool = get_pool()
    table_counts: dict[str, int] = {}

    for table_idx, table_name in enumerate(_EXPORT_TABLES):
        try:
            await _set_progress(task_id, {
                "phase": "db",
                "current": table_idx,
                "total": len(_EXPORT_TABLES),
                "detail": f"Exporting table: {table_name}",
            })
        except Exception:
            logger.warning("Redis progress update failed, continuing export", exc_info=True)

        async with pool.acquire() as conn:
            # Check table exists (skip gracefully if migration not applied)
            exists = await conn.fetchval(
                "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
                "WHERE table_schema = 'public' AND table_name = $1)",
                table_name,
            )
            if not exists:
                logger.warning("Table does not exist, skipping", extra={"table": table_name})
                table_counts[table_name] = 0
                continue

            # Get safe column list (excludes sensitive columns like password_hash)
            columns = await _get_export_columns(conn, table_name)
            col_list = ", ".join(f'"{c}"' for c in columns)

        # L-11: Fetch rows in batches — connection is acquired and released per batch.
        # Table name comes from hardcoded _EXPORT_TABLES, not user input.
        zip_info = zipfile.ZipInfo(f"database/{table_name}.json")
        zip_info.compress_type = zipfile.ZIP_DEFLATED
        row_count = 0
        offset = 0

        with zf.open(zip_info, "w") as dest:
            dest.write(b"[")
            first = True

            while True:
                async with pool.acquire() as conn:
                    rows = await conn.fetch(
                        f'SELECT {col_list} FROM "{table_name}" '  # noqa: S608
                        f"ORDER BY ctid LIMIT {EXPORT_DB_BATCH_SIZE} OFFSET {offset}",
                    )

                for row in rows:
                    if not first:
                        dest.write(b",\n")
                    first = False
                    dest.write(
                        json.dumps(
                            dict(row), default=_json_serial, ensure_ascii=False,
                        ).encode("utf-8")
                    )
                    row_count += 1

                if len(rows) < EXPORT_DB_BATCH_SIZE:
                    break
                offset += EXPORT_DB_BATCH_SIZE

            dest.write(b"]")

        table_counts[table_name] = row_count

        logger.info(
            "Exported table",
            extra={"table": table_name, "rows": row_count, "index": table_idx},
        )

    # Update progress to indicate DB phase done
    try:
        await _set_progress_field(task_id, "current", len(_EXPORT_TABLES))
    except Exception:
        logger.warning("Redis progress update failed, continuing export", exc_info=True)

    return table_counts


def _sync_copy_s3_object_to_zip(
    client: Any,
    bucket: str,
    key: str,
    zf: zipfile.ZipFile,
) -> int:
    """Download a single S3 object and write it into the ZIP (sync, runs in executor).

    Returns the object size in bytes. Ensures the S3 response body is closed
    even if an exception occurs (L-13).
    """
    resp = client.get_object(Bucket=bucket, Key=key)
    body = resp["Body"]
    obj_size = int(resp.get("ContentLength", 0))
    try:
        zip_info = zipfile.ZipInfo(f"files/{key}")
        zip_info.compress_type = zipfile.ZIP_STORED
        with zf.open(zip_info, "w") as dest:
            while True:
                chunk = body.read(65536)  # 64KB chunks
                if not chunk:
                    break
                dest.write(chunk)
    finally:
        # L-13: Always close the S3 response body
        try:
            body.close()
        except Exception:
            pass
    return obj_size


async def _export_files_to_zip(
    zf: zipfile.ZipFile,
    task_id: str,
) -> tuple[int, int, list[str]]:
    """Copy all S3 objects into files/ directory inside the ZIP.

    Uses a single-pass listing to avoid double-listing race conditions.
    Sync boto3 calls are offloaded to a thread executor (L-10).

    Returns (total_files, total_bytes, skipped_keys).
    """
    try:
        client = get_storage()
    except RuntimeError:
        init_storage()
        client = get_storage()

    bucket = settings.S3_BUCKET_NAME
    loop = asyncio.get_event_loop()

    # B7: Single-pass — stream objects into ZIP while counting
    try:
        await _set_progress(task_id, {
            "phase": "files",
            "current": 0,
            "total": 0,
            "detail": "Scanning and copying files from storage",
        })
    except Exception:
        logger.warning("Redis progress update failed, continuing export", exc_info=True)

    file_count = 0
    total_bytes = 0
    skipped: list[str] = []
    zip_size_estimate = zf.fp.tell() if zf.fp else 0  # type: ignore[union-attr]

    # L-10: Offload blocking S3 pagination to executor
    paginator = client.get_paginator("list_objects_v2")
    pages = await loop.run_in_executor(
        None, lambda: list(paginator.paginate(Bucket=bucket))
    )

    for page in pages:
        for obj in page.get("Contents", []):
            key: str = obj["Key"]

            # Skip export archives themselves
            if key.startswith("exports/"):
                continue

            # Check ZIP size cap
            if zip_size_estimate >= EXPORT_MAX_ZIP_BYTES:
                skipped.append(key)
                continue

            try:
                # L-10: Offload blocking S3 get + ZIP write to executor
                # L-13: body.close() handled inside _sync_copy_s3_object_to_zip
                obj_size = await loop.run_in_executor(
                    None, _sync_copy_s3_object_to_zip, client, bucket, key, zf,
                )

                total_bytes += obj_size
                zip_size_estimate += obj_size  # approximate (stored, not compressed)

            except Exception:
                logger.warning("Failed to export S3 object", extra={"key": key}, exc_info=True)
                skipped.append(key)
                continue

            file_count += 1

            if file_count % EXPORT_S3_BATCH_LOG_INTERVAL == 0:
                try:
                    await _set_progress(task_id, {
                        "phase": "files",
                        "current": file_count,
                        "total": 0,  # unknown in single-pass; suppresses misleading 100% bar
                        "detail": f"Copied {file_count} files ({key})",
                        "zip_size": zip_size_estimate,
                    })
                except Exception:
                    logger.warning("Redis progress update failed, continuing export", exc_info=True)

    # Final progress update
    try:
        await _set_progress(task_id, {
            "phase": "files",
            "current": file_count,
            "total": file_count,
            "zip_size": zip_size_estimate,
        })
    except Exception:
        logger.warning("Redis progress update failed, continuing export", exc_info=True)

    return file_count, total_bytes, skipped


async def _trim_history(redis: Any) -> None:
    """Trim export history to EXPORT_HISTORY_MAX entries."""
    from app.core.constants import EXPORT_HISTORY_MAX

    count = await redis.zcard(HISTORY_KEY)
    if count > EXPORT_HISTORY_MAX:
        await redis.zremrangebyrank(HISTORY_KEY, 0, count - EXPORT_HISTORY_MAX - 1)


async def _async_export(task_id: str, options: dict, user_id: str) -> dict:
    """Main async export coroutine."""
    from app.core.constants import EXPORT_LOCK_TTL_SECONDS
    from app.core.redis import get_redis

    await _ensure_pool()
    await _ensure_redis()

    redis = get_redis()

    # ── Acquire distributed lock ──────────────────────────────────────
    # B2: Use Lua script that accepts absent or "pending" (set by endpoint pre-lock).
    acquired = await redis.eval(
        _LUA_ACQUIRE_LOCK, 1, LOCK_KEY, task_id, str(EXPORT_LOCK_TTL_SECONDS),
    )
    if not acquired:
        raise RuntimeError("Another site export is already in progress.")

    tmp_path: str | None = None

    try:
        # Ensure storage client is initialised
        try:
            get_storage()
        except RuntimeError:
            init_storage()

        include_db = options.get("include_database", True)
        include_files = options.get("include_files", True)

        started_at = datetime.now(timezone.utc).isoformat()
        try:
            await _set_progress(task_id, {
                "phase": "starting",
                "current": 0,
                "total": 0,
                "detail": "Initializing export",
                "zip_size": 0,
                "started_at": started_at,
            })
        except Exception:
            logger.warning("Redis progress update failed, continuing export", exc_info=True)

        # Create temporary file for ZIP
        fd, tmp_path = tempfile.mkstemp(suffix=".zip", prefix="site-export-")
        os.close(fd)

        table_counts: dict[str, int] = {}
        file_count = 0
        total_file_bytes = 0
        skipped_files: list[str] = []

        with zipfile.ZipFile(tmp_path, "w", allowZip64=True) as zf:
            # Phase 1: Database
            if include_db:
                table_counts = await _export_db_to_zip(zf, task_id)

            # Phase 2: Files
            if include_files:
                file_count, total_file_bytes, skipped_files = await _export_files_to_zip(zf, task_id)

            # Phase 3: Write metadata
            metadata = {
                "exported_at": datetime.now(timezone.utc).isoformat(),
                "exported_by": user_id,
                "options": options,
                "tables": table_counts,
                "file_count": file_count,
                "total_file_bytes": total_file_bytes,
                "skipped_files": skipped_files[:100],  # cap list for metadata size
                "skipped_count": len(skipped_files),
                "partial": len(skipped_files) > 0,
                "version": "1.0",
            }
            manifest_json = json.dumps(
                {"tables": table_counts},
                default=_json_serial,
                ensure_ascii=False,
            )
            zf.writestr(
                zipfile.ZipInfo("database/_manifest.json"),
                manifest_json.encode("utf-8"),
            )
            zf.writestr(
                zipfile.ZipInfo("metadata.json"),
                json.dumps(metadata, ensure_ascii=False, indent=2).encode("utf-8"),
            )

        # Phase 4: Upload ZIP to S3
        zip_size = os.path.getsize(tmp_path)
        try:
            await _set_progress(task_id, {
                "phase": "uploading",
                "current": 0,
                "total": 1,
                "detail": f"Uploading ZIP ({zip_size / 1024 / 1024:.1f} MB)",
                "zip_size": zip_size,
            })
        except Exception:
            logger.warning("Redis progress update failed, continuing export", exc_info=True)

        storage_key = f"exports/site-backup/{task_id}/{uuid.uuid4().hex}.zip"

        # Upload in chunks to avoid loading full ZIP into memory
        client = get_storage()
        bucket = settings.S3_BUCKET_NAME

        # For files under ~100MB, simple put_object is fine.
        # For larger files, use multipart upload.
        if zip_size <= 100 * 1024 * 1024:
            with open(tmp_path, "rb") as f:
                data = f.read()
            upload_file(data, storage_key, "application/zip")
            del data
        else:
            # Multipart upload for large files
            mpu = client.create_multipart_upload(
                Bucket=bucket,
                Key=storage_key,
                ContentType="application/zip",
            )
            upload_id = mpu["UploadId"]
            parts: list[dict] = []
            part_size = 50 * 1024 * 1024  # 50MB parts

            try:
                with open(tmp_path, "rb") as f:
                    part_number = 1
                    while True:
                        chunk = f.read(part_size)
                        if not chunk:
                            break
                        resp = client.upload_part(
                            Bucket=bucket,
                            Key=storage_key,
                            UploadId=upload_id,
                            PartNumber=part_number,
                            Body=chunk,
                        )
                        parts.append({"ETag": resp["ETag"], "PartNumber": part_number})
                        part_number += 1

                client.complete_multipart_upload(
                    Bucket=bucket,
                    Key=storage_key,
                    UploadId=upload_id,
                    MultipartUpload={"Parts": parts},
                )
            except Exception:
                client.abort_multipart_upload(
                    Bucket=bucket,
                    Key=storage_key,
                    UploadId=upload_id,
                )
                raise

        logger.info("Site export ZIP uploaded", extra={"key": storage_key, "size": zip_size})

        # Generate presigned download URL
        timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        download_filename = f"site-backup-{timestamp_str}.zip"
        download_url = generate_presigned_url(
            storage_key,
            expires_in=EXPORT_PRESIGNED_TTL_SECONDS,
            filename=download_filename,
        )

        # Save to history (includes storage_key for presigned URL regeneration)
        history_entry = json.dumps({
            "task_id": task_id,
            "status": "SUCCESS",
            "created_at": started_at,
            "created_by": user_id,
            "options": options,
            "file_size": zip_size,
            "storage_key": storage_key,
        })
        now_ts = datetime.now(timezone.utc).timestamp()
        await redis.zadd(HISTORY_KEY, {history_entry: now_ts})
        # M-12: Populate lookup hash for O(1) delete
        await redis.hset("export:site:lookup", task_id, history_entry)

        # B6: Store storage_key in progress hash so progress endpoint
        # can regenerate presigned URLs instead of using the cached one.
        try:
            await _set_progress(task_id, {
                "phase": "done",
                "current": 1,
                "total": 1,
                "detail": "Export complete",
                "zip_size": zip_size,
                "started_at": started_at,
                "storage_key": storage_key,
            })
        except Exception:
            logger.warning("Redis progress update failed, continuing export", exc_info=True)

        # B4: Trim history on success path
        await _trim_history(redis)

        return {"download_url": download_url, "storage_key": storage_key, "file_size": zip_size}

    except Exception as exc:
        # Record failure in progress
        try:
            await _set_progress(task_id, {
                "phase": "failed",
                "detail": _sanitize_error(str(exc)[:500]),
            })
            # Record in history as failed
            history_entry = json.dumps({
                "task_id": task_id,
                "status": "FAILURE",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "created_by": user_id,
                "options": options,
                "file_size": None,
                "storage_key": None,
            })
            now_ts = datetime.now(timezone.utc).timestamp()
            await redis.zadd(HISTORY_KEY, {history_entry: now_ts})
            # M-12: Populate lookup hash for O(1) delete
            await redis.hset("export:site:lookup", task_id, history_entry)

            # B4: Trim history on failure path too
            await _trim_history(redis)
        except Exception:
            logger.error("Failed to record export failure", exc_info=True)
        raise

    finally:
        # Always release lock (Lua script: only release if we own it)
        try:
            await redis.eval(_LUA_RELEASE_LOCK, 1, LOCK_KEY, task_id)
        except Exception:
            logger.error("Failed to release export lock", exc_info=True)

        # Always clean up temp file
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError:
                logger.warning("Failed to delete temp file", extra={"path": tmp_path})


# ── Celery task definition ────────────────────────────────────────────────

@celery.task(
    bind=True,
    name="tasks.export_site_data",
    max_retries=0,
    soft_time_limit=3600,
    time_limit=7200,
)
def export_site_data(self: Any, options: dict, user_id: str) -> dict:
    """Export full site data. Runs in Celery worker (sync wrapper)."""
    import asyncio

    from celery.exceptions import SoftTimeLimitExceeded

    from app.tasks.async_runner import _ensure_loop

    loop = _ensure_loop()
    coro = _async_export(self.request.id, options, user_id)
    future = asyncio.run_coroutine_threadsafe(coro, loop)

    try:
        result: dict = future.result(timeout=7200)
        return result
    except SoftTimeLimitExceeded:
        # F-21: Cancel the orphan coroutine to prevent resource leaks
        future.cancel()
        task_id = self.request.id
        logger.error("Site export hit soft time limit", extra={"task_id": task_id})
        # Clean up Redis lock and temp files via best-effort async cleanup
        try:
            _run_async(_cleanup_after_timeout(task_id), timeout=30)
        except Exception:
            logger.error("Failed to clean up after timeout", exc_info=True)
        raise


async def _cleanup_after_timeout(task_id: str) -> None:
    """Best-effort cleanup of Redis lock after a timeout."""
    try:
        from app.core.redis import get_redis

        redis = get_redis()
        await redis.eval(_LUA_RELEASE_LOCK, 1, LOCK_KEY, task_id)
    except Exception:
        logger.error("Failed to release lock during timeout cleanup", exc_info=True)
    try:
        await _set_progress(task_id, {
            "phase": "failed",
            "detail": "Export timed out",
        })
    except Exception:
        pass


# ── Cleanup task ──────────────────────────────────────────────────────────

async def _async_cleanup_old_exports() -> int:
    """Delete export ZIPs older than EXPORT_CLEANUP_DAYS."""
    from datetime import timedelta

    from app.core.constants import EXPORT_CLEANUP_DAYS

    await _ensure_redis()

    from app.core.redis import get_redis

    redis = get_redis()

    cutoff_ts = (datetime.now(timezone.utc) - timedelta(days=EXPORT_CLEANUP_DAYS)).timestamp()

    # Find old history entries
    old_entries = await redis.zrangebyscore(HISTORY_KEY, "-inf", cutoff_ts)
    if not old_entries:
        return 0

    try:
        client = get_storage()
    except RuntimeError:
        init_storage()
        client = get_storage()

    bucket = settings.S3_BUCKET_NAME
    deleted = 0
    # B5: Track entries whose S3 files were successfully deleted (or had no file).
    # Only remove these from history; entries with failed S3 deletions are retained.
    cleaned_entries: list[str] = []

    for entry_str in old_entries:
        try:
            entry = json.loads(entry_str)
            storage_key = entry.get("storage_key")
            if storage_key:
                try:
                    client.delete_object(Bucket=bucket, Key=storage_key)
                    logger.info("Deleted old export", extra={"key": storage_key})
                except Exception:
                    logger.warning("Failed to delete old export file", extra={"key": storage_key})
                    continue  # B5: do NOT remove history entry if file deletion failed
            cleaned_entries.append(entry_str)
            deleted += 1
        except (json.JSONDecodeError, TypeError):
            # Malformed entries can be safely removed
            cleaned_entries.append(entry_str)

    # B5: Only remove successfully cleaned entries from sorted set
    for entry_str in cleaned_entries:
        await redis.zrem(HISTORY_KEY, entry_str)

    logger.info("Cleaned up old site exports", extra={"deleted": deleted})
    return deleted


@celery.task(name="cleanup_old_site_exports", max_retries=0)
def cleanup_old_site_exports() -> int:
    """Periodic cleanup of old site export files."""
    return _run_async(_async_cleanup_old_exports(), timeout=300)

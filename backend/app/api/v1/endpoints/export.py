"""Site data export endpoints (SUPER_ADMIN only)."""

import asyncio
import json
import re

from fastapi import APIRouter, Depends, Path, Query, Request, status
from loguru import logger

from app.core.rate_limit import get_client_ip

from app.core.constants import EXPORT_PRESIGNED_TTL_SECONDS, RATE_LIMIT_SITE_EXPORT
from app.core.deps import require_role
from app.core.errors import AppError, ErrorCode
from app.schemas.export import (
    ExportHistoryItem,
    ExportHistoryResponse,
    ExportProgressResponse,
    SiteExportRequest,
    SiteExportResponse,
)

router = APIRouter(prefix="/admin/export", tags=["admin-export"])

# S2: Pattern to detect internal details that should not be exposed to users.
_INTERNAL_PATTERNS = re.compile(
    r"((?:/[a-z_]+)+\.py|Traceback|asyncpg\.|postgresql://|redis://|File \"|"
    r"ConnectionRefusedError|OSError|socket\.gaierror|"
    r"minio://|http://minio:|s3://)",
    re.IGNORECASE,
)
_SAFE_ERROR_MSG = "Export failed due to an internal error. Please check server logs."


def _sanitize_error(raw: str | None) -> str | None:
    """Return a safe error message, stripping internal details."""
    if not raw:
        return raw
    if _INTERNAL_PATTERNS.search(raw):
        return _SAFE_ERROR_MSG
    # Truncate to a reasonable length
    return raw[:200]


@router.post("", status_code=status.HTTP_202_ACCEPTED, response_model=SiteExportResponse)
async def start_site_export(
    body: SiteExportRequest,
    request: Request,
    current_user: dict = Depends(require_role("SUPER_ADMIN")),
) -> SiteExportResponse:
    """Trigger a full site data export (database + files).

    Only one export can run at a time (distributed lock).
    Rate limited to 1 per 30 minutes.
    """
    from app.core.rate_limit import check_rate_limit
    from app.core.redis import get_redis

    user_id = current_user["sub"]

    # Rate limit
    rl_key = f"rl:site_export:{user_id}"
    max_count, window = RATE_LIMIT_SITE_EXPORT
    allowed = await check_rate_limit(rl_key, max_count, window)
    if not allowed:
        raise AppError(ErrorCode.SYS_429, 429, "Export rate limit exceeded. Please wait before trying again.")

    # B2: Atomically reserve the lock to prevent TOCTOU race.
    # SET NX with short TTL (60s safety net). The Celery task will upgrade
    # this "pending" value to its task_id via a Lua script that accepts
    # either absent or "pending" as valid preconditions.
    redis = get_redis()
    pre_locked = await redis.set("export:site:lock", "pending", nx=True, ex=60)
    if not pre_locked:
        raise AppError(ErrorCode.SYS_409, 409, "Another site export is already in progress.")

    # Trigger Celery task
    from app.tasks.site_export import export_site_data

    options = body.model_dump()
    task = export_site_data.delay(options, user_id)

    # Store task ownership
    await redis.set(f"task_owner:{task.id}", user_id, ex=86400)

    # Audit log
    try:
        from app.core.event_bus import emit

        ip = get_client_ip(request)
        await emit(
            "audit.action",
            user_id=user_id,
            action="SITE_EXPORT_START",
            target_type="export",
            target_id=task.id,
            ip_address=ip,
            detail=json.dumps(options),
        )
    except Exception as e:
        logger.error("Audit log emit failed for SITE_EXPORT_START", extra={"error": str(e)})

    return SiteExportResponse(task_id=task.id, message="Export started. Poll progress for status.")


@router.get("/progress/{task_id}", response_model=ExportProgressResponse)
async def get_export_progress(
    current_user: dict = Depends(require_role("SUPER_ADMIN")),
    task_id: str = Path(..., min_length=1, max_length=64),
) -> ExportProgressResponse:
    """Poll export task progress."""
    from celery.result import AsyncResult

    from app.celery_app import celery
    from app.core.redis import get_redis

    redis = get_redis()

    # Read progress from Redis hash
    progress_key = f"export:progress:{task_id}"
    progress = await redis.hgetall(progress_key)

    # Get Celery task state
    result = AsyncResult(task_id, app=celery)
    celery_status = result.state

    download_url = None
    error_msg = None

    if celery_status == "SUCCESS":
        # B6: Regenerate presigned URL from storage_key instead of using
        # the cached URL from the Celery result (which expires after 15 min).
        storage_key = progress.get("storage_key")
        if storage_key:
            try:
                from app.core.storage import generate_presigned_url as gen_url

                download_url = gen_url(
                    storage_key,
                    expires_in=EXPORT_PRESIGNED_TTL_SECONDS,
                    filename=f"site-backup-{task_id}.zip",
                )
            except Exception:
                logger.warning("Failed to regenerate presigned URL for export progress", exc_info=True)
        elif result.result:
            # Fallback to Celery result if storage_key not in progress hash
            download_url = result.result.get("download_url")
    elif celery_status == "FAILURE":
        # S2: Sanitize error — don't leak internal details
        raw_error = str(result.result) if result.result else progress.get("detail")
        error_msg = _sanitize_error(raw_error)

    # S2: Sanitize `detail` on failure — it may contain str(exc) with internal info.
    detail = progress.get("detail")
    if progress.get("phase") == "failed" and detail:
        detail = _sanitize_error(detail)

    return ExportProgressResponse(
        task_id=task_id,
        status=celery_status,
        phase=progress.get("phase"),
        current=int(progress.get("current", 0)),
        total=int(progress.get("total", 0)),
        detail=detail,
        zip_size=int(progress.get("zip_size", 0)),
        download_url=download_url,
        started_at=progress.get("started_at"),
        error=error_msg,
    )


@router.get("/history", response_model=ExportHistoryResponse)
async def get_export_history(
    request: Request,
    current_user: dict = Depends(require_role("SUPER_ADMIN")),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> ExportHistoryResponse:
    """List past export records (most recent first), with pagination."""
    from app.core.redis import get_redis
    from app.core.storage import generate_presigned_url, get_storage

    redis = get_redis()

    # M-11: Get total count and paginated slice from sorted set
    total = await redis.zcard("export:site:history") or 0
    start = offset
    stop = offset + limit - 1  # zrevrange stop is inclusive
    entries = await redis.zrevrange("export:site:history", start, stop)

    loop = asyncio.get_running_loop()

    exports: list[ExportHistoryItem] = []
    for entry_str in entries:
        try:
            entry = json.loads(entry_str)
        except (json.JSONDecodeError, TypeError):
            continue

        download_url = None
        if entry.get("status") == "SUCCESS" and entry.get("storage_key"):
            # Check if the file still exists in S3 before generating URL
            try:
                from app.core.config import settings as app_settings

                client = get_storage()
                # M-07: Wrap synchronous boto3 call in executor
                await loop.run_in_executor(
                    None,
                    lambda: client.head_object(
                        Bucket=app_settings.S3_BUCKET_NAME,
                        Key=entry["storage_key"],
                    ),
                )
                download_url = generate_presigned_url(
                    entry["storage_key"],
                    expires_in=EXPORT_PRESIGNED_TTL_SECONDS,
                    filename=f"site-backup-{entry.get('task_id', 'unknown')}.zip",
                )
            except Exception:
                # File no longer exists or storage unavailable
                pass

        exports.append(ExportHistoryItem(
            task_id=entry.get("task_id", ""),
            status=entry.get("status", "UNKNOWN"),
            created_at=entry.get("created_at", ""),
            created_by=entry.get("created_by", ""),
            options=entry.get("options", {}),
            file_size=entry.get("file_size"),
            download_url=download_url,
        ))

    return ExportHistoryResponse(exports=exports, total=total)


@router.delete("/{task_id}", status_code=status.HTTP_200_OK)
async def delete_export(
    request: Request,
    current_user: dict = Depends(require_role("SUPER_ADMIN")),
    # S3: Add Path validation consistent with progress endpoint
    task_id: str = Path(..., min_length=1, max_length=64),
) -> dict:
    """Delete an export archive from storage and history."""
    from app.core.redis import get_redis

    redis = get_redis()

    # M-12: Try hash lookup first (O(1)), fall back to linear scan for older entries
    lookup_entry_str = await redis.hget("export:site:lookup", task_id)
    target_entry: str | None = None
    storage_key: str | None = None

    if lookup_entry_str:
        try:
            entry = json.loads(lookup_entry_str)
            storage_key = entry.get("storage_key")
            # We need the exact sorted-set member string to zrem it
            target_entry = lookup_entry_str
        except (json.JSONDecodeError, TypeError):
            pass

    if target_entry is None:
        # Fallback: linear scan (for entries created before hash was introduced)
        entries = await redis.zrange("export:site:history", 0, -1)
        for entry_str in entries:
            try:
                entry = json.loads(entry_str)
                if entry.get("task_id") == task_id:
                    target_entry = entry_str
                    storage_key = entry.get("storage_key")
                    break
            except (json.JSONDecodeError, TypeError):
                continue

    if target_entry is None:
        raise AppError(ErrorCode.SYS_404, 404, "Export record not found.")

    # M-07: Delete file from S3 using executor to avoid blocking the event loop
    if storage_key:
        try:
            from app.core.config import settings
            from app.core.storage import get_storage

            client = get_storage()
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(
                None,
                lambda: client.delete_object(Bucket=settings.S3_BUCKET_NAME, Key=storage_key),
            )
            logger.info("Deleted export file", extra={"key": storage_key})
        except Exception:
            logger.warning("Failed to delete export file from storage", extra={"key": storage_key})

    # Remove from history sorted set and lookup hash
    await redis.zrem("export:site:history", target_entry)
    await redis.hdel("export:site:lookup", task_id)

    # Clean up progress key
    await redis.delete(f"export:progress:{task_id}")

    # Audit log
    try:
        from app.core.event_bus import emit

        ip = get_client_ip(request)
        await emit(
            "audit.action",
            user_id=current_user["sub"],
            action="SITE_EXPORT_DELETE",
            target_type="export",
            target_id=task_id,
            ip_address=ip,
        )
    except Exception as e:
        logger.error("Audit log emit failed for SITE_EXPORT_DELETE", extra={"error": str(e)})

    return {"message": "Export deleted."}

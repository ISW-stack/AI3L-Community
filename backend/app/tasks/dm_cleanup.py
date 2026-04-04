"""DM cleanup tasks -- expired files and messages."""

from datetime import datetime, timedelta, timezone

from loguru import logger

from app.celery_app import celery
from app.tasks.async_runner import run_async as _run_async
from app.tasks.utils import ensure_pool as _ensure_pool


@celery.task(name="cleanup_dm_expired_files", bind=True, max_retries=2, default_retry_delay=30)
def cleanup_dm_expired_files(self) -> dict:  # type: ignore[override]
    """Delete DM file attachments past their expiry. Refund storage quota."""
    result: dict = _run_async(_cleanup_files())
    return result


async def _cleanup_files() -> dict:
    await _ensure_pool()

    from app.core.async_storage import delete_file
    from app.core.constants import DM_FILE_EXPIRY_DAYS
    from app.repositories import dm_repo, user_repo

    cutoff = datetime.now(timezone.utc) - timedelta(days=DM_FILE_EXPIRY_DAYS)

    deleted = 0
    errors = 0

    while True:
        expired = await dm_repo.find_expired_file_messages(cutoff, limit=1000)
        if not expired:
            break

        for msg in expired:
            try:
                # F-17: Clear DB record first, then delete from MinIO.
                # If MinIO deletion fails, the orphan cleanup task will catch it.
                # This avoids the case where MinIO succeeds but DB fails,
                # leaving no record for retry on next run.
                attachment_key = msg.get("attachment_key")
                attachment_size = msg.get("attachment_size")
                sender_id = msg.get("sender_id")

                cleared = await dm_repo.clear_message_attachment_if_present(
                    msg["id"], has_content=msg.get("content") is not None
                )
                if not cleared:
                    continue

                if attachment_key:
                    try:
                        await delete_file(attachment_key)
                    except Exception:
                        logger.warning(
                            "Failed to delete DM file from storage (orphan cleanup will handle)",
                            exc_info=True,
                            extra={"msg_id": str(msg["id"]), "key": attachment_key},
                        )
                    if attachment_size and sender_id:
                        # M-04 Equivalent: Retry storage decrement during cleanup
                        for attempt in range(3):
                            try:
                                await user_repo.decrement_storage_used(
                                    sender_id, attachment_size
                                )
                                break
                            except Exception:
                                if attempt == 2:
                                    logger.error(
                                        "Failed to refund storage counter after DM cleanup",
                                        extra={
                                            "msg_id": str(msg["id"]),
                                            "sender_id": str(sender_id),
                                            "total_freed": attachment_size,
                                            "compensation_required": True,
                                        },
                                        exc_info=True,
                                    )
                                else:
                                    import asyncio
                                    await asyncio.sleep(1)
                deleted += 1
            except Exception:
                errors += 1
                logger.error(
                    "Failed to clean up DM attachment",
                    exc_info=True,
                    extra={"msg_id": str(msg["id"])},
                )

        if len(expired) < 1000:
            break

    logger.info("DM file cleanup complete", extra={"deleted": deleted, "errors": errors})
    return {"deleted": deleted, "errors": errors}


@celery.task(name="cleanup_dm_expired_text", bind=True, max_retries=2, default_retry_delay=30)
def cleanup_dm_expired_text(self) -> dict:  # type: ignore[override]
    """Delete DM text messages older than the retention period."""
    result: dict = _run_async(_cleanup_text())
    return result


async def _cleanup_text() -> dict:
    await _ensure_pool()

    from app.core.constants import DM_TEXT_EXPIRY_DAYS
    from app.repositories import dm_repo

    cutoff = datetime.now(timezone.utc) - timedelta(days=DM_TEXT_EXPIRY_DAYS)
    total_deleted = 0

    from app.core.database import get_pool

    while True:
        expired = await dm_repo.find_expired_text_messages(cutoff, limit=1000)
        if not expired:
            break

        # Group by conversation for per-conversation transactions.
        conv_msgs: dict[object, list] = {}
        for msg in expired:
            cid = msg["conversation_id"]
            if cid not in conv_msgs:
                conv_msgs[cid] = []
            conv_msgs[cid].append(msg["id"])

        # F-18: Process each conversation in its own transaction so advisory
        # locks are released after each one, avoiding lock accumulation.
        # F-64: Use DELETE...RETURNING to atomically get actual char lengths
        # of deleted rows. If a double-run occurs, already-deleted rows won't
        # appear in RETURNING, so no spurious char decrements happen.
        pool = get_pool()
        for cid, cid_msg_ids in conv_msgs.items():
            async with pool.acquire() as conn:
                async with conn.transaction():
                    await conn.execute(
                        "SELECT pg_advisory_xact_lock(hashtext($1::text))",
                        str(cid),
                    )
                    deleted_rows = await conn.fetch(
                        "DELETE FROM dm_messages WHERE id = ANY($1::uuid[]) "
                        "RETURNING id, COALESCE(LENGTH(content), 0) AS content_len",
                        cid_msg_ids,
                    )
                    chars = sum(r["content_len"] for r in deleted_rows)
                    if chars > 0:
                        await conn.execute(
                            "UPDATE conversations SET total_chars = GREATEST(0, total_chars - $1) "
                            "WHERE id = $2",
                            chars,
                            cid,
                        )
            total_deleted += len(deleted_rows)
        if len(expired) < 1000:
            break

    logger.info("DM text cleanup complete", extra={"deleted": total_deleted})
    return {"deleted": total_deleted}


# ── L-12: Orphan file cleanup for dm/ prefix ──────────────────────────────

_DM_ORPHAN_BATCH_SIZE = 1000


@celery.task(name="cleanup_dm_orphan_files", bind=True, max_retries=2, default_retry_delay=30, soft_time_limit=3500, time_limit=3600)
def cleanup_dm_orphan_files(self) -> dict:  # type: ignore[override]
    """Weekly task: delete dm/ files in MinIO not referenced by any dm_messages row."""
    result: dict = _run_async(_cleanup_dm_orphans())
    return result


async def _cleanup_dm_orphans() -> dict:
    import asyncio

    await _ensure_pool()

    from app.core.database import get_pool
    from app.core.storage import get_storage

    from app.core.config import settings

    client = get_storage()
    bucket = settings.S3_BUCKET_NAME
    pool = get_pool()

    deleted = 0
    errors = 0
    checked = 0

    # F-19: Run sync boto3 paginator in executor to avoid blocking event loop
    loop = asyncio.get_event_loop()
    paginator = client.get_paginator("list_objects_v2")

    def _list_all_dm_keys() -> list[str]:
        keys: list[str] = []
        for page in paginator.paginate(Bucket=bucket, Prefix="dm/"):
            for obj in page.get("Contents", []):
                keys.append(obj["Key"])
        return keys

    # F-66: Add timeout to prevent indefinite hang if MinIO is unresponsive
    _DM_S3_LIST_TIMEOUT = 300  # 5 minutes
    try:
        all_keys = await asyncio.wait_for(
            loop.run_in_executor(None, _list_all_dm_keys),
            timeout=_DM_S3_LIST_TIMEOUT,
        )
    except asyncio.TimeoutError:
        logger.error(
            "DM orphan cleanup: S3 listing timed out after %ds",
            _DM_S3_LIST_TIMEOUT,
        )
        return {"checked": 0, "deleted": 0, "errors": 1, "timeout": True}

    # Process in batches
    for i in range(0, len(all_keys), _DM_ORPHAN_BATCH_SIZE):
        batch = all_keys[i : i + _DM_ORPHAN_BATCH_SIZE]
        d, e = await _process_dm_orphan_batch(pool, client, bucket, batch, loop)
        checked += len(batch)
        deleted += d
        errors += e

    logger.info(
        "DM orphan file cleanup complete",
        extra={"checked": checked, "deleted": deleted, "errors": errors},
    )
    return {"checked": checked, "deleted": deleted, "errors": errors}


async def _process_dm_orphan_batch(
    pool: object, client: object, bucket: str, keys: list[str],
    loop: object | None = None,
) -> tuple[int, int]:
    """Check a batch of dm/ keys against dm_messages. Delete orphans.

    Returns (deleted_count, error_count).
    """
    import asyncio

    if loop is None:
        loop = asyncio.get_event_loop()
    deleted = 0
    errors = 0

    async with pool.acquire() as conn:  # type: ignore[union-attr]
        referenced = await conn.fetch(
            "SELECT DISTINCT attachment_key FROM dm_messages "
            "WHERE attachment_key = ANY($1::text[])",
            keys,
        )
    referenced_keys = {r["attachment_key"] for r in referenced}

    for key in keys:
        if key in referenced_keys:
            continue
        try:
            # F-19: Run sync boto3 delete in executor
            await loop.run_in_executor(  # type: ignore[union-attr]
                None,
                lambda k=key: client.delete_object(Bucket=bucket, Key=k),  # type: ignore[union-attr]
            )
            deleted += 1
            logger.info("Deleted orphan DM file", extra={"key": key})
        except Exception:
            errors += 1
            logger.warning(
                "Failed to delete orphan DM file",
                exc_info=True,
                extra={"key": key},
            )

    return deleted, errors

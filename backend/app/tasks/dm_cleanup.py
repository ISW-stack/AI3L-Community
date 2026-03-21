"""DM cleanup tasks -- expired files and messages."""

from datetime import datetime, timedelta, timezone

from loguru import logger

from app.celery_app import celery
from app.tasks.async_runner import run_async as _run_async
from app.tasks.cleanup import _ensure_pool


@celery.task(name="cleanup_dm_expired_files")
def cleanup_dm_expired_files() -> dict:
    """Delete DM file attachments past their expiry. Refund storage quota."""
    result: dict = _run_async(_cleanup_files())
    return result


async def _cleanup_files() -> dict:
    await _ensure_pool()

    from app.core.async_storage import delete_file
    from app.core.constants import DM_FILE_EXPIRY_DAYS
    from app.repositories import dm_repo, user_repo

    cutoff = datetime.now(timezone.utc) - timedelta(days=DM_FILE_EXPIRY_DAYS)

    expired = await dm_repo.find_expired_file_messages(cutoff)
    deleted = 0
    errors = 0

    for msg in expired:
        try:
            if msg.get("attachment_key"):
                await delete_file(msg["attachment_key"])
                if msg.get("attachment_size") and msg.get("sender_id"):
                    await user_repo.decrement_storage_used(msg["sender_id"], msg["attachment_size"])
            await dm_repo.clear_message_attachment(msg["id"])
            deleted += 1
        except Exception:
            errors += 1
            logger.error(
                "Failed to clean up DM attachment",
                exc_info=True,
                extra={"msg_id": str(msg["id"])},
            )

    logger.info("DM file cleanup complete", extra={"deleted": deleted, "errors": errors})
    return {"deleted": deleted, "errors": errors}


@celery.task(name="cleanup_dm_expired_text")
def cleanup_dm_expired_text() -> dict:
    """Delete DM text messages older than the retention period."""
    result: dict = _run_async(_cleanup_text())
    return result


async def _cleanup_text() -> dict:
    await _ensure_pool()

    from app.core.constants import DM_TEXT_EXPIRY_DAYS
    from app.repositories import dm_repo

    cutoff = datetime.now(timezone.utc) - timedelta(days=DM_TEXT_EXPIRY_DAYS)
    expired = await dm_repo.find_expired_text_messages(cutoff)

    if not expired:
        return {"deleted": 0}

    # Group by conversation for char count adjustment
    conv_chars: dict = {}
    msg_ids = []
    for msg in expired:
        msg_ids.append(msg["id"])
        cid = msg["conversation_id"]
        content_len = len(msg.get("content") or "")
        conv_chars[cid] = conv_chars.get(cid, 0) + content_len

    # Delete messages and decrement char counts in a single transaction
    from app.core.database import get_pool

    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            deleted = await conn.fetchval(
                "WITH d AS (DELETE FROM dm_messages WHERE id = ANY($1::uuid[]) RETURNING id) "
                "SELECT COUNT(*) FROM d",
                msg_ids,
            )
            for cid, chars in conv_chars.items():
                if chars > 0:
                    await conn.execute(
                        "UPDATE conversations SET total_chars = GREATEST(0, total_chars - $1) "
                        "WHERE id = $2",
                        chars,
                        cid,
                    )

    logger.info("DM text cleanup complete", extra={"deleted": deleted})
    return {"deleted": deleted}

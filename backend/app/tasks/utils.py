"""Shared utility functions for Celery task modules.

Consolidates duplicated helpers (_ensure_pool, _ensure_redis,
_decrement_owner_storage) that were previously copy-pasted across
cleanup.py, virustotal.py, view_sync.py, and form_autoclose.py.
"""

import uuid

from loguru import logger

from app.core.config import settings
from app.core.database import get_pool, init_db_pool
from app.core.redis import get_redis, init_redis


async def ensure_pool() -> None:
    """Ensure the asyncpg connection pool is initialised (worker may not have it)."""
    try:
        get_pool()
    except RuntimeError:
        await init_db_pool(settings.DATABASE_URL)


async def ensure_redis() -> None:
    """Ensure the Redis connection is initialised (worker may not have it)."""
    try:
        get_redis()
    except RuntimeError:
        await init_redis(settings.REDIS_URL)


async def decrement_owner_storage(storage_key: str, file_size: int) -> None:
    """Parse user_id from storage key and decrement their storage counter.

    Supports key patterns:
    - editor/{user_id}/{filename}
    - forms/{...}/{user_id}/{filename}
    - dm/{user_id}/{filename}
    """
    from app.repositories import user_repo

    if not storage_key or "/" not in storage_key:
        logger.warning("Invalid storage key format", extra={"key": storage_key})
        return

    await ensure_pool()

    parts = storage_key.split("/")
    owner_id_str: str | None = None

    # Try to find the user UUID in common key patterns
    for part in parts[1:]:  # skip prefix like "editor", "forms", "dm"
        try:
            uuid.UUID(part)
            owner_id_str = part
            break
        except ValueError:
            continue

    if not owner_id_str:
        logger.warning(
            "Could not extract user_id from storage key",
            extra={"key": storage_key},
        )
        return

    try:
        owner_uuid = uuid.UUID(owner_id_str)
        # M-04 Equivalent: Retry storage decrement in centralized utility
        for attempt in range(3):
            try:
                await user_repo.increment_storage_used(owner_uuid, -file_size)
                logger.info(
                    "Decremented storage for user after file deletion",
                    extra={"user_id": owner_id_str, "key": storage_key, "size": file_size},
                )
                break
            except Exception:
                if attempt == 2:
                    logger.error(
                        "Failed to decrement storage after file deletion - persistence failure",
                        extra={"key": storage_key, "user_id": owner_id_str, "compensation_required": True},
                        exc_info=True,
                    )
                else:
                    import asyncio
                    await asyncio.sleep(1)
    except (ValueError, Exception) as e:
        logger.warning(
            "Failed to decrement storage after file deletion",
            extra={"key": storage_key, "error": str(e)},
        )

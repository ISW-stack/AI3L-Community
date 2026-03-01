"""Celery task: anonymize stale guest accounts (older than 24 hours)."""

import asyncio

from loguru import logger

from app.celery_app import celery


@celery.task
def cleanup_stale_guests() -> dict:
    """Anonymize guest users whose accounts are older than 24 hours."""
    return asyncio.run(_cleanup())


async def _cleanup() -> dict:
    from app.core.database import get_pool, init_pool

    # Ensure pool is available in worker context
    try:
        pool = get_pool()
    except RuntimeError:
        await init_pool()
        pool = get_pool()

    async with pool.acquire() as conn:
        result = await conn.execute("""
            UPDATE users SET
                username = 'Deleted_Guest_' || LEFT(id::text, 8),
                display_name = 'Deleted Guest',
                password_hash = 'ANONYMIZED',
                avatar_url = NULL,
                orcid = NULL,
                affiliation = NULL,
                bio = NULL,
                is_deleted = true,
                updated_at = NOW()
            WHERE role = 'GUEST'
              AND is_deleted = false
              AND created_at < NOW() - INTERVAL '24 hours'
            """)

    # Parse "UPDATE N"
    count = int(result.split()[-1]) if result else 0
    logger.info("Guest cleanup completed", extra={"anonymized": count})
    return {"anonymized": count}

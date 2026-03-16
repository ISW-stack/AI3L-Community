"""Celery task: Auto-close forms past their deadline.

Periodically checks for forms whose deadline has passed and marks them as closed.
"""

from typing import Any

from loguru import logger

from app.celery_app import celery
from app.core.config import settings
from app.core.database import get_pool, init_db_pool
from app.tasks.async_runner import run_async as _run_async


async def _ensure_pool() -> None:
    try:
        get_pool()
    except RuntimeError:
        await init_db_pool(settings.DATABASE_URL)


async def _close_expired_forms() -> list[str]:
    """Find active forms past their deadline and mark them as closed.

    Returns list of closed form IDs.
    """
    await _ensure_pool()
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            UPDATE forms
            SET is_closed = true, updated_at = NOW()
            WHERE deadline < NOW()
              AND is_closed = false
              AND is_deleted = false
            RETURNING id
            """)
        return [str(row["id"]) for row in rows]


@celery.task(name="auto_close_expired_forms", bind=True, max_retries=1)
def auto_close_expired_forms(self: Any) -> dict[str, Any]:
    """Periodic task: auto-close forms whose deadline has passed."""

    async def _run() -> dict[str, Any]:
        closed_ids = await _close_expired_forms()
        return {"closed_count": len(closed_ids), "closed_ids": closed_ids}

    result: dict[str, Any] = _run_async(_run())
    if result["closed_count"] > 0:
        logger.info(
            "Auto-closed %d expired form(s): %s",
            result["closed_count"],
            result["closed_ids"],
        )
    else:
        logger.debug("No expired forms to close")
    return result

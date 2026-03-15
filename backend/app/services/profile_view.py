"""Service layer for profile view tracking."""

import uuid

from loguru import logger

from app.core.database import get_pool
from app.repositories import profile_view_repo


async def record_profile_view(
    pool: object,
    redis: object,
    profile_id: str,
    viewer_id: str,
) -> None:
    """Record a profile view with Redis dedup.

    Skips self-views and uses Redis to avoid excessive DB writes.
    """
    # Skip self-views
    if profile_id == viewer_id:
        return

    profile_uuid = uuid.UUID(profile_id)
    viewer_uuid = uuid.UUID(viewer_id)

    # Redis dedup: one view per viewer per profile per 24 hours
    from app.core.constants import PROFILE_VIEW_DEDUP_TTL
    from app.core.redis import get_redis

    redis = get_redis()
    dedup_key = f"profile_viewed:{profile_id}:{viewer_id}"
    is_new = await redis.set(dedup_key, "1", ex=PROFILE_VIEW_DEDUP_TTL, nx=True)
    if not is_new:
        return  # Already viewed recently

    pool = get_pool()
    try:
        async with pool.acquire() as conn:
            async with conn.transaction():
                # Upsert view record and check if it's a new viewer
                is_new_viewer = await profile_view_repo.upsert_view(
                    conn, profile_uuid, viewer_uuid
                )
                # Always increment total counter
                await profile_view_repo.increment_total_counter(conn, profile_uuid)
                # Only increment unique counter for new viewers
                if is_new_viewer:
                    await profile_view_repo.increment_unique_counter(conn, profile_uuid)
    except Exception:
        logger.warning(
            "Failed to record profile view",
            extra={"profile_id": profile_id, "viewer_id": viewer_id},
            exc_info=True,
        )

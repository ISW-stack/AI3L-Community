import time

from fastapi import APIRouter

from app.repositories import dashboard_repo

router = APIRouter(prefix="/public", tags=["public"])

# Simple in-memory cache (5 minutes)
_stats_cache: dict = {}
_CACHE_TTL = 300  # 5 minutes


@router.get("/stats")
async def get_public_stats() -> dict:
    global _stats_cache
    now = time.monotonic()
    if _stats_cache and now - _stats_cache.get("_ts", 0) < _CACHE_TTL:
        return {k: v for k, v in _stats_cache.items() if k != "_ts"}

    member_count = await dashboard_repo.count_users()
    post_count = await dashboard_repo.count_posts()
    sig_count = await dashboard_repo.count_sigs()

    stats = {
        "member_count": member_count,
        "post_count": post_count,
        "sig_count": sig_count,
    }
    # Atomic reference swap — avoids brief inconsistency window
    _stats_cache = {**stats, "_ts": now}
    return stats

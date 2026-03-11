"""Admin dashboard stats service."""

from loguru import logger

from app.repositories import dashboard_repo


async def get_dashboard_stats() -> dict:
    """Return counts for the admin dashboard.

    Each stat is fetched independently so a single query failure does not
    crash the entire dashboard.
    """
    stat_queries = [
        ("users", dashboard_repo.count_users()),
        ("posts", dashboard_repo.count_posts()),
        ("sigs", dashboard_repo.count_sigs()),
        ("forms", dashboard_repo.count_forms()),
        ("pending_reports", dashboard_repo.count_pending_reports()),
        ("pending_applications", dashboard_repo.count_pending_applications()),
    ]
    stats: dict = {}
    for key, coro in stat_queries:
        try:
            stats[key] = await coro
        except Exception:
            logger.warning(f"Dashboard stat '{key}' query failed", exc_info=True)
            stats[key] = 0
    return stats

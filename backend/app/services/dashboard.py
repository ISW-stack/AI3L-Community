"""Admin dashboard stats service."""

from app.repositories import dashboard_repo


async def get_dashboard_stats() -> dict:
    """Return counts for the admin dashboard."""
    return {
        "users": await dashboard_repo.count_users(),
        "posts": await dashboard_repo.count_posts(),
        "sigs": await dashboard_repo.count_sigs(),
        "forms": await dashboard_repo.count_forms(),
        "pending_reports": await dashboard_repo.count_pending_reports(),
        "pending_applications": await dashboard_repo.count_pending_applications(),
    }

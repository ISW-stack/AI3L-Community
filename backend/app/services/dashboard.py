"""Admin dashboard stats service."""

from app.core.database import get_pool


async def get_dashboard_stats() -> dict:
    """Return counts for the admin dashboard."""
    pool = get_pool()
    async with pool.acquire() as conn:
        users = await conn.fetchval("SELECT COUNT(*) FROM users WHERE is_deleted = FALSE")
        posts = await conn.fetchval("SELECT COUNT(*) FROM posts WHERE is_deleted = FALSE")
        sigs = await conn.fetchval("SELECT COUNT(*) FROM sigs WHERE is_deleted = FALSE")
        forms = await conn.fetchval("SELECT COUNT(*) FROM forms WHERE is_deleted = FALSE")
        pending_reports = await conn.fetchval(
            "SELECT COUNT(*) FROM post_reports WHERE status = 'PENDING'"
        )
        pending_applications = await conn.fetchval(
            "SELECT COUNT(*) FROM membership_applications WHERE status = 'PENDING'"
        )

    return {
        "users": users or 0,
        "posts": posts or 0,
        "sigs": sigs or 0,
        "forms": forms or 0,
        "pending_reports": pending_reports or 0,
        "pending_applications": pending_applications or 0,
    }

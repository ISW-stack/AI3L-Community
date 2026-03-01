from app.core.database import get_pool


async def count_users() -> int:
    pool = get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchval("SELECT COUNT(*) FROM users WHERE is_deleted = FALSE") or 0


async def count_posts() -> int:
    pool = get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchval("SELECT COUNT(*) FROM posts WHERE is_deleted = FALSE") or 0


async def count_sigs() -> int:
    pool = get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchval("SELECT COUNT(*) FROM sigs WHERE is_deleted = FALSE") or 0


async def count_forms() -> int:
    pool = get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchval("SELECT COUNT(*) FROM forms WHERE is_deleted = FALSE") or 0


async def count_pending_reports() -> int:
    pool = get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchval("SELECT COUNT(*) FROM post_reports WHERE status = 'PENDING'") or 0


async def count_pending_applications() -> int:
    pool = get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchval("SELECT COUNT(*) FROM membership_applications WHERE status = 'PENDING'") or 0

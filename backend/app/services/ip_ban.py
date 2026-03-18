import uuid
from datetime import datetime

from app.core.redis import get_redis
from app.repositories import ip_ban_repo


async def is_ip_banned(ip: str) -> bool:
    """Check if an IP is banned. Uses Redis cache (300s TTL) before hitting DB."""
    redis = get_redis()
    cache_key = f"ip_ban:{ip}"
    cached = await redis.get(cache_key)
    if cached is not None:
        return cached == "1"

    ban = await ip_ban_repo.find_by_ip(ip)
    await redis.set(cache_key, "1" if ban else "0", ex=300)
    return ban is not None


async def ban_ip(
    ip: str,
    reason: str,
    banned_by: uuid.UUID,
    expires_at: datetime | None = None,
) -> dict:
    """Create an IP ban and invalidate the Redis cache for that IP."""
    ban_id = uuid.uuid4()
    ban = await ip_ban_repo.create(ban_id, ip, reason, banned_by, expires_at)

    # Invalidate cache so the ban takes effect immediately
    redis = get_redis()
    await redis.delete(f"ip_ban:{ip}")

    return ban


async def unban_ip(ban_id: uuid.UUID) -> bool:
    """Remove an IP ban by ID and invalidate the cache.

    We need to look up the IP first so we can clear its cache entry.
    """
    # We need to find the ban to get its IP for cache invalidation.
    # Since we only have the ban_id, query the DB directly.
    from app.core.database import get_pool

    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT ip_address FROM ip_bans WHERE id = $1", ban_id
        )

    deleted = await ip_ban_repo.delete(ban_id)

    if deleted and row:
        redis = get_redis()
        await redis.delete(f"ip_ban:{row['ip_address']}")

    return deleted


async def list_ip_bans(
    page: int = 1, page_size: int = 50
) -> tuple[list[dict], int]:
    """Return paginated list of all IP bans."""
    return await ip_ban_repo.list_all(page, page_size)

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
        return bool(cached == "1")

    ban = await ip_ban_repo.find_by_ip(ip)
    await redis.set(cache_key, "1" if ban else "0", ex=300)
    return bool(ban is not None)


async def ban_ip(
    ip: str,
    reason: str,
    banned_by: uuid.UUID,
    expires_at: datetime | None = None,
) -> dict:
    """Create an IP ban and invalidate the Redis cache for that IP."""
    ban_id = uuid.uuid4()
    ban = await ip_ban_repo.create(ban_id, ip, reason, banned_by, expires_at)

    # Set cache to "banned" immediately so the ban takes effect without a DB round-trip
    redis = get_redis()
    await redis.set(f"ip_ban:{ip}", "1", ex=300)

    return ban


async def unban_ip(ban_id: uuid.UUID) -> bool:
    """Remove an IP ban by ID and invalidate the cache."""
    from app.core.database import get_pool

    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "DELETE FROM ip_bans WHERE id = $1 RETURNING ip_address",
            ban_id,
        )
    if row:
        # Explicitly cache "not banned" so a stale "1" never lingers
        redis = get_redis()
        await redis.set(f"ip_ban:{row['ip_address']}", "0", ex=300)
        return True
    return False


async def list_ip_bans(page: int = 1, page_size: int = 50) -> tuple[list[dict], int]:
    """Return paginated list of all IP bans."""
    return await ip_ban_repo.list_all(page, page_size)

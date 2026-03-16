"""Redis-cached bilateral block set helpers."""

import logging
import uuid

logger = logging.getLogger(__name__)


async def get_blocked_user_ids(redis, user_id: str, pool=None) -> set[str]:
    """Get bilateral block set from Redis. Falls back to DB on miss when pool is provided."""
    key = f"block:set:{user_id}"
    members = await redis.smembers(key)
    if members:
        return {m.decode() if isinstance(m, bytes) else m for m in members}

    # Redis miss — fall back to DB if pool is available
    if pool is not None:
        try:
            async with pool.acquire() as conn:
                rows = await conn.fetch(
                    "SELECT blocker_id, blocked_id FROM blocks WHERE blocker_id=$1 OR blocked_id=$1",  # noqa: E501
                    uuid.UUID(user_id),
                )
            if rows:
                blocked: set[str] = set()
                pipe = redis.pipeline()
                for row in rows:
                    blocker = str(row["blocker_id"])
                    blocked_uid = str(row["blocked_id"])
                    # Add the *other* user to the set
                    other = blocked_uid if blocker == user_id else blocker
                    blocked.add(other)
                    pipe.sadd(key, other)
                pipe.expire(key, 3600)  # Re-warm cache with 1h TTL
                await pipe.execute()
                return blocked
        except Exception:
            logger.warning("DB fallback for block cache failed", exc_info=True)

    return set()


async def warmup_block_cache(pool, redis) -> None:
    """Load all block relationships into Redis on app startup."""
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT blocker_id, blocked_id FROM blocks")

    if not rows:
        return

    pipe = redis.pipeline()
    for row in rows:
        blocker = str(row["blocker_id"])
        blocked = str(row["blocked_id"])
        pipe.sadd(f"block:set:{blocker}", blocked)
        pipe.sadd(f"block:set:{blocked}", blocker)
    await pipe.execute()
    logger.info("Block cache warmed: %d block records", len(rows))


async def update_block_cache(redis, blocker_id: str, blocked_id: str, *, added: bool) -> None:
    """Update Redis block sets when a block is added/removed."""
    if added:
        pipe = redis.pipeline()
        pipe.sadd(f"block:set:{blocker_id}", blocked_id)
        pipe.sadd(f"block:set:{blocked_id}", blocker_id)
        await pipe.execute()
    else:
        pipe = redis.pipeline()
        pipe.srem(f"block:set:{blocker_id}", blocked_id)
        pipe.srem(f"block:set:{blocked_id}", blocker_id)
        await pipe.execute()


def build_block_exclusion_clause(
    blocked_ids: set[str], user_column: str, param_idx: int
) -> tuple[str, list]:
    """Build SQL exclusion clause for blocked users.

    Returns (sql_fragment, params) where sql_fragment is like
    'AND p.user_id != ALL($3::uuid[])' and params is [list_of_uuids].
    """
    _ALLOWED_COLUMNS = {
        "p.user_id",
        "cm.user_id",
        "n.trigger_user_id",
        "f.created_by",
        "ap.uploaded_by",
        "ac.user_id",
        "fr.user_id",
    }
    if user_column not in _ALLOWED_COLUMNS:
        raise ValueError(f"Invalid column for block exclusion: {user_column}")

    if not blocked_ids:
        return "", []

    uuid_list = [uuid.UUID(uid) for uid in blocked_ids]
    return f" AND {user_column} != ALL(${param_idx}::uuid[])", [uuid_list]

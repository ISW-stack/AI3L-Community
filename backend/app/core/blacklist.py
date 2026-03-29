"""Redis-cached bilateral block set helpers."""

import logging
import uuid
from typing import Any

import asyncpg

logger = logging.getLogger(__name__)


async def get_blocked_user_ids(
    redis: Any, user_id: str, pool: asyncpg.Pool | None = None
) -> set[str]:
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


async def warmup_block_cache(pool: asyncpg.Pool, redis: Any) -> None:
    """Load all block relationships into Redis on app startup (batched to limit memory)."""
    _BATCH_SIZE = 5000
    total_loaded = 0
    offset = 0

    while True:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT blocker_id, blocked_id FROM blocks "
                "ORDER BY blocker_id, blocked_id LIMIT $1 OFFSET $2",
                _BATCH_SIZE,
                offset,
            )

        if not rows:
            break

        pipe = redis.pipeline()
        seen_keys: set[str] = set()
        for row in rows:
            blocker = str(row["blocker_id"])
            blocked = str(row["blocked_id"])
            key_blocker = f"block:set:{blocker}"
            key_blocked = f"block:set:{blocked}"
            pipe.sadd(key_blocker, blocked)
            pipe.sadd(key_blocked, blocker)
            seen_keys.add(key_blocker)
            seen_keys.add(key_blocked)
        for key in seen_keys:
            pipe.expire(key, 86400)  # 24h TTL
        await pipe.execute()

        total_loaded += len(rows)
        offset += _BATCH_SIZE

        if len(rows) < _BATCH_SIZE:
            break

    if total_loaded:
        logger.info("Block cache warmed: %d block records", total_loaded)


async def update_block_cache(redis: Any, blocker_id: str, blocked_id: str, *, added: bool) -> None:
    """Update Redis block sets when a block is added/removed."""
    key1 = f"block:set:{blocker_id}"
    key2 = f"block:set:{blocked_id}"
    if added:
        pipe = redis.pipeline()
        pipe.sadd(key1, blocked_id)
        pipe.sadd(key2, blocker_id)
        pipe.expire(key1, 86400)
        pipe.expire(key2, 86400)
        await pipe.execute()
    else:
        pipe = redis.pipeline()
        pipe.srem(key1, blocked_id)
        pipe.srem(key2, blocker_id)
        pipe.expire(key1, 86400)
        pipe.expire(key2, 86400)
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

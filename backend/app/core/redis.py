from redis.asyncio import Redis
from loguru import logger

_redis: Redis | None = None


async def init_redis(url: str) -> Redis:
    global _redis
    _redis = Redis.from_url(
        url,
        decode_responses=True,
        socket_keepalive=True,
    )
    logger.info("Redis client initialized")
    return _redis


async def close_redis() -> None:
    global _redis
    if _redis:
        await _redis.close()
        _redis = None
        logger.info("Redis client closed")


def get_redis() -> Redis:
    if _redis is None:
        raise RuntimeError("Redis client is not initialized. Call init_redis() first.")
    return _redis

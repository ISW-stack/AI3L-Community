from loguru import logger
from redis.asyncio import Redis

_redis: Redis | None = None


async def init_redis(url: str) -> Redis:
    global _redis
    # TLS not used for same-host Docker deployment; use rediss:// for remote Redis
    _redis = Redis.from_url(
        url,
        decode_responses=True,
        socket_keepalive=True,
        socket_timeout=10,
        socket_connect_timeout=5,
        retry_on_timeout=True,
        max_connections=20,
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

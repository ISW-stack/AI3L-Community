from app.core.redis import get_redis


async def check_rate_limit(key: str, max_count: int, window_seconds: int) -> bool:
    """Check rate limit using Redis INCR + EXPIRE pipeline.

    Returns True if within limit, False if exceeded.
    """
    redis = get_redis()
    pipe = redis.pipeline()
    pipe.incr(key)
    pipe.expire(key, window_seconds)
    results = await pipe.execute()
    count = results[0]
    return count <= max_count

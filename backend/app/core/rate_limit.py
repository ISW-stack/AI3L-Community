from typing import Any

from app.core.redis import get_redis

_LUA_RATE_LIMIT = """
local key = KEYS[1]
local max_count = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local current = redis.call('INCR', key)
if current == 1 then
    redis.call('EXPIRE', key, window)
end
if current > max_count then
    return 0
end
return 1
"""


async def check_rate_limit(key: str, max_count: int, window_seconds: int) -> bool:
    """Check rate limit using atomic Lua script (INCR + EXPIRE in one round-trip).

    Returns True if within limit, False if exceeded.
    """
    redis = get_redis()
    result: Any = await redis.eval(  # type: ignore[misc]
        _LUA_RATE_LIMIT, 1, key, str(max_count), str(window_seconds)
    )
    return bool(result == 1)

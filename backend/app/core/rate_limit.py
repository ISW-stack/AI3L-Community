import ipaddress
from typing import Any, Awaitable, cast

from fastapi import Request

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


def get_client_ip(request: Request) -> str | None:
    """Extract client IP from request, checking proxy headers first.

    Priority:
    1. X-Real-IP (set by nginx from trusted proxy)
    2. X-Forwarded-For (first IP in the list — the original client)
    3. request.client.host

    Returns None if no IP can be determined.
    """
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        ip = real_ip.strip()
        if _is_valid_ip(ip):
            return ip

    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        ip = forwarded_for.split(",")[0].strip()
        if _is_valid_ip(ip):
            return ip

    if request.client:
        return request.client.host

    return None


def _is_valid_ip(ip: str) -> bool:
    """Validate that a string is a valid IPv4 or IPv6 address."""
    try:
        ipaddress.ip_address(ip)
        return True
    except ValueError:
        return False


async def check_rate_limit(key: str, max_count: int, window_seconds: int) -> bool:
    """Check rate limit using atomic Lua script (INCR + EXPIRE in one round-trip).

    Returns True if within limit, False if exceeded.
    """
    redis = get_redis()
    result: Any = await cast(
        Awaitable[Any], redis.eval(_LUA_RATE_LIMIT, 1, key, str(max_count), str(window_seconds))
    )
    return bool(result == 1)

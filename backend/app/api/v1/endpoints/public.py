import json

from fastapi import APIRouter, Request

from app.core.errors import AppError, ErrorCode
from app.core.rate_limit import check_rate_limit, get_client_ip
from app.core.redis import get_redis
from app.repositories import dashboard_repo

router = APIRouter(prefix="/public", tags=["public"])

_CACHE_KEY = "public:stats"
_CACHE_TTL = 300  # 5 minutes


@router.get("/stats")
async def get_public_stats(request: Request) -> dict:
    ip = get_client_ip(request) or "unknown"
    if not await check_rate_limit(f"rl:public_stats:{ip}", 30, 60):
        raise AppError(ErrorCode.SYS_429, 429, "Too many requests.")

    redis = get_redis()
    cached = await redis.get(_CACHE_KEY)
    if cached:
        return json.loads(cached)

    member_count = await dashboard_repo.count_users()
    post_count = await dashboard_repo.count_posts()
    sig_count = await dashboard_repo.count_sigs()

    stats = {
        "member_count": member_count,
        "post_count": post_count,
        "sig_count": sig_count,
    }
    await redis.set(_CACHE_KEY, json.dumps(stats), ex=_CACHE_TTL)
    return stats

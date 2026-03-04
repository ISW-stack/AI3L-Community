import time

from fastapi import APIRouter

from app.core.database import get_pool
from app.core.redis import get_redis
from app.schemas.health import DependencyStatus, HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    dependencies: list[DependencyStatus] = []
    overall_healthy = True

    # Check PostgreSQL
    try:
        pool = get_pool()
        start = time.perf_counter()
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        latency = (time.perf_counter() - start) * 1000
        dependencies.append(
            DependencyStatus(name="postgresql", status="healthy", latency_ms=round(latency, 2))
        )
    except Exception:
        overall_healthy = False
        dependencies.append(
            DependencyStatus(name="postgresql", status="unhealthy", error="connection failed")
        )

    # Check Redis
    try:
        redis = get_redis()
        start = time.perf_counter()
        await redis.ping()
        latency = (time.perf_counter() - start) * 1000
        dependencies.append(
            DependencyStatus(name="redis", status="healthy", latency_ms=round(latency, 2))
        )
    except Exception:
        overall_healthy = False
        dependencies.append(
            DependencyStatus(name="redis", status="unhealthy", error="connection failed")
        )

    return HealthResponse(
        status="healthy" if overall_healthy else "unhealthy",
        dependencies=dependencies,
    )

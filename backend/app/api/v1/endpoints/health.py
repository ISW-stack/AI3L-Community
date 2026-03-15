import time

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.database import get_pool
from app.core.deps import require_role
from app.core.redis import get_redis
from app.schemas.health import DependencyStatus, HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health/live")
async def liveness() -> JSONResponse:
    """Lightweight liveness probe — no external dependency checks."""
    return JSONResponse(content={"status": "ok"}, status_code=200)


@router.get("/health", response_model=HealthResponse)
async def health_check(
    current_user: dict = Depends(require_role("SUPER_ADMIN")),
) -> HealthResponse:
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

    # Check MinIO/Storage
    try:
        from app.core.storage import get_storage

        start = time.perf_counter()
        client = get_storage()
        client.head_bucket(Bucket=settings.MINIO_BUCKET_NAME)
        latency = (time.perf_counter() - start) * 1000
        dependencies.append(
            DependencyStatus(name="minio", status="healthy", latency_ms=round(latency, 2))
        )
    except Exception:
        overall_healthy = False
        dependencies.append(
            DependencyStatus(name="minio", status="unhealthy", error="connection failed")
        )

    return HealthResponse(
        status="healthy" if overall_healthy else "unhealthy",
        dependencies=dependencies,
    )

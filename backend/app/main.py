from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app.core.config import settings
from app.core.database import close_db_pool, init_db_pool
from app.core.logging import setup_logging
from app.core.redis import close_redis, init_redis
from app.core.storage import init_storage
from app.api.v1.router import api_v1_router


async def bootstrap_super_admin() -> None:
    """Create initial Super Admin from .env if it doesn't exist yet."""
    from app.services.user import create_user, user_exists_by_username

    username = settings.SUPER_ADMIN_USERNAME
    password = settings.SUPER_ADMIN_PASSWORD

    if await user_exists_by_username(username):
        logger.info("Super Admin already exists, skipping bootstrap")
        return

    await create_user(
        username=username,
        password=password,
        role="SUPER_ADMIN",
        display_name="Super Admin",
    )
    logger.info("Super Admin bootstrapped from .env", extra={"username": username})


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Startup
    setup_logging(level=settings.LOG_LEVEL, fmt=settings.LOG_FORMAT)
    logger.info("Starting AI3L Community API")

    await init_db_pool(settings.DATABASE_URL)
    await init_redis(settings.REDIS_URL)

    try:
        init_storage()
    except Exception as e:
        logger.warning(f"Storage init skipped: {e}")

    # Bootstrap Super Admin (requires DB to be ready)
    try:
        await bootstrap_super_admin()
    except Exception as e:
        logger.warning(f"Super Admin bootstrap skipped: {e}")

    logger.info("All dependencies initialized")
    yield

    # Shutdown
    logger.info("Shutting down AI3L Community API")
    await close_redis()
    await close_db_pool()
    logger.info("All dependencies closed")


app = FastAPI(
    title="AI3L Community API",
    version="0.1.0",
    docs_url="/docs" if settings.is_development else None,
    redoc_url="/redoc" if settings.is_development else None,
    openapi_url="/openapi.json" if settings.is_development else None,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS_LIST,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["*"],
)

from app.middleware.idempotency import IdempotencyMiddleware  # noqa: E402

app.add_middleware(IdempotencyMiddleware)

app.include_router(api_v1_router, prefix="/api/v1")

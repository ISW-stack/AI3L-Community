from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app.core.config import settings
from app.core.database import close_db_pool, init_db_pool
from app.core.logging import setup_logging
from app.core.redis import close_redis, init_redis
from app.api.v1.router import api_v1_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Startup
    setup_logging(level=settings.LOG_LEVEL, fmt=settings.LOG_FORMAT)
    logger.info("Starting AI3L Community API")

    await init_db_pool(settings.DATABASE_URL)
    await init_redis(settings.REDIS_URL)

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

app.include_router(api_v1_router, prefix="/api/v1")

import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

# Datadog tracing — must be patched before FastAPI import
try:
    from app.core.config import settings as _early_settings

    if _early_settings.DD_TRACE_ENABLED:
        from ddtrace import patch_all

        patch_all()
except Exception:
    pass

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api.v1.router import api_v1_router
from app.core.config import settings
from app.core.csrf import CSRFMiddleware
from app.core.database import close_db_pool, init_db_pool
from app.core.logging import setup_logging
from app.core.redis import close_redis, init_redis
from app.core.storage import close_storage, init_storage


async def bootstrap_super_admin() -> None:
    """Create or sync Super Admin credentials from .env."""
    from app.core.security import async_hash_password
    from app.repositories import user_repo
    from app.services.user import create_user, user_exists_by_username

    username = settings.SUPER_ADMIN_USERNAME
    password = settings.SUPER_ADMIN_PASSWORD

    if not await user_exists_by_username(username):
        await create_user(
            username=username,
            password=password,
            role="SUPER_ADMIN",
            display_name="Super Admin",
        )
        logger.info("Super Admin bootstrapped from .env", extra={"username": username})
    else:
        # Sync password so .env credentials are always authoritative
        user = await user_repo.find_by_username(username)
        if user:
            new_hash = await async_hash_password(password)
            await user_repo.update_password_hash(user["id"], new_hash)
            logger.info("Super Admin password synced from .env", extra={"username": username})


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Startup
    setup_logging(level=settings.LOG_LEVEL, fmt=settings.LOG_FORMAT)
    logger.info("Starting AI3L Community API")

    # Sentry SDK initialization
    if settings.SENTRY_DSN:
        try:
            import sentry_sdk

            sentry_sdk.init(
                dsn=settings.SENTRY_DSN,
                traces_sample_rate=settings.SENTRY_TRACES_SAMPLE_RATE,
                environment=settings.FASTAPI_ENV,
            )
            logger.info("Sentry SDK initialized")
        except Exception as e:
            logger.warning(f"Sentry init failed: {e}")

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

    # Register event bus handlers
    from app.event_handlers import register_all

    register_all()

    # Start WebSocket Redis Pub/Sub subscriber
    from app.api.v1.endpoints.ws import start_redis_subscriber, stop_redis_subscriber

    try:
        await start_redis_subscriber()
    except Exception as e:
        logger.warning(f"WebSocket Redis subscriber start skipped: {e}")

    logger.info("All dependencies initialized")

    # Production security checks — abort startup on insecure defaults
    if not settings.is_development:
        _defaults = {
            "SECRET_KEY": "changeme_secret_key_at_least_32_characters_long",
            "POSTGRES_PASSWORD": "changeme_postgres",
            "REDIS_PASSWORD": "changeme_redis",
            "MINIO_ROOT_PASSWORD": "changeme_minio",
            "JWT_SECRET_KEY": "changeme_jwt_secret_key",
            "SUPER_ADMIN_PASSWORD": "changeme_admin",
        }
        _insecure = False
        for key, default in _defaults.items():
            if getattr(settings, key) == default:
                logger.error(
                    f"SECURITY: {key} is using default value — change it in .env before deploying"
                )
                _insecure = True
        if not settings.COOKIE_SECURE:
            logger.error(
                "SECURITY: COOKIE_SECURE is False — cookies will be sent over HTTP. Set COOKIE_SECURE=true in .env for production"  # noqa: E501
            )
            _insecure = True
        if _insecure:
            logger.error("Aborting startup due to insecure production configuration.")
            sys.exit(1)

    yield

    # Shutdown
    logger.info("Shutting down AI3L Community API")
    try:
        await stop_redis_subscriber()
    except Exception:
        pass
    close_storage()
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
    allow_headers=["Content-Type", "X-CSRF-Token", "X-Idempotency-Key"],
)

# CSRF double-submit cookie middleware (after CORS so preflight is handled first)
app.add_middleware(CSRFMiddleware, header_name=settings.CSRF_HEADER_NAME)

from app.middleware.idempotency import IdempotencyMiddleware  # noqa: E402

app.add_middleware(IdempotencyMiddleware)

# Trusted host middleware — prevents Host header attacks in production
if not settings.is_development:
    _trusted = [h.strip() for h in settings.TRUSTED_HOSTS.split(",") if h.strip()]
    if _trusted:
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=_trusted)
    else:
        logger.warning("TRUSTED_HOSTS not configured — TrustedHostMiddleware disabled")

app.include_router(api_v1_router, prefix="/api/v1")

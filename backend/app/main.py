import asyncio
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

# Datadog tracing — must be patched before FastAPI import
try:
    from app.core.config import settings as _early_settings

    if _early_settings.DD_TRACE_ENABLED:
        from ddtrace import patch_all

        patch_all()
except ImportError:
    pass  # ddtrace not installed
except Exception as e:
    import logging

    logging.getLogger(__name__).warning("Datadog tracing init failed: %s", e)

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger
from starlette.middleware.base import RequestResponseEndpoint
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.responses import Response

from app.api.v1.router import api_v1_router
from app.core.config import settings
from app.core.csrf import CSRFMiddleware
from app.core.database import close_db_pool, init_db_pool
from app.core.logging import setup_logging
from app.core.logging_utils import mask_pii
from app.core.redis import close_redis, init_redis
from app.core.storage import close_storage, init_storage


async def bootstrap_super_admin() -> None:
    """Create or sync Super Admin credentials from .env."""
    from app.core.security import async_hash_password, async_verify_password
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
        logger.info("Super Admin bootstrapped from .env", extra={"username": mask_pii(username)})
    else:
        # Sync password so .env credentials are always authoritative
        user = await user_repo.find_by_username(username)
        if user:
            # Only rehash if the .env password doesn't match the stored hash
            if not await async_verify_password(password, user["password_hash"]):
                new_hash = await async_hash_password(password)
                await user_repo.update_password_hash(user["id"], new_hash)
                logger.info(
                    "Super Admin password synced from .env", extra={"username": mask_pii(username)}
                )
            else:
                logger.debug(
                    "Super Admin password unchanged, skipping rehash",
                    extra={"username": mask_pii(username)},
                )


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
        except Exception:
            logger.warning("Sentry init failed", exc_info=True)

    await init_db_pool(settings.DATABASE_URL)
    await init_redis(settings.REDIS_URL)

    try:
        init_storage()
    except Exception:
        logger.warning("Storage init skipped", exc_info=True)

    # Bootstrap Super Admin (requires DB to be ready)
    try:
        await bootstrap_super_admin()
    except Exception:
        logger.warning("Super Admin bootstrap skipped", exc_info=True)

    # Warm up block cache (requires DB + Redis)
    try:
        from app.core.blacklist import warmup_block_cache
        from app.core.database import get_pool as _get_pool
        from app.core.redis import get_redis as _get_redis

        await warmup_block_cache(_get_pool(), _get_redis())
    except Exception:
        logger.warning("Block cache warmup skipped", exc_info=True)

    # Register event bus handlers
    from app.event_handlers import register_all

    register_all()

    # Start WebSocket Redis Pub/Sub subscriber
    from app.api.v1.endpoints.ws import start_redis_subscriber, stop_redis_subscriber

    try:
        await start_redis_subscriber()
    except Exception:
        logger.warning("WebSocket Redis subscriber start skipped", exc_info=True)

    logger.info("All dependencies initialized")

    # Development warning — nudge developer if JWT secret is still the default
    if settings.is_development:
        _dev_defaults = {
            "JWT_SECRET_KEY": "changeme_jwt_secret_key",
            "SECRET_KEY": "changeme_secret_key_at_least_32_characters_long",
        }
        for key, default in _dev_defaults.items():
            if getattr(settings, key) == default:
                logger.warning(
                    f"SECURITY: {key} is still using the default value. "
                    "Generate a strong random secret with: "
                    'python -c "import secrets; print(secrets.token_urlsafe(48))"'
                )

    # Production security checks — abort startup on insecure defaults
    if not settings.is_development:
        _defaults = {
            "SECRET_KEY": "changeme_secret_key_at_least_32_characters_long",
            "POSTGRES_PASSWORD": "changeme_postgres",
            "REDIS_PASSWORD": "changeme_redis",
            "S3_SECRET_ACCESS_KEY": "changeme_s3",
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
        if not settings.S3_PUBLIC_URL:
            logger.error("SECURITY: S3_PUBLIC_URL must be set in production")
            _insecure = True
        if _insecure:
            logger.error("Aborting startup due to insecure production configuration.")
            sys.exit(1)

    yield

    # Shutdown
    logger.info("Shutting down AI3L Community API")
    try:
        await stop_redis_subscriber()
    except Exception as e:
        logger.warning("Redis subscriber cleanup failed: %s", e)
    close_storage()
    await close_redis()
    await close_db_pool()
    logger.info("All dependencies closed")


MAX_REQUEST_BODY_SIZE = 10 * 1024 * 1024  # 10 MB

# MO-17: Limit concurrent large uploads to bound peak memory
_UPLOAD_SEMAPHORE = asyncio.Semaphore(3)

_UPLOAD_BODY_LIMITS: dict[str, int] = {
    "/api/v1/albums/": 50 * 1024 * 1024,  # 50 MB
    "/api/v1/dm/": 10 * 1024 * 1024,  # 10 MB (DM_MAX_ATTACHMENT_SIZE)
    "/api/v1/files/": 10 * 1024 * 1024,  # 10 MB (MAX_EDITOR_FILE_SIZE)
}


def _get_body_limit(path: str) -> int:
    """Return the body-size limit for a given request path."""
    for prefix, limit in _UPLOAD_BODY_LIMITS.items():
        if path.startswith(prefix):
            return limit
    return MAX_REQUEST_BODY_SIZE


class _BodyTooLargeError(Exception):
    """Internal signal raised when chunked body exceeds the path-specific limit."""


app = FastAPI(
    title="AI3L Community API",
    version="0.1.0",
    docs_url="/docs" if settings.is_development else None,
    redoc_url="/redoc" if settings.is_development else None,
    openapi_url="/openapi.json" if settings.is_development else None,
    lifespan=lifespan,
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Return a sanitized 422 response without leaking schema internals."""
    errors = []
    for error in exc.errors():
        loc = error.get("loc", ())
        field = str(loc[-1]) if loc else "unknown"
        errors.append(
            {
                "field": field,
                "message": error.get("msg", "Invalid value"),
            }
        )
    return JSONResponse(
        status_code=422,
        content={"code": "VALIDATION_ERROR", "errors": errors},
    )


@app.middleware("http")
async def limit_upload_concurrency(
    request: Request, call_next: RequestResponseEndpoint
) -> Response:
    """Limit concurrent upload requests to prevent memory pressure."""
    path = request.url.path
    is_upload = request.method == "POST" and any(path.startswith(p) for p in _UPLOAD_BODY_LIMITS)
    if is_upload:
        async with _UPLOAD_SEMAPHORE:
            return await call_next(request)
    return await call_next(request)


@app.middleware("http")
async def limit_request_body_size(request: Request, call_next: RequestResponseEndpoint) -> Response:
    """Reject requests whose body exceeds the path-specific limit.

    Checks Content-Length header first. For chunked transfer (no Content-Length),
    wraps the ASGI receive callable to count bytes and abort if the limit is exceeded.
    """
    body_limit = _get_body_limit(request.url.path)
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > body_limit:
                return JSONResponse(status_code=413, content={"detail": "Request body too large"})
        except (ValueError, TypeError):
            return JSONResponse(
                status_code=400, content={"detail": "Invalid Content-Length header"}
            )
    elif request.method in ("POST", "PUT", "PATCH"):
        # No Content-Length — may be chunked transfer.  Wrap receive to enforce limit.
        bytes_received = 0

        original_receive = request._receive  # type: ignore[attr-defined]

        async def _size_limited_receive() -> dict:  # type: ignore[type-arg]
            nonlocal bytes_received
            message = await original_receive()
            body = message.get("body", b"")
            bytes_received += len(body)
            if bytes_received > body_limit:
                raise _BodyTooLargeError()
            return dict(message)

        request._receive = _size_limited_receive  # type: ignore[attr-defined]

    try:
        return await call_next(request)
    except _BodyTooLargeError:
        return JSONResponse(status_code=413, content={"detail": "Request body too large"})


@app.middleware("http")
async def check_ip_ban(request: Request, call_next: RequestResponseEndpoint) -> Response:
    """Block requests from banned IPs."""
    from app.core.rate_limit import get_client_ip

    ip = get_client_ip(request)
    if ip:
        try:
            from app.services.ip_ban import is_ip_banned

            if await is_ip_banned(ip):
                return JSONResponse(
                    status_code=403,
                    content={"detail": "Your IP address has been banned."},
                )
        except Exception:
            pass  # Redis/DB failure -> allow request through
    return await call_next(request)


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS_LIST,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Content-Type", "X-CSRF-Token", "Idempotency-Key"],
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


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all for unhandled exceptions — return generic 500 without leaking internals."""
    logger.error(
        "Unhandled exception",
        extra={"path": request.url.path, "method": request.method},
        exc_info=exc,
    )
    return JSONResponse(
        status_code=500,
        content={"code": "SYS_500", "message": "Internal server error."},
    )

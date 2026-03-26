import json
import re

from fastapi import Request, Response
from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from app.core.errors import ErrorCode
from app.core.redis import get_redis

IDEMPOTENCY_TTL = 300  # 5 minutes
IDEMPOTENCY_HEADER = "Idempotency-Key"
_IDEM_KEY_RE = re.compile(r"^[a-zA-Z0-9\-]{1,256}$")


class IdempotencyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.method not in ("POST", "PUT"):
            return await call_next(request)

        idem_key = request.headers.get(IDEMPOTENCY_HEADER)
        if not idem_key:
            return await call_next(request)

        if not _IDEM_KEY_RE.match(idem_key):
            return await call_next(request)

        # Namespace key by user (from JWT sub) to prevent cross-user collisions
        # Try HttpOnly cookie first (primary auth), then Bearer header (fallback)
        token = request.cookies.get("access_token")
        if not token:
            auth_header = request.headers.get("Authorization", "")
            if auth_header.startswith("Bearer "):
                token = auth_header[7:]

        # Skip idempotency caching for unauthenticated requests to prevent
        # cross-user response leakage in a shared "anonymous" namespace.
        if not token:
            return await call_next(request)

        # F-30: Use user_id from JWT (stable across token refresh) instead of
        # token hash which changes on every login/refresh.
        try:
            from app.core.security import decode_access_token

            payload = decode_access_token(token)
            user_ns = payload["sub"][:16] if payload and payload.get("sub") else None
        except Exception:
            user_ns = None
        if not user_ns:
            # Fallback: skip idempotency for invalid tokens (auth middleware will reject)
            return await call_next(request)
        redis_key = f"idempotency:{user_ns}:{idem_key}"

        try:
            redis = get_redis()
            cached = await redis.get(redis_key)
        except Exception:
            logger.warning("Redis unavailable for idempotency, proceeding without", exc_info=True)
            return await call_next(request)

        if cached:
            data = json.loads(cached)
            if data.get("status") == "processing":
                conflict_body = json.dumps(
                    {
                        "detail": {
                            "code": ErrorCode.SYS_409.value,
                            "message": "Duplicate request is still processing.",
                        }
                    }
                )
                return Response(
                    content=conflict_body,
                    status_code=409,
                    headers={"Content-Type": "application/json", IDEMPOTENCY_HEADER: idem_key},
                )
            logger.debug("Idempotency cache hit", extra={"key": idem_key})
            return Response(
                content=data["body"],
                status_code=data["status_code"],
                headers={"Content-Type": "application/json", IDEMPOTENCY_HEADER: idem_key},
            )

        # Mark as processing (short TTL to handle crashes)
        acquired = await redis.set(redis_key, json.dumps({"status": "processing"}), ex=30, nx=True)
        if not acquired:
            # Another concurrent request claimed this key
            conflict_body = json.dumps(
                {
                    "detail": {
                        "code": ErrorCode.SYS_409.value,
                        "message": "Duplicate request is still processing.",
                    }
                }
            )
            return Response(
                content=conflict_body,
                status_code=409,
                headers={
                    "Content-Type": "application/json",
                    IDEMPOTENCY_HEADER: idem_key,
                },
            )

        response = await call_next(request)

        # Cache JSON responses to prevent duplicate side effects.
        # Only cache 2xx and 4xx (excluding 429) — transient 5xx and 429
        # errors must NOT be cached so retries can succeed.
        content_type = response.headers.get("content-type", "")
        if "application/json" in content_type:
            # MO-19: Use list + join instead of O(n²) concatenation; cap cache size
            body_chunks: list[bytes] = []
            body_size = 0
            async for chunk in response.body_iterator:  # type: ignore[attr-defined]
                c = chunk if isinstance(chunk, bytes) else chunk.encode()
                body_size += len(c)
                body_chunks.append(c)
            body = b"".join(body_chunks)

            status = response.status_code
            cacheable = (200 <= status <= 299) or (400 <= status <= 499 and status != 429)
            max_cache_size = 512 * 1024  # 512 KB
            if cacheable and body_size <= max_cache_size:
                cache_data = json.dumps(
                    {
                        "body": body.decode("utf-8", errors="replace"),
                        "status_code": status,
                    }
                )
                try:
                    await redis.set(redis_key, cache_data, ex=IDEMPOTENCY_TTL)
                except Exception:
                    logger.warning("Failed to cache idempotency response", exc_info=True)
            else:
                # Non-cacheable status or too large to cache — remove the processing marker
                try:
                    await redis.delete(redis_key)
                except Exception:
                    pass

            return Response(
                content=body,
                status_code=response.status_code,
                headers=dict(response.headers),
            )

        # Non-JSON or streaming responses — clear the processing marker
        try:
            await redis.delete(redis_key)
        except Exception:
            pass
        return response

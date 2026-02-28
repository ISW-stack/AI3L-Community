import hashlib
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
        user_id = "anonymous"
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
            user_id = hashlib.sha256(token.encode()).hexdigest()[:16]

        redis_key = f"idempotency:{user_id}:{idem_key}"
        redis = get_redis()

        # Check for existing response
        cached = await redis.get(redis_key)
        if cached:
            data = json.loads(cached)
            if data.get("status") == "processing":
                conflict_body = json.dumps({"detail": {"code": ErrorCode.SYS_409.value, "message": "Duplicate request is still processing."}})
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
        await redis.set(redis_key, json.dumps({"status": "processing"}), ex=30, nx=True)

        response = await call_next(request)

        # Cache successful responses
        if 200 <= response.status_code < 300:
            body = b""
            async for chunk in response.body_iterator:
                body += chunk if isinstance(chunk, bytes) else chunk.encode()

            cache_data = json.dumps({"body": body.decode(), "status_code": response.status_code})
            await redis.set(redis_key, cache_data, ex=IDEMPOTENCY_TTL)

            return Response(
                content=body,
                status_code=response.status_code,
                headers=dict(response.headers),
            )

        # Don't cache error responses — delete the processing marker
        await redis.delete(redis_key)
        return response

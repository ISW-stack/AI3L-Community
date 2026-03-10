"""CSRF double-submit cookie middleware.

Compares the `csrf_token` cookie with the `X-CSRF-Token` header for
state-changing requests (POST/PUT/PATCH/DELETE).
"""

import secrets
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}

# Exact paths exempt from CSRF check (authentication endpoints where the
# user doesn't yet have a CSRF token).
_EXEMPT_EXACT = frozenset(
    {
        "/api/v1/auth/login",
        "/api/v1/auth/register",
        "/api/v1/auth/captcha",
    }
)

# Prefix-based exemptions (only for routes with dynamic path segments).
_EXEMPT_PREFIXES = ("/api/v1/auth/guest/",)


class CSRFMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: Any, *, header_name: str = "X-CSRF-Token") -> None:
        super().__init__(app)
        self.header_name = header_name

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        # Safe methods — no CSRF check needed
        if request.method in _SAFE_METHODS:
            response: Response = await call_next(request)
            return response

        # WebSocket upgrade — skip (handled by ticket auth)
        if request.headers.get("upgrade", "").lower() == "websocket":
            response = await call_next(request)
            return response

        # WebSocket endpoint path — skip (handled by ticket auth)
        path = request.url.path
        if path.startswith("/api/v1/ws"):
            response = await call_next(request)
            return response

        # Exempt paths (exact match first, then prefix match for dynamic routes)
        if path in _EXEMPT_EXACT:
            response = await call_next(request)
            return response
        for prefix in _EXEMPT_PREFIXES:
            if path.startswith(prefix):
                response = await call_next(request)
                return response

        # Double-submit check
        cookie_token = request.cookies.get("csrf_token")
        header_token = request.headers.get(self.header_name)

        if not cookie_token or not header_token or not secrets.compare_digest(cookie_token, header_token):
            return JSONResponse(
                status_code=403,
                content={"detail": "CSRF token missing or mismatched."},
            )

        response = await call_next(request)
        return response

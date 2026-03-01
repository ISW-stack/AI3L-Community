"""CSRF double-submit cookie middleware.

Compares the `csrf_token` cookie with the `X-CSRF-Token` header for
state-changing requests (POST/PUT/PATCH/DELETE).
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}

# Paths exempt from CSRF check (authentication endpoints where the user
# doesn't yet have a CSRF token, and captcha).
_EXEMPT_PREFIXES = (
    "/api/v1/auth/login",
    "/api/v1/auth/register",
    "/api/v1/auth/guest/",
    "/api/v1/auth/captcha",
)


class CSRFMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, *, header_name: str = "X-CSRF-Token"):
        super().__init__(app)
        self.header_name = header_name

    async def dispatch(self, request: Request, call_next):
        # Safe methods — no CSRF check needed
        if request.method in _SAFE_METHODS:
            return await call_next(request)

        # WebSocket upgrade — skip (handled by ticket auth)
        if request.headers.get("upgrade", "").lower() == "websocket":
            return await call_next(request)

        # Exempt paths
        path = request.url.path
        for prefix in _EXEMPT_PREFIXES:
            if path.startswith(prefix):
                return await call_next(request)

        # Double-submit check
        cookie_token = request.cookies.get("csrf_token")
        header_token = request.headers.get(self.header_name)

        if not cookie_token or not header_token or cookie_token != header_token:
            return JSONResponse(
                status_code=403,
                content={"detail": "CSRF token missing or mismatched."},
            )

        return await call_next(request)

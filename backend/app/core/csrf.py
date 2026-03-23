"""CSRF double-submit cookie middleware.

Compares the `csrf_token` cookie with the `X-CSRF-Token` header for
state-changing requests (POST/PUT/PATCH/DELETE).
The CSRF token is bound to the session JTI via HMAC.
"""

import hashlib
import hmac
import secrets
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.config import settings
from app.core.security import decode_access_token

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

# Prefix-based exemptions for guest login (path has a dynamic invite code segment).
# Only matches the exact guest login route pattern: /api/v1/auth/guest/{invite_code}
# Rejects deeper sub-paths like /api/v1/auth/guest/{code}/foo.
_EXEMPT_GUEST_PREFIX = "/api/v1/auth/guest/"


def generate_csrf_token(jti: str) -> str:
    """Generate a CSRF token bound to the session JTI."""
    return hmac.new(
        settings.SECRET_KEY.encode(),
        jti.encode(),
        hashlib.sha256,
    ).hexdigest()


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

        # Exempt paths (exact match first, then guest login with single path segment)
        if path in _EXEMPT_EXACT:
            response = await call_next(request)
            return response
        if path.startswith(_EXEMPT_GUEST_PREFIX):
            # Only allow /api/v1/auth/guest/{invite_code} — no deeper sub-paths
            remainder = path[len(_EXEMPT_GUEST_PREFIX) :]
            if remainder and "/" not in remainder:
                response = await call_next(request)
                return response

        # Double-submit check
        cookie_token = request.cookies.get("csrf_token")
        # Starlette Headers.get() is case-insensitive per ASGI spec
        header_token = request.headers.get(self.header_name)

        if (
            not cookie_token
            or not header_token
            or not secrets.compare_digest(cookie_token, header_token)
        ):
            return JSONResponse(
                status_code=403,
                content={"detail": "CSRF token missing or mismatched."},
            )

        # Verify the CSRF token is bound to the current session JTI.
        # Only enforce JTI binding for cookie-based sessions. Bearer tokens
        # are explicitly sent by JavaScript and are immune to CSRF by design;
        # the double-submit check above is sufficient for them.
        jwt_token = request.cookies.get("access_token")
        if not jwt_token:
            auth_header = request.headers.get("authorization", "")
            if auth_header.startswith("Bearer "):
                # Bearer auth — double-submit check already passed above.
                # No JTI binding needed (Bearer tokens can't be sent by
                # cross-origin form submissions).
                response = await call_next(request)
                return response
        if not jwt_token:
            # No JWT cookie and no Bearer = no session. Reject.
            return JSONResponse(
                status_code=403,
                content={
                    "detail": {"code": "CSRF_002", "message": "CSRF validation failed: no session."}
                },
            )
        payload = decode_access_token(jwt_token)
        if payload and payload.get("jti"):
            expected = generate_csrf_token(payload["jti"])
            if not secrets.compare_digest(expected, header_token):
                return JSONResponse(
                    status_code=403,
                    content={"detail": "CSRF token not bound to session."},
                )
        elif payload is not None:
            # Token decoded but JTI missing — reject
            return JSONResponse(
                status_code=403,
                content={
                    "detail": {
                        "code": "CSRF_003",
                        "message": "CSRF validation failed: missing JTI.",
                    }
                },
            )
        else:
            # Cookie JWT expired/invalid — reject instead of falling through
            return JSONResponse(
                status_code=403,
                content={
                    "detail": {
                        "code": "CSRF_004",
                        "message": "CSRF validation failed: session expired.",
                    }
                },
            )

        response = await call_next(request)
        return response

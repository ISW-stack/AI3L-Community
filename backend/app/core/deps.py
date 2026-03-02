import uuid
from typing import Any

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.errors import AppError, ErrorCode
from app.core.security import decode_access_token
from app.services.auth import validate_session
from app.services.user import get_user_by_id

security_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security_scheme),
) -> dict:
    """Extract and validate JWT + Redis session. Returns JWT payload.

    Token sources (in priority order):
    1. HttpOnly cookie `access_token`
    2. Authorization: Bearer header (backward compatibility)
    """
    # Try cookie first
    token = request.cookies.get("access_token")

    # Fall back to Bearer header
    if not token and credentials is not None:
        token = credentials.credentials

    if not token:
        raise AppError(ErrorCode.AUTH_001, 401, "Missing authentication token.")

    payload = decode_access_token(token)
    if payload is None:
        raise AppError(ErrorCode.AUTH_001, 401, "Invalid or expired token.")

    user_id = payload.get("sub")
    role = payload.get("role")
    jti = payload.get("jti")

    if not all([user_id, role, jti]):
        raise AppError(ErrorCode.AUTH_001, 401, "Invalid token payload.")

    if not isinstance(user_id, str) or not isinstance(role, str) or not isinstance(jti, str):
        raise AppError(ErrorCode.AUTH_001, 401, "Invalid token payload.")

    # Dual validation: JWT + Redis session
    is_valid = await validate_session(str(user_id), str(role), str(jti))
    if not is_valid:
        raise AppError(ErrorCode.AUTH_002, 401, "Session expired or invalidated.")

    # Check if user is banned (skip for guests — they have no DB record)
    if role != "GUEST":
        user = await get_user_by_id(uuid.UUID(user_id))
        if user and user.get("is_banned"):
            reason = user.get("ban_reason") or "No reason provided"
            raise AppError(ErrorCode.AUTH_004, 403, f"Account is banned: {reason}")

    return payload


def require_role(*allowed_roles: str) -> Any:
    """Dependency factory: restrict endpoint to specific roles."""

    async def role_checker(current_user: dict = Depends(get_current_user)) -> dict:
        user_role = current_user.get("role")
        if user_role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions.",
            )
        return current_user

    return role_checker

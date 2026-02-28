from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.errors import AppError, ErrorCode
from app.core.security import decode_access_token
from app.services.auth import validate_session

security_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security_scheme),
) -> dict:
    """Extract and validate JWT + Redis session. Returns JWT payload."""
    if credentials is None:
        raise AppError(ErrorCode.AUTH_001, 401, "Missing authentication token.")

    payload = decode_access_token(credentials.credentials)
    if payload is None:
        raise AppError(ErrorCode.AUTH_001, 401, "Invalid or expired token.")

    user_id = payload.get("sub")
    role = payload.get("role")
    jti = payload.get("jti")

    if not all([user_id, role, jti]):
        raise AppError(ErrorCode.AUTH_001, 401, "Invalid token payload.")

    # Dual validation: JWT + Redis session
    is_valid = await validate_session(user_id, role, jti)
    if not is_valid:
        raise AppError(ErrorCode.AUTH_002, 401, "Session expired or invalidated.")

    # Check if user is banned (skip for guests — they have no DB record)
    if role != "GUEST":
        from app.services.user import get_user_by_id
        import uuid

        user = await get_user_by_id(uuid.UUID(user_id))
        if user and user.get("is_banned"):
            reason = user.get("ban_reason") or "No reason provided"
            raise AppError(ErrorCode.AUTH_004, 403, f"Account is banned: {reason}")

    return payload


def require_role(*allowed_roles: str):
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

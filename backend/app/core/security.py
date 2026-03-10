import re
import uuid
from datetime import datetime, timedelta, timezone

import jwt
from fastapi.concurrency import run_in_threadpool
from jwt import InvalidTokenError as JWTError
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

# --- Password ---


def hash_password(password: str) -> str:
    return str(pwd_context.hash(password))


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bool(pwd_context.verify(plain_password, hashed_password))


async def async_hash_password(password: str) -> str:
    """Non-blocking hash_password — runs Argon2id in a thread."""
    return await run_in_threadpool(hash_password, password)


async def async_verify_password(plain_password: str, hashed_password: str) -> bool:
    """Non-blocking verify_password — runs Argon2id in a thread."""
    return await run_in_threadpool(verify_password, plain_password, hashed_password)


def validate_password_policy(password: str) -> str | None:
    """Return error message if password doesn't meet policy, None if valid."""
    if len(password) < 8:
        return "Password must be at least 8 characters long."
    if not re.search(r"[A-Z]", password):
        return "Password must contain at least one uppercase letter."
    if not re.search(r"[a-z]", password):
        return "Password must contain at least one lowercase letter."
    if not re.search(r"[0-9]", password):
        return "Password must contain at least one digit."
    return None


# --- JWT ---

ROLE_TTL_MAP: dict[str, timedelta] = {
    "GUEST": timedelta(minutes=settings.JWT_GUEST_EXPIRE_MINUTES),
    "MEMBER": timedelta(minutes=settings.JWT_MEMBER_EXPIRE_MINUTES),
    "ADMIN": timedelta(minutes=settings.JWT_ADMIN_EXPIRE_MINUTES),
    "SUPER_ADMIN": timedelta(minutes=settings.JWT_SUPER_ADMIN_EXPIRE_MINUTES),
}


def create_access_token(
    user_id: str,
    role: str,
    expires_delta: timedelta | None = None,
) -> tuple[str, str, datetime]:
    """Create JWT. Returns (token, jti, expires_at)."""
    jti = str(uuid.uuid4())
    if expires_delta is None:
        expires_delta = ROLE_TTL_MAP.get(role, timedelta(hours=3))
    expires_at = datetime.now(timezone.utc) + expires_delta

    payload = {
        "sub": user_id,
        "role": role,
        "jti": jti,
        "exp": expires_at,
        "iat": datetime.now(timezone.utc),
    }
    token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return token, jti, expires_at


def decode_access_token(token: str) -> dict | None:
    """Decode and verify JWT. Returns payload dict or None if invalid."""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        return dict(payload)
    except JWTError:
        return None

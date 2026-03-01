import uuid
from datetime import datetime, timedelta, timezone

from loguru import logger

from app.core.constants import MAX_GUESTS
from app.core.redis import get_redis
from app.core.security import (
    ROLE_TTL_MAP,
    create_access_token,
    verify_password,
)
from app.repositories import auth_repo
from app.services.user import get_user_by_username

SESSION_KEY_TEMPLATE = "session:{role}:{user_id}"
BLACKLIST_KEY_TEMPLATE = "jwt:blacklist:{jti}"
GUEST_ONLINE_KEY = "online_count:guest"


async def authenticate_user(username: str, password: str) -> dict | None:
    """Verify username + password. Returns user dict or None."""
    user = await get_user_by_username(username)
    if user is None:
        return None
    if user.get("is_deleted"):
        return None
    if not verify_password(password, user["password_hash"]):
        return None
    return user


async def create_session(user_id: str, role: str) -> tuple[str, int]:
    """Create JWT + Redis session. Returns (token, expires_in_seconds)."""
    ttl = ROLE_TTL_MAP.get(role, timedelta(hours=3))
    token, jti, expires_at = create_access_token(user_id, role, ttl)
    ttl_seconds = int(ttl.total_seconds())

    redis = get_redis()
    session_key = SESSION_KEY_TEMPLATE.format(role=role, user_id=user_id)
    await redis.set(session_key, token, ex=ttl_seconds)

    logger.info("Session created", extra={"user_id": user_id, "role": role})
    return token, ttl_seconds


async def destroy_session(user_id: str, role: str, jti: str) -> None:
    """Logout: remove session + blacklist JWT."""
    redis = get_redis()

    session_key = SESSION_KEY_TEMPLATE.format(role=role, user_id=user_id)
    await redis.delete(session_key)

    blacklist_key = BLACKLIST_KEY_TEMPLATE.format(jti=jti)
    await redis.set(blacklist_key, "1", ex=28800)  # 8 hours max

    if role == "GUEST":
        await redis.decr(GUEST_ONLINE_KEY)

    logger.info("Session destroyed", extra={"user_id": user_id})


async def refresh_session_ttl(user_id: str, role: str) -> bool:
    """Heartbeat: refresh Redis session TTL. Returns True if session exists."""
    redis = get_redis()
    session_key = SESSION_KEY_TEMPLATE.format(role=role, user_id=user_id)

    exists = await redis.exists(session_key)
    if not exists:
        return False

    ttl = ROLE_TTL_MAP.get(role, timedelta(hours=3))
    await redis.expire(session_key, int(ttl.total_seconds()))
    return True


async def validate_session(user_id: str, role: str, jti: str) -> bool:
    """Validate JWT is not blacklisted AND Redis session exists."""
    redis = get_redis()

    blacklist_key = BLACKLIST_KEY_TEMPLATE.format(jti=jti)
    if await redis.exists(blacklist_key):
        return False

    session_key = SESSION_KEY_TEMPLATE.format(role=role, user_id=user_id)
    return bool(await redis.exists(session_key))


async def guest_login(display_name: str) -> tuple[str, int] | None:
    """Create guest session. Returns (token, expires_in) or None if limit reached."""
    redis = get_redis()

    count = await redis.incr(GUEST_ONLINE_KEY)
    if count > MAX_GUESTS:
        await redis.decr(GUEST_ONLINE_KEY)
        return None

    guest_id = str(uuid.uuid4())
    try:
        token, ttl_seconds = await create_session(guest_id, "GUEST")
    except Exception:
        await redis.decr(GUEST_ONLINE_KEY)
        raise

    logger.info(
        "Guest login",
        extra={"guest_id": guest_id, "display_name": display_name, "online_guests": count},
    )
    return token, ttl_seconds


async def get_invite_code(invite_code: str) -> dict | None:
    """Verify invite code exists, is not expired, and has not been consumed."""
    return await auth_repo.find_invite_code(invite_code)


async def consume_invite_code(code: str, user_id: str) -> None:
    """Mark an invite code as consumed by the given user."""
    await auth_repo.consume_invite_code(code, uuid.UUID(user_id))
    logger.info("Invite code consumed", extra={"code": code, "user_id": user_id})


async def create_invite_code(user_id: str) -> tuple[str, datetime]:
    """Generate a new invite code. Returns (code, expires_at)."""
    code = f"INV-{uuid.uuid4().hex[:8].upper()}"
    expires_at = datetime.now(timezone.utc) + timedelta(days=7)
    await auth_repo.insert_invite_code(uuid.uuid4(), code, uuid.UUID(user_id), expires_at)
    logger.info("Invite code created", extra={"user_id": user_id, "code": code})
    return code, expires_at

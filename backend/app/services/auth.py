import json
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from loguru import logger

from app.core.constants import MAX_GUESTS
from app.core.redis import get_redis
from app.core.security import ROLE_TTL_MAP, create_access_token, verify_password
from app.models.user import UserRole
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
    await redis.set(session_key, jti, ex=ttl_seconds)

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
    """Validate JWT is not blacklisted AND Redis session jti matches."""
    redis = get_redis()

    blacklist_key = BLACKLIST_KEY_TEMPLATE.format(jti=jti)
    if await redis.exists(blacklist_key):
        return False

    session_key = SESSION_KEY_TEMPLATE.format(role=role, user_id=user_id)
    stored_jti = await redis.get(session_key)
    return bool(stored_jti == jti)


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


async def revoke_user_sessions(user_id: str) -> None:
    """Revoke all Redis sessions for a user (all roles) in one batch delete."""
    redis = get_redis()
    session_keys = [SESSION_KEY_TEMPLATE.format(role=r.value, user_id=user_id) for r in UserRole]
    await redis.delete(*session_keys)
    logger.info("All sessions revoked", extra={"user_id": user_id})


async def create_ws_ticket(user_payload: dict) -> str:
    """Generate a one-time WebSocket authentication ticket (30s TTL).

    Returns the ticket string.
    """
    ticket = secrets.token_urlsafe(32)
    redis = get_redis()
    await redis.set(
        f"ws:ticket:{ticket}",
        json.dumps(
            {
                "sub": user_payload["sub"],
                "role": user_payload["role"],
                "jti": user_payload["jti"],
            }
        ),
        ex=30,
    )
    return ticket


async def register_new_user(
    username: str,
    password: str,
    display_name: str,
    invite_code: str,
) -> dict:
    """Create user and consume invite code in a single DB transaction.

    Returns the created user dict.
    """
    from app.core.database import get_pool
    from app.core.security import hash_password

    user_id = uuid.uuid4()
    pw_hash = hash_password(password)
    if not display_name:
        display_name = username

    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                """
                INSERT INTO users (id, username, password_hash, role, display_name)
                VALUES ($1, $2, $3, $4, $5)
                RETURNING *
                """,
                user_id,
                username,
                pw_hash,
                UserRole.MEMBER.value,
                display_name,
            )
            await conn.execute(
                "UPDATE invite_codes SET consumed_at = NOW(), consumed_by = $1 WHERE code = $2",
                user_id,
                invite_code,
            )
    user = dict(row)
    logger.info("User registered", extra={"user_id": str(user_id), "invite_code": invite_code})
    return user

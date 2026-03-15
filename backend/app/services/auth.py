import json
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from loguru import logger

from app.core.constants import MAX_GUESTS
from app.core.redis import get_redis
from app.core.security import ROLE_TTL_MAP, async_verify_password, create_access_token
from app.models.user import UserRole
from app.repositories import auth_repo
from app.services.user import get_user_by_username

SESSION_KEY_TEMPLATE = "session:{role}:{user_id}"
BLACKLIST_KEY_TEMPLATE = "jwt:blacklist:{jti}"


async def authenticate_user(username: str, password: str) -> dict | None:
    """Verify username + password. Returns user dict or None."""
    user = await get_user_by_username(username)
    if user is None:
        return None
    if user.get("is_deleted"):
        return None
    if not await async_verify_password(password, user["password_hash"]):
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


_GUEST_COUNTER_KEY = "meta:guest_counter"


async def sync_guest_counter() -> None:
    """Sync the atomic guest counter with actual session count in Redis.

    Called on startup or when counter may be stale.
    """
    redis = get_redis()
    count = 0
    async for _ in redis.scan_iter(match="session:GUEST:*", count=100):
        count += 1
    await redis.set(_GUEST_COUNTER_KEY, count)


async def _get_guest_count() -> int:
    """Read current guest count from the atomic counter."""
    redis = get_redis()
    val = await redis.get(_GUEST_COUNTER_KEY)
    if val is None:
        # Counter not initialised yet — sync from session keys
        await sync_guest_counter()
        val = await redis.get(_GUEST_COUNTER_KEY)
    return int(val) if val is not None else 0


async def guest_login(display_name: str) -> tuple[str, int] | None:
    """Create guest session. Returns (token, expires_in) or None if limit reached.

    Uses Redis INCR for atomic counting to prevent TOCTOU race conditions.
    """
    redis = get_redis()

    # Atomically initialise counter only if it doesn't exist (SETNX).
    # This eliminates the TOCTOU race in the old exists-then-sync pattern.
    count = 0
    async for _ in redis.scan_iter(match="session:GUEST:*", count=100):
        count += 1
    await redis.set(_GUEST_COUNTER_KEY, count, nx=True)

    # Atomically increment — if over limit, decrement and reject
    new_count = await redis.incr(_GUEST_COUNTER_KEY)
    if new_count > MAX_GUESTS:
        await redis.decr(_GUEST_COUNTER_KEY)
        return None

    guest_id = str(uuid.uuid4())
    token, ttl_seconds = await create_session(guest_id, "GUEST")

    # Store display_name in Redis so WebSocket and API can retrieve it
    await redis.set(f"guest:display_name:{guest_id}", display_name, ex=ttl_seconds)

    logger.info(
        "Guest login",
        extra={"guest_id": guest_id, "display_name": display_name, "online_guests": new_count},
    )
    return token, ttl_seconds


async def decrement_guest_counter() -> None:
    """Decrement the atomic guest counter (call on guest session expiry/logout)."""
    redis = get_redis()
    val = await redis.decr(_GUEST_COUNTER_KEY)
    # Prevent counter from going negative
    if val < 0:
        await redis.set(_GUEST_COUNTER_KEY, 0)


async def decrement_guest_ip_counter(ip: str) -> None:
    """Decrement the per-IP guest counter (call on guest logout).

    Clamps to zero to prevent negative values from stale or duplicate decrements.
    """
    redis = get_redis()
    ip_guest_key = f"guest:ip:{ip}"
    val = await redis.decr(ip_guest_key)
    if val < 0:
        await redis.set(ip_guest_key, 0)
        await redis.expire(ip_guest_key, 3600)


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
    from app.core.security import async_hash_password

    user_id = uuid.uuid4()
    pw_hash = await async_hash_password(password)
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
            result = await conn.execute(
                "UPDATE invite_codes SET consumed_at = NOW(), consumed_by = $1 "
                "WHERE code = $2 AND consumed_at IS NULL",
                user_id,
                invite_code,
            )
            if result != "UPDATE 1":
                raise ValueError("Invite code already consumed.")
    user = dict(row)
    logger.info("User registered", extra={"user_id": str(user_id), "invite_code": invite_code})
    return user

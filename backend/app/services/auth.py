import json
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from loguru import logger

from app.core.constants import MAX_GUESTS, MAX_GUESTS_PER_IP
from app.core.logging_utils import mask_pii
from app.core.redis import get_redis
from app.core.security import ROLE_TTL_MAP, async_verify_password, create_access_token
from app.models.user import UserRole
from app.repositories import auth_repo
from app.services.user import get_user_by_username

SESSION_KEY_TEMPLATE = "session:{role}:{user_id}"
BLACKLIST_KEY_TEMPLATE = "jwt:blacklist:{jti}"

# Pre-computed dummy hash for timing-oracle prevention (AUTH-01).
# Ensures non-existent user lookups take the same time as real ones.
_DUMMY_HASH: str = ""


def _init_dummy_hash() -> str:
    from passlib.context import CryptContext

    ctx = CryptContext(schemes=["argon2"], deprecated="auto")
    return str(ctx.hash("dummy_password_for_timing_oracle"))


_DUMMY_HASH = _init_dummy_hash()


async def authenticate_user(username: str, password: str) -> dict | None:
    """Verify username + password. Returns user dict or None."""
    user = await get_user_by_username(username)
    if user is None:
        await async_verify_password(password, _DUMMY_HASH)
        return None
    if user.get("is_deleted"):
        await async_verify_password(password, _DUMMY_HASH)
        return None
    if not await async_verify_password(password, user["password_hash"]):
        return None
    return user


async def create_session(user_id: str, role: str) -> tuple[str, str, int]:
    """Create JWT + Redis session. Returns (token, jti, expires_in_seconds).

    If an existing session is found for the same user+role, publishes a
    FORCE_LOGOUT message via Redis Pub/Sub so the old session's WebSocket
    can inform the user and close gracefully.
    """
    ttl = ROLE_TTL_MAP.get(role, timedelta(hours=3))
    token, jti, expires_at = create_access_token(user_id, role, ttl)
    ttl_seconds = int(ttl.total_seconds())

    redis = get_redis()
    session_key = SESSION_KEY_TEMPLATE.format(role=role, user_id=user_id)

    # Atomically swap the session key and retrieve the previous JTI in one round-trip.
    # SET ... GET (Redis 6.2+) is atomic, eliminating the read-then-write race where
    # two concurrent logins could both read the same old_jti and both overwrite it.
    old_raw = await redis.set(session_key, jti, ex=ttl_seconds, get=True)
    old_jti = old_raw.decode() if isinstance(old_raw, bytes) else old_raw
    if old_jti:
        # Notify the old session via WebSocket Pub/Sub
        await redis.publish(
            f"ws:user:{user_id}",
            json.dumps(
                {
                    "type": "FORCE_LOGOUT",
                    "reason": "logged_in_from_another_device",
                }
            ),
        )
        # Blacklist the old JTI so it cannot be reused
        old_blacklist_key = BLACKLIST_KEY_TEMPLATE.format(jti=old_jti)
        await redis.set(old_blacklist_key, "1", ex=28800)
        logger.info(
            "Session overridden — old session invalidated",
            extra={"user_id": user_id, "role": role},
        )

    logger.info("Session created", extra={"user_id": user_id, "role": role})
    return token, jti, ttl_seconds


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
    if not stored_jti:
        return False
    stored_jti_str = stored_jti.decode() if isinstance(stored_jti, bytes) else stored_jti
    return secrets.compare_digest(stored_jti_str, jti)


_GUEST_COUNTER_KEY = "meta:guest_counter"

# Lua: atomically increment guest counter with limit check.
# KEYS[1] = counter key, ARGV[1] = max guests.
# Returns new count on success, -1 if limit exceeded.
_GUEST_INCR_LUA = """
local new_count = redis.call('INCR', KEYS[1])
if new_count > tonumber(ARGV[1]) then
    redis.call('DECR', KEYS[1])
    return -1
end
return new_count
"""


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


async def guest_login(display_name: str) -> tuple[str, str, int] | None:
    """Create guest session. Returns (token, jti, expires_in) or None if limit reached.

    Uses Redis INCR for atomic counting to prevent TOCTOU race conditions.
    """
    redis = get_redis()

    # Atomically check-and-increment via Lua script.
    # If counter key is missing, INCR creates it at 0→1 (safe).
    # sync_guest_counter() at startup seeds the accurate value.
    new_count: int = await redis.eval(  # type: ignore[misc]
        _GUEST_INCR_LUA, 1, _GUEST_COUNTER_KEY, MAX_GUESTS  # type: ignore[arg-type]
    )
    if new_count == -1:
        return None

    guest_id = str(uuid.uuid4())
    token, jti, ttl_seconds = await create_session(guest_id, "GUEST")

    # Store display_name in Redis so WebSocket and API can retrieve it
    await redis.set(f"guest:display_name:{guest_id}", display_name, ex=ttl_seconds)

    logger.info(
        "Guest login",
        extra={
            "guest_id": guest_id,
            "display_name": mask_pii(display_name),
            "online_guests": new_count,
        },
    )
    return token, jti, ttl_seconds


# Lua: atomically decrement guest counter, clamping to zero.
# KEYS[1] = counter key. Returns new value (0 if clamped).
_GUEST_DECR_LUA = """
local val = redis.call('DECR', KEYS[1])
if val < 0 then
    redis.call('SET', KEYS[1], 0)
    return 0
end
return val
"""

# Lua: atomically decrement per-IP guest counter, clamping to zero and preserving TTL.
# KEYS[1] = ip counter key, ARGV[1] = default TTL in seconds.
_GUEST_IP_DECR_LUA = """
local val = redis.call('DECR', KEYS[1])
if val < 0 then
    redis.call('SET', KEYS[1], 0)
    local ttl = redis.call('TTL', KEYS[1])
    if ttl < 0 then
        redis.call('EXPIRE', KEYS[1], tonumber(ARGV[1]))
    end
    return 0
end
return val
"""

# Lua: atomically increment per-IP guest counter with limit check.
# KEYS[1] = ip counter key, ARGV[1] = max guests per IP, ARGV[2] = TTL in seconds.
# Returns new count on success, -1 if limit exceeded.
# Sets EXPIRE only on first guest from this IP (new_count == 1).
_GUEST_IP_INCR_LUA = """
local new_count = redis.call('INCR', KEYS[1])
if new_count > tonumber(ARGV[1]) then
    redis.call('DECR', KEYS[1])
    return -1
end
if new_count == 1 then
    redis.call('EXPIRE', KEYS[1], tonumber(ARGV[2]))
end
return new_count
"""


async def decrement_guest_counter() -> None:
    """Decrement the atomic guest counter (call on guest session expiry/logout).

    Uses a Lua script for atomic decrement-and-clamp to prevent race conditions
    where concurrent DECRs go negative and a SET(0) overwrites an intervening INCR.
    """
    redis = get_redis()
    await redis.eval(_GUEST_DECR_LUA, 1, _GUEST_COUNTER_KEY)  # type: ignore[misc]


async def decrement_guest_ip_counter(ip: str) -> None:
    """Decrement the per-IP guest counter (call on guest logout).

    Uses a Lua script for atomic decrement-and-clamp. Preserves existing TTL
    on the key; if no TTL is set (key was reset), applies the default 3600s.
    """
    redis = get_redis()
    ip_guest_key = f"guest:ip:{ip}"
    await redis.eval(_GUEST_IP_DECR_LUA, 1, ip_guest_key, 3600)  # type: ignore[misc, arg-type]


async def increment_guest_ip_counter(ip: str) -> bool:
    """Atomically increment the per-IP guest counter with limit check.

    Returns True if the increment succeeded (under limit), False if limit exceeded.
    Uses a Lua script to prevent TOCTOU race conditions where concurrent requests
    from the same IP could bypass the per-IP guest limit.
    """
    redis = get_redis()
    ip_guest_key = f"guest:ip:{ip}"
    result: int = await redis.eval(  # type: ignore[misc]
        _GUEST_IP_INCR_LUA, 1, ip_guest_key, MAX_GUESTS_PER_IP, 3600  # type: ignore[arg-type]
    )
    return result != -1


async def get_invite_code(invite_code: str) -> dict | None:
    """Verify invite code exists, is not expired, and has not been consumed."""
    return await auth_repo.find_invite_code(invite_code)


async def consume_invite_code(code: str, user_id: str | None = None) -> bool:
    """Mark an invite code as consumed. Returns True if updated.

    ``user_id`` is optional — guest logins consume the code without a DB user.
    """
    uid = uuid.UUID(user_id) if user_id else None
    ok = await auth_repo.consume_invite_code(code, uid)
    if ok:
        logger.info(
            "Invite code consumed",
            extra={"code": mask_pii(code, 4), "user_id": user_id or "guest"},
        )
    return ok


async def create_invite_code(user_id: str) -> tuple[str, datetime]:
    """Generate a new invite code. Returns (code, expires_at)."""
    code = f"INV-{uuid.uuid4().hex[:16].upper()}"
    expires_at = datetime.now(timezone.utc) + timedelta(days=7)
    await auth_repo.insert_invite_code(uuid.uuid4(), code, uuid.UUID(user_id), expires_at)
    logger.info("Invite code created", extra={"user_id": user_id, "code": mask_pii(code, 4)})
    return code, expires_at


async def revoke_user_sessions(user_id: str) -> None:
    """Revoke all Redis sessions for a user (all roles): blacklist JTIs then delete keys."""
    redis = get_redis()
    session_keys = [SESSION_KEY_TEMPLATE.format(role=r.value, user_id=user_id) for r in UserRole]

    # Batch-read all JTIs, blacklist them, then delete session keys
    stored_jtis = await redis.mget(*session_keys)
    async with redis.pipeline(transaction=False) as pipe:
        for jti_raw in stored_jtis:
            if jti_raw:
                jti_str = jti_raw.decode() if isinstance(jti_raw, bytes) else jti_raw
                pipe.set(BLACKLIST_KEY_TEMPLATE.format(jti=jti_str), "1", ex=28800)
        pipe.delete(*session_keys)
        await pipe.execute()
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
                "WHERE code = $2 AND consumed_at IS NULL AND expires_at > NOW()",
                user_id,
                invite_code,
            )
            if result != "UPDATE 1":
                raise ValueError("Invite code already consumed or expired.")
    user = dict(row)
    logger.info(
        "User registered", extra={"user_id": str(user_id), "invite_code": mask_pii(invite_code, 4)}
    )
    return user

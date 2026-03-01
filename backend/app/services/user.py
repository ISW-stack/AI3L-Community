import uuid

from loguru import logger

from app.core.database import get_pool
from app.core.security import hash_password, validate_password_policy, verify_password
from app.models.user import UserRole


async def get_user_by_username(username: str) -> dict | None:
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM users WHERE username = $1", username)
        return dict(row) if row else None


async def get_user_by_id(user_id: uuid.UUID) -> dict | None:
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM users WHERE id = $1", user_id)
        return dict(row) if row else None


async def create_user(
    username: str,
    password: str,
    role: str = UserRole.MEMBER.value,
    display_name: str = "",
) -> dict:
    pool = get_pool()
    user_id = uuid.uuid4()
    pw_hash = hash_password(password)
    if not display_name:
        display_name = username

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO users (id, username, password_hash, role, display_name)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING *
            """,
            user_id,
            username,
            pw_hash,
            role,
            display_name,
        )
        logger.info("User created", extra={"user_id": str(user_id), "role": role})
        return dict(row)


async def update_user_profile(
    user_id: uuid.UUID,
    display_name: str | None = None,
    bio: str | None = None,
    affiliation: str | None = None,
    orcid: str | None = None,
    avatar_url: str | None = None,
) -> dict | None:
    pool = get_pool()

    # Build dynamic SET clause
    fields: list[str] = []
    values: list = []
    idx = 1

    for field_name, value in [
        ("display_name", display_name),
        ("bio", bio),
        ("affiliation", affiliation),
        ("orcid", orcid),
        ("avatar_url", avatar_url),
    ]:
        if value is not None:
            fields.append(f"{field_name} = ${idx}")
            values.append(value)
            idx += 1

    if not fields:
        return await get_user_by_id(user_id)

    values.append(user_id)
    query = f"UPDATE users SET {', '.join(fields)}, updated_at = NOW() WHERE id = ${idx} RETURNING *"

    async with pool.acquire() as conn:
        row = await conn.fetchrow(query, *values)
        return dict(row) if row else None


async def user_exists_by_username(username: str) -> bool:
    pool = get_pool()
    async with pool.acquire() as conn:
        count = await conn.fetchval(
            "SELECT COUNT(*) FROM users WHERE username = $1", username
        )
        return count > 0


async def update_user_role(user_id: uuid.UUID, new_role: str) -> dict | None:
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "UPDATE users SET role = $1, updated_at = NOW() WHERE id = $2 AND is_deleted = false RETURNING *",
            new_role,
            user_id,
        )
        if row:
            logger.info("User role updated", extra={"user_id": str(user_id), "new_role": new_role})
        return dict(row) if row else None


async def anonymize_user(user_id: uuid.UUID) -> bool:
    """GDPR anonymization: overwrite PII, set is_deleted=true."""
    pool = get_pool()
    anon_name = f"Deleted_User_{uuid.uuid4().hex[:8]}"
    async with pool.acquire() as conn:
        result = await conn.execute(
            """
            UPDATE users SET
                username = $1,
                display_name = $1,
                password_hash = 'ANONYMIZED',
                avatar_url = NULL,
                orcid = NULL,
                affiliation = NULL,
                bio = NULL,
                is_deleted = true,
                updated_at = NOW()
            WHERE id = $2 AND is_deleted = false
            """,
            anon_name,
            user_id,
        )
        deleted = result == "UPDATE 1"
        if deleted:
            logger.info("User anonymized (GDPR)", extra={"user_id": str(user_id)})
        return deleted


async def ban_user(user_id: uuid.UUID, reason: str) -> bool:
    """Ban a user: set is_banned=true, revoke all sessions, send WS FORCE_LOGOUT."""
    pool = get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "UPDATE users SET is_banned = true, ban_reason = $1, updated_at = NOW() WHERE id = $2 AND is_deleted = false",
            reason,
            user_id,
        )
        if result != "UPDATE 1":
            return False

    # Revoke all Redis sessions for this user
    from app.core.redis import get_redis

    redis = get_redis()
    for role in [r.value for r in UserRole]:
        await redis.delete(f"session:{role}:{user_id}")

    # Force logout via WebSocket (best-effort)
    try:
        from app.api.v1.endpoints.ws import force_logout

        await force_logout(str(user_id))
    except Exception:
        pass

    logger.info("User banned", extra={"user_id": str(user_id), "reason": reason})
    return True


async def unban_user(user_id: uuid.UUID) -> bool:
    """Unban a user: set is_banned=false, clear ban_reason."""
    pool = get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "UPDATE users SET is_banned = false, ban_reason = NULL, updated_at = NOW() WHERE id = $1 AND is_deleted = false",
            user_id,
        )
        if result != "UPDATE 1":
            return False

    logger.info("User unbanned", extra={"user_id": str(user_id)})
    return True


def get_user_storage_used(user_id: str) -> int:
    """Return total bytes stored for a user across editor/ and avatars/ prefixes."""
    from app.core.config import settings
    from app.core.storage import get_storage

    client = get_storage()
    bucket = settings.MINIO_BUCKET_NAME
    total = 0
    for prefix in [f"editor/{user_id}/", f"avatars/{user_id}/"]:
        paginator = client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
            for obj in page.get("Contents", []):
                total += obj["Size"]
    return total


async def change_password(user_id: uuid.UUID, old_password: str, new_password: str) -> bool:
    """Verify old password, validate policy, hash new, update. Returns True on success."""
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT password_hash FROM users WHERE id = $1 AND is_deleted = false",
            user_id,
        )
        if not row:
            raise ValueError("User not found.")

        if not verify_password(old_password, row["password_hash"]):
            raise ValueError("Current password is incorrect.")

        error = validate_password_policy(new_password)
        if error:
            raise ValueError(error)

        new_hash = hash_password(new_password)
        await conn.execute(
            "UPDATE users SET password_hash = $1, updated_at = NOW() WHERE id = $2",
            new_hash,
            user_id,
        )
        logger.info("Password changed", extra={"user_id": str(user_id)})
        return True


async def list_users(offset: int = 0, limit: int = 50) -> tuple[list[dict], int]:
    pool = get_pool()
    async with pool.acquire() as conn:
        total = await conn.fetchval("SELECT COUNT(*) FROM users WHERE is_deleted = false")
        rows = await conn.fetch(
            "SELECT * FROM users WHERE is_deleted = false ORDER BY created_at DESC OFFSET $1 LIMIT $2",
            offset,
            limit,
        )
        return [dict(r) for r in rows], total

import uuid

from loguru import logger

from app.core.database import get_pool
from app.core.security import hash_password
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

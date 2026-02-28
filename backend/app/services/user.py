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

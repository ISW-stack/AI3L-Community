import uuid
from typing import Any

from app.core.database import get_pool


async def find_by_id(user_id: uuid.UUID) -> dict | None:
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM users WHERE id = $1", user_id)
        return dict(row) if row else None


async def find_by_username(username: str) -> dict | None:
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM users WHERE username = $1", username)
        return dict(row) if row else None


async def insert(
    user_id: uuid.UUID,
    username: str,
    password_hash: str,
    role: str,
    display_name: str,
) -> dict:
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO users (id, username, password_hash, role, display_name)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING *
            """,
            user_id,
            username,
            password_hash,
            role,
            display_name,
        )
        return dict(row)


async def update_profile(user_id: uuid.UUID, **fields: Any) -> dict | None:
    """Dynamic update of user profile fields."""
    set_parts: list[str] = []
    values: list = []
    idx = 1
    for field_name, value in fields.items():
        if value is not None:
            set_parts.append(f"{field_name} = ${idx}")
            values.append(value)
            idx += 1

    if not set_parts:
        return await find_by_id(user_id)

    values.append(user_id)
    query = (
        f"UPDATE users SET {', '.join(set_parts)}, updated_at = NOW() WHERE id = ${idx} RETURNING *"
    )

    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(query, *values)
        return dict(row) if row else None


async def exists_by_username(username: str) -> bool:
    pool = get_pool()
    async with pool.acquire() as conn:
        count = await conn.fetchval("SELECT COUNT(*) FROM users WHERE username = $1", username)
        return bool(count > 0)


async def update_role(user_id: uuid.UUID, new_role: str) -> dict | None:
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "UPDATE users SET role = $1, updated_at = NOW() WHERE id = $2 AND is_deleted = false RETURNING *",  # noqa: E501
            new_role,
            user_id,
        )
        return dict(row) if row else None


async def anonymize(user_id: uuid.UUID, anon_name: str) -> bool:
    pool = get_pool()
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
        return bool(result == "UPDATE 1")


async def set_ban(user_id: uuid.UUID, reason: str) -> bool:
    pool = get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "UPDATE users SET is_banned = true, ban_reason = $1, updated_at = NOW() WHERE id = $2 AND is_deleted = false",  # noqa: E501
            reason,
            user_id,
        )
        return bool(result == "UPDATE 1")


async def clear_ban(user_id: uuid.UUID) -> bool:
    pool = get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "UPDATE users SET is_banned = false, ban_reason = NULL, updated_at = NOW() WHERE id = $1 AND is_deleted = false",  # noqa: E501
            user_id,
        )
        return bool(result == "UPDATE 1")


async def list_all(offset: int = 0, limit: int = 50) -> tuple[list[dict], int]:
    pool = get_pool()
    async with pool.acquire() as conn:
        total = await conn.fetchval("SELECT COUNT(*) FROM users WHERE is_deleted = false")
        rows = await conn.fetch(
            "SELECT * FROM users WHERE is_deleted = false ORDER BY created_at DESC OFFSET $1 LIMIT $2",  # noqa: E501
            offset,
            limit,
        )
        return [dict(r) for r in rows], total


async def update_password_hash(user_id: uuid.UUID, new_hash: str) -> None:
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE users SET password_hash = $1, updated_at = NOW() WHERE id = $2",
            new_hash,
            user_id,
        )


async def find_password_hash(user_id: uuid.UUID) -> str | None:
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT password_hash FROM users WHERE id = $1 AND is_deleted = false",
            user_id,
        )
        return row["password_hash"] if row else None


async def bulk_update_role(user_ids: list[uuid.UUID], role: str, conn: Any) -> int:
    """Update role for multiple users. Returns count updated."""
    result = await conn.execute(
        "UPDATE users SET role = $1, updated_at = NOW() WHERE id = ANY($2::uuid[]) AND is_deleted = false",  # noqa: E501
        role,
        user_ids,
    )
    return int(result.split()[-1])

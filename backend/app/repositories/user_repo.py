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
    _ALLOWED_FIELDS = {
        "display_name",
        "bio",
        "affiliation",
        "orcid",
        "avatar_url",
        "preferred_language",
    }
    set_parts: list[str] = []
    values: list = []
    idx = 1
    for field_name, value in fields.items():
        if field_name not in _ALLOWED_FIELDS:
            continue
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


async def list_all(
    page: int = 1,
    page_size: int = 50,
    search: str | None = None,
) -> tuple[list[dict], int]:
    pool = get_pool()
    offset = (page - 1) * page_size
    async with pool.acquire() as conn:
        if search:
            pattern = f"%{search}%"
            rows = await conn.fetch(
                "SELECT *, COUNT(*) OVER() AS _total FROM users"
                " WHERE is_deleted = false"
                " AND (username ILIKE $1 OR display_name ILIKE $1)"
                " ORDER BY created_at DESC OFFSET $2 LIMIT $3",
                pattern,
                offset,
                page_size,
            )
        else:
            rows = await conn.fetch(
                "SELECT *, COUNT(*) OVER() AS _total FROM users"
                " WHERE is_deleted = false"
                " ORDER BY created_at DESC OFFSET $1 LIMIT $2",
                offset,
                page_size,
            )
        if rows:
            total = rows[0]["_total"]
            return [
                {k: v for k, v in dict(r).items() if k != "_total"} for r in rows
            ], total
        return [], 0


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


async def increment_storage_used(
    user_id: uuid.UUID,
    delta_bytes: int,  # positive for upload, negative for delete
) -> None:
    """Atomically update storage_used_bytes. Clamps at 0 to prevent negative values."""
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE users
            SET storage_used_bytes = GREATEST(0, storage_used_bytes + $1)
            WHERE id = $2
            """,
            delta_bytes,
            user_id,
        )


async def decrement_storage_used(user_id: uuid.UUID, delta_bytes: int) -> None:
    """Atomically decrease storage_used_bytes. Clamps at 0 to prevent negative values."""
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE users
            SET storage_used_bytes = GREATEST(0, storage_used_bytes - $1)
            WHERE id = $2
            """,
            delta_bytes,
            user_id,
        )


async def count_by_role(role: str) -> int:
    """Count non-deleted users with the given role."""
    pool = get_pool()
    async with pool.acquire() as conn:
        result = await conn.fetchval(
            "SELECT COUNT(*) FROM users WHERE role = $1 AND is_deleted = false",
            role,
        )
        return int(result)


async def count_super_admins_excluding(user_ids: list[uuid.UUID]) -> int:
    """Count SUPER_ADMIN users not in the given list (non-deleted)."""
    pool = get_pool()
    async with pool.acquire() as conn:
        result = await conn.fetchval(
            "SELECT COUNT(*) FROM users "
            "WHERE role = 'SUPER_ADMIN' AND is_deleted = false "
            "AND id != ALL($1::uuid[])",
            user_ids,
        )
        return int(result)


async def get_storage_used(user_id: uuid.UUID) -> int:
    """Return the DB-tracked storage_used_bytes for a user."""
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT storage_used_bytes FROM users WHERE id = $1", user_id)
    return int(row["storage_used_bytes"]) if row else 0

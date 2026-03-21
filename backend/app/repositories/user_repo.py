import uuid
from typing import Any

from app.core.database import get_pool

# Columns safe to return from user queries (excludes password_hash).
_USER_COLUMNS = (
    "id, username, display_name, role, bio, affiliation, orcid, "
    "avatar_url, preferred_language, is_banned, ban_reason, is_deleted, "
    "created_at, updated_at"
)


def _escape_ilike(s: str) -> str:
    """Escape ILIKE special characters."""
    return s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


async def find_by_id(user_id: uuid.UUID) -> dict | None:
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT u.id, u.username, u.display_name, u.role, u.bio,
                   u.affiliation, u.orcid, u.avatar_url, u.preferred_language,
                   u.is_banned, u.ban_reason, u.is_deleted,
                   u.created_at, u.updated_at,
                   COALESCE(up.dm_friends_only, FALSE) AS dm_friends_only
            FROM users u
            LEFT JOIN user_preferences up ON up.user_id = u.id
            WHERE u.id = $1
            """,
            user_id,
        )
        return dict(row) if row else None


async def find_by_username(username: str) -> dict | None:
    """Return the full user row **including password_hash**.

    This is intentional — the function is used by authenticate_user which
    needs the hash to verify credentials.  All other lookup functions use
    the restricted _USER_COLUMNS projection.
    """
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
            f"""
            INSERT INTO users (id, username, password_hash, role, display_name)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING {_USER_COLUMNS}
            """,
            user_id,
            username,
            password_hash,
            role,
            display_name,
        )
        return dict(row)


async def update_profile(user_id: uuid.UUID, **fields: Any) -> dict | None:
    """Dynamic update of user profile fields.

    Only fields explicitly passed as keyword arguments are updated.
    A value of ``None`` means "clear this field" (set to NULL in the database).
    Fields not present in *fields* are left unchanged.
    """
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
    import re

    for field_name, value in fields.items():
        if field_name not in _ALLOWED_FIELDS:
            continue
        if not re.match(r"^[a-z_]+$", field_name):
            raise ValueError(f"Invalid field name: {field_name}")
        # Include the field whether the value is a string or None (clear).
        set_parts.append(f"{field_name} = ${idx}")
        values.append(value)
        idx += 1

    if not set_parts:
        return await find_by_id(user_id)

    values.append(user_id)
    query = (
        f"UPDATE users SET {', '.join(set_parts)}, updated_at = NOW() "
        f"WHERE id = ${idx} RETURNING {_USER_COLUMNS}"
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
            f"UPDATE users SET role = $1, updated_at = NOW() WHERE id = $2 AND is_deleted = false RETURNING {_USER_COLUMNS}",  # noqa: E501
            new_role,
            user_id,
        )
        return dict(row) if row else None


async def update_role_in_conn(user_id: uuid.UUID, new_role: str, conn: Any) -> dict | None:
    """Update role within an existing connection/transaction."""
    row = await conn.fetchrow(
        f"UPDATE users SET role = $1, updated_at = NOW() WHERE id = $2 AND is_deleted = false RETURNING {_USER_COLUMNS}",  # noqa: E501
        new_role,
        user_id,
    )
    return dict(row) if row else None


async def count_super_admins_for_update(conn: Any) -> int:
    """Count SUPER_ADMIN users with FOR UPDATE lock to prevent TOCTOU races.

    Uses a subquery so that FOR UPDATE locks the rows while the outer COUNT(*)
    aggregates them — PostgreSQL does not allow FOR UPDATE directly on aggregate queries.
    """
    result = await conn.fetchval(
        """
        SELECT COUNT(*) FROM (
            SELECT id FROM users
            WHERE role = 'SUPER_ADMIN' AND is_deleted = false
            FOR UPDATE
        ) AS locked_admins
        """,
    )
    return int(result)


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
            pattern = f"%{_escape_ilike(search)}%"
            rows = await conn.fetch(
                f"SELECT {_USER_COLUMNS}, COUNT(*) OVER() AS _total FROM users"
                " WHERE is_deleted = false"
                " AND (username ILIKE $1 ESCAPE '\\' OR display_name ILIKE $1 ESCAPE '\\')"
                " ORDER BY created_at DESC OFFSET $2 LIMIT $3",
                pattern,
                offset,
                page_size,
            )
        else:
            rows = await conn.fetch(
                f"SELECT {_USER_COLUMNS}, COUNT(*) OVER() AS _total FROM users"
                " WHERE is_deleted = false"
                " ORDER BY created_at DESC OFFSET $1 LIMIT $2",
                offset,
                page_size,
            )
        if rows:
            total = rows[0]["_total"]
            return [{k: v for k, v in dict(r).items() if k != "_total"} for r in rows], total
        return [], 0


async def search_users(query: str, limit: int = 20) -> list[dict]:
    """Search users by username or display_name with proper ILIKE escaping."""
    pool = get_pool()
    pattern = f"%{_escape_ilike(query)}%"
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, username, display_name, avatar_url FROM users"
            " WHERE is_deleted = false"
            " AND (username ILIKE $1 ESCAPE '\\' OR display_name ILIKE $1 ESCAPE '\\')"
            " ORDER BY username ASC"
            " LIMIT $2",
            pattern,
            limit,
        )
        return [dict(r) for r in rows]


async def search_users_for_coauthor(query: str, limit: int = 5) -> list[dict]:
    """Search active, non-banned users for co-author invitation.

    Uses _escape_ilike to neutralise ILIKE wildcards (%, _) in user input
    and ESCAPE '\\' so the database applies the escaping correctly.
    """
    pool = get_pool()
    pattern = f"%{_escape_ilike(query)}%"
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, username, display_name, avatar_url FROM users"
            " WHERE is_deleted = false AND is_banned = false"
            " AND (display_name ILIKE $1 ESCAPE '\\' OR username ILIKE $1 ESCAPE '\\')"
            " ORDER BY display_name"
            " LIMIT $2",
            pattern,
            limit,
        )
        return [dict(r) for r in rows]


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


async def count_super_admins_excluding(
    user_ids: list[uuid.UUID], conn: Any = None
) -> int:
    """Count SUPER_ADMIN users not in the given list (non-deleted)."""
    query = (
        "SELECT COUNT(*) FROM users "
        "WHERE role = 'SUPER_ADMIN' AND is_deleted = false "
        "AND id != ALL($1::uuid[])"
    )
    if conn:
        result = await conn.fetchval(query, user_ids)
    else:
        pool = get_pool()
        async with pool.acquire() as c:
            result = await c.fetchval(query, user_ids)
    return int(result)


async def get_storage_used(user_id: uuid.UUID) -> int:
    """Return the DB-tracked storage_used_bytes for a user."""
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT storage_used_bytes FROM users WHERE id = $1", user_id)
    return int(row["storage_used_bytes"]) if row else 0


async def find_all_members(
    offset: int = 0,
    limit: int = 24,
    search: str | None = None,
) -> tuple[list[dict], int]:
    """Return non-guest, non-deleted users with pagination and optional search."""
    pool = get_pool()
    async with pool.acquire() as conn:
        base_where = "WHERE u.is_deleted = false AND u.role != 'GUEST'"
        params: list = []
        idx = 1

        if search:
            escaped = _escape_ilike(search)
            base_where += f" AND (u.display_name ILIKE ${idx} ESCAPE '\\' OR u.username ILIKE ${idx} ESCAPE '\\')"
            params.append(f"%{escaped}%")
            idx += 1

        params.append(limit)
        params.append(offset)

        rows = await conn.fetch(
            f"""
            SELECT u.id, u.username, u.display_name, u.role,
                   u.avatar_url, u.affiliation, u.bio,
                   COUNT(*) OVER() AS _total
            FROM users u
            {base_where}
            ORDER BY u.display_name ASC
            LIMIT ${idx} OFFSET ${idx + 1}
            """,
            *params,
        )
        if not rows:
            return [], 0
        total = rows[0]["_total"]
        items = [{k: v for k, v in dict(r).items() if k != "_total"} for r in rows]
        return items, total

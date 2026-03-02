import uuid
from typing import Any

from app.core.database import get_pool


async def insert(
    sig_id: uuid.UUID, name: str, description: str | None, creator_id: uuid.UUID, conn: Any
) -> dict:
    row = await conn.fetchrow(
        """
        INSERT INTO sigs (id, name, description, created_by, member_count)
        VALUES ($1, $2, $3, $4, 1)
        RETURNING *
        """,
        sig_id,
        name,
        description,
        creator_id,
    )
    return dict(row)


async def add_member(
    member_id: uuid.UUID, sig_id: uuid.UUID, user_id: uuid.UUID, role: str, conn: Any
) -> None:
    await conn.execute(
        "INSERT INTO sig_members (id, sig_id, user_id, role) VALUES ($1, $2, $3, $4)",
        member_id,
        sig_id,
        user_id,
        role,
    )


async def find_creator_display_name(user_id: uuid.UUID, conn: Any) -> str | None:
    row = await conn.fetchrow("SELECT display_name FROM users WHERE id = $1", user_id)
    return row["display_name"] if row else None


async def find_by_id(sig_id: uuid.UUID) -> dict | None:
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT s.*, u.display_name AS creator_display_name
            FROM sigs s
            LEFT JOIN users u ON s.created_by = u.id
            WHERE s.id = $1 AND s.is_deleted = false
            """,
            sig_id,
        )
        return dict(row) if row else None


async def find_many(offset: int = 0, limit: int = 50) -> tuple[list[dict], int]:
    pool = get_pool()
    async with pool.acquire() as conn:
        total = await conn.fetchval(
            "SELECT COUNT(*) FROM sigs WHERE is_deleted = false",
        )
        rows = await conn.fetch(
            """
            SELECT s.*, u.display_name AS creator_display_name
            FROM sigs s
            LEFT JOIN users u ON s.created_by = u.id
            WHERE s.is_deleted = false
            ORDER BY s.created_at DESC
            LIMIT $1 OFFSET $2
            """,
            limit,
            offset,
        )
        return [dict(r) for r in rows], total


async def update(sig_id: uuid.UUID, name: str, description: str | None) -> dict | None:
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            WITH updated AS (
                UPDATE sigs SET name = $1, description = $2, updated_at = NOW()
                WHERE id = $3 AND is_deleted = false
                RETURNING *
            )
            SELECT u.*, usr.display_name AS creator_display_name
            FROM updated u
            LEFT JOIN users usr ON usr.id = u.created_by
            """,
            name,
            description,
            sig_id,
        )
        if not row:
            return None
        return dict(row)


async def soft_delete(sig_id: uuid.UUID) -> bool:
    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            result = await conn.execute(
                "UPDATE sigs SET is_deleted = true, updated_at = NOW() WHERE id = $1 AND is_deleted = false",  # noqa: E501
                sig_id,
            )
            if result != "UPDATE 1":
                return False
            await conn.execute(
                "UPDATE posts SET is_deleted = true, updated_at = NOW() WHERE sig_id = $1 AND is_deleted = false",  # noqa: E501
                sig_id,
            )
            return True


async def remove_member(sig_id: uuid.UUID, user_id: uuid.UUID) -> bool:
    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            result = await conn.execute(
                "DELETE FROM sig_members WHERE sig_id = $1 AND user_id = $2",
                sig_id,
                user_id,
            )
            if result != "DELETE 1":
                return False
            await conn.execute(
                "UPDATE sigs SET member_count = GREATEST(member_count - 1, 0) WHERE id = $1",
                sig_id,
            )
            return True


async def get_member_role(sig_id: uuid.UUID, user_id: uuid.UUID) -> str | None:
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT role FROM sig_members WHERE sig_id = $1 AND user_id = $2",
            sig_id,
            user_id,
        )
        return row["role"] if row else None


async def get_member_role_in_conn(sig_id: uuid.UUID, user_id: uuid.UUID, conn: Any) -> str | None:
    row = await conn.fetchrow(
        "SELECT role FROM sig_members WHERE sig_id = $1 AND user_id = $2",
        sig_id,
        user_id,
    )
    return row["role"] if row else None


async def count_admins(sig_id: uuid.UUID, conn: Any) -> int:
    """Count admins with FOR UPDATE lock to serialize concurrent leave/demote operations.

    Excludes soft-deleted users so that deactivated accounts are not counted as active admins.
    """
    rows = await conn.fetch(
        """
        SELECT sm.id FROM sig_members sm
        JOIN users u ON sm.user_id = u.id
        WHERE sm.sig_id = $1 AND sm.role = 'ADMIN' AND u.is_deleted = false
        FOR UPDATE
        """,
        sig_id,
    )
    return len(rows)


async def delete_member(sig_id: uuid.UUID, user_id: uuid.UUID, conn: Any) -> bool:
    result = await conn.execute(
        "DELETE FROM sig_members WHERE sig_id = $1 AND user_id = $2",
        sig_id,
        user_id,
    )
    if result != "DELETE 1":
        return False
    await conn.execute(
        "UPDATE sigs SET member_count = GREATEST(member_count - 1, 0) WHERE id = $1",
        sig_id,
    )
    return True


async def update_member_role(sig_id: uuid.UUID, user_id: uuid.UUID, role: str) -> dict | None:
    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            return await update_member_role_in_conn(sig_id, user_id, role, conn)


async def update_member_role_in_conn(
    sig_id: uuid.UUID, user_id: uuid.UUID, role: str, conn: Any
) -> dict | None:
    """Update or insert a member's role within an existing connection/transaction."""
    sig = await conn.fetchrow(
        "SELECT id FROM sigs WHERE id = $1 AND is_deleted = false",
        sig_id,
    )
    if not sig:
        return None

    existing = await conn.fetchrow(
        "SELECT id FROM sig_members WHERE sig_id = $1 AND user_id = $2",
        sig_id,
        user_id,
    )

    if existing:
        await conn.execute(
            "UPDATE sig_members SET role = $1, updated_at = NOW() WHERE id = $2",
            role,
            existing["id"],
        )
    else:
        member_id = uuid.uuid4()
        await conn.execute(
            "INSERT INTO sig_members (id, sig_id, user_id, role) VALUES ($1, $2, $3, $4)",
            member_id,
            sig_id,
            user_id,
            role,
        )
        await conn.execute(
            "UPDATE sigs SET member_count = member_count + 1 WHERE id = $1",
            sig_id,
        )

    row = await conn.fetchrow(
        """
        SELECT sm.*, u.display_name, u.username
        FROM sig_members sm
        JOIN users u ON sm.user_id = u.id
        WHERE sm.sig_id = $1 AND sm.user_id = $2
        """,
        sig_id,
        user_id,
    )
    return dict(row) if row else None


async def join_member(sig_id: uuid.UUID, user_id: uuid.UUID, conn: Any) -> dict | None:
    """Insert a new MEMBER row. Returns the member row with user info, or None if SIG not found."""
    sig = await conn.fetchrow(
        "SELECT id FROM sigs WHERE id = $1 AND is_deleted = false",
        sig_id,
    )
    if not sig:
        return None

    member_id = uuid.uuid4()
    await conn.execute(
        "INSERT INTO sig_members (id, sig_id, user_id, role) VALUES ($1, $2, $3, 'MEMBER')",
        member_id,
        sig_id,
        user_id,
    )
    await conn.execute(
        "UPDATE sigs SET member_count = member_count + 1 WHERE id = $1",
        sig_id,
    )
    row = await conn.fetchrow(
        """
        SELECT sm.*, u.display_name, u.username
        FROM sig_members sm
        JOIN users u ON sm.user_id = u.id
        WHERE sm.id = $1
        """,
        member_id,
    )
    return dict(row) if row else None


async def find_by_user(user_id: uuid.UUID) -> list[dict]:
    """Return all SIGs that a user is a member of."""
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT s.*, u.display_name AS creator_display_name, sm.role AS my_role
            FROM sig_members sm
            JOIN sigs s ON sm.sig_id = s.id
            LEFT JOIN users u ON s.created_by = u.id
            WHERE sm.user_id = $1 AND s.is_deleted = false
            ORDER BY sm.created_at DESC
            """,
            user_id,
        )
        return [dict(r) for r in rows]


async def find_members(
    sig_id: uuid.UUID,
    offset: int = 0,
    limit: int = 50,
) -> tuple[list[dict], int]:
    pool = get_pool()
    async with pool.acquire() as conn:
        total = await conn.fetchval(
            "SELECT COUNT(*) FROM sig_members WHERE sig_id = $1",
            sig_id,
        )
        rows = await conn.fetch(
            """
            SELECT sm.*, u.display_name, u.username, u.avatar_url
            FROM sig_members sm
            JOIN users u ON sm.user_id = u.id
            WHERE sm.sig_id = $1
            ORDER BY sm.created_at ASC
            LIMIT $2 OFFSET $3
            """,
            sig_id,
            limit,
            offset,
        )
        return [dict(r) for r in rows], total

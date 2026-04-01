import uuid

from app.core.database import get_pool

# Valid categories in display order
CATEGORIES = ("chair", "co_chair", "ec_member", "sig_chair", "member", "sre")


async def find_all_grouped() -> list[dict]:
    """Return all classifications joined with user info, ordered by category rank then display_order."""
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT mc.id, mc.user_id, mc.category, mc.display_order,
                   u.username, u.display_name, u.avatar_url
            FROM member_classifications mc
            JOIN users u ON u.id = mc.user_id
            WHERE u.is_deleted = false
            ORDER BY
                CASE mc.category
                    WHEN 'chair' THEN 0
                    WHEN 'co_chair' THEN 1
                    WHEN 'ec_member' THEN 2
                    WHEN 'sig_chair' THEN 3
                    WHEN 'member' THEN 4
                    WHEN 'sre' THEN 5
                END,
                mc.display_order ASC,
                u.display_name ASC
            """
        )
        return [dict(r) for r in rows]


async def find_by_user_id(user_id: uuid.UUID) -> dict | None:
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM member_classifications WHERE user_id = $1", user_id
        )
        return dict(row) if row else None


async def find_by_category(category: str) -> list[dict]:
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT mc.id, mc.user_id, mc.category, mc.display_order,
                   u.username, u.display_name, u.avatar_url
            FROM member_classifications mc
            JOIN users u ON u.id = mc.user_id
            WHERE mc.category = $1 AND u.is_deleted = false
            ORDER BY mc.display_order ASC, u.display_name ASC
            """,
            category,
        )
        return [dict(r) for r in rows]


async def count_by_category() -> dict[str, int]:
    """Return {category: count} for all categories."""
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT mc.category, COUNT(*) AS cnt
            FROM member_classifications mc
            JOIN users u ON u.id = mc.user_id
            WHERE u.is_deleted = false
            GROUP BY mc.category
            """
        )
        return {r["category"]: r["cnt"] for r in rows}


async def upsert(
    user_id: uuid.UUID, category: str, display_order: int, assigned_by: uuid.UUID
) -> dict:
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO member_classifications (id, user_id, category, display_order, assigned_by)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (user_id) DO UPDATE
                SET category = EXCLUDED.category,
                    display_order = EXCLUDED.display_order,
                    assigned_by = EXCLUDED.assigned_by
            RETURNING *
            """,
            uuid.uuid4(),
            user_id,
            category,
            display_order,
            assigned_by,
        )
        return dict(row)


async def delete_by_user_id(user_id: uuid.UUID) -> bool:
    pool = get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM member_classifications WHERE user_id = $1", user_id
        )
        return bool(result == "DELETE 1")


async def find_unclassified_members() -> list[dict]:
    """Return active non-guest users who have no classification at all."""
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT u.id AS user_id, u.username, u.display_name, u.avatar_url
            FROM users u
            WHERE u.is_deleted = false
              AND u.role != 'GUEST'
              AND u.id NOT IN (SELECT mc.user_id FROM member_classifications mc)
            ORDER BY u.display_name ASC
            """
        )
        return [dict(r) for r in rows]


async def count_unclassified_members() -> int:
    pool = get_pool()
    async with pool.acquire() as conn:
        val = await conn.fetchval(
            """
            SELECT COUNT(*) FROM users u
            WHERE u.is_deleted = false
              AND u.role != 'GUEST'
              AND u.id NOT IN (SELECT mc.user_id FROM member_classifications mc)
            """
        )
        return int(val)


async def count_in_category(category: str) -> int:
    pool = get_pool()
    async with pool.acquire() as conn:
        val = await conn.fetchval(
            """
            SELECT COUNT(*) FROM member_classifications mc
            JOIN users u ON u.id = mc.user_id
            WHERE mc.category = $1 AND u.is_deleted = false
            """,
            category,
        )
        return int(val)

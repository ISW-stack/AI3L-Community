import uuid

from app.core.database import get_pool


async def find_all() -> list[dict]:
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM contributors ORDER BY display_order ASC, created_at ASC"
        )
        return [dict(r) for r in rows]


async def find_by_id(contributor_id: uuid.UUID) -> dict | None:
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM contributors WHERE id = $1", contributor_id
        )
        return dict(row) if row else None


async def insert(
    contributor_id: uuid.UUID,
    github_username: str,
    display_name: str,
    role: str,
    display_order: int,
) -> dict:
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO contributors (id, github_username, display_name, role, display_order)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING *
            """,
            contributor_id,
            github_username,
            display_name,
            role,
            display_order,
        )
        return dict(row)


async def update(
    contributor_id: uuid.UUID,
    github_username: str,
    display_name: str,
    role: str,
    display_order: int,
) -> dict | None:
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            UPDATE contributors
            SET github_username = $1, display_name = $2, role = $3,
                display_order = $4, updated_at = now()
            WHERE id = $5
            RETURNING *
            """,
            github_username,
            display_name,
            role,
            display_order,
            contributor_id,
        )
        return dict(row) if row else None


async def delete(contributor_id: uuid.UUID) -> bool:
    pool = get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM contributors WHERE id = $1", contributor_id
        )
        return bool(result == "DELETE 1")


async def exists_by_github(github_username: str) -> bool:
    pool = get_pool()
    async with pool.acquire() as conn:
        count = await conn.fetchval(
            "SELECT COUNT(*) FROM contributors WHERE github_username = $1",
            github_username,
        )
        return bool(count > 0)

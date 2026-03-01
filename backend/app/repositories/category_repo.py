import uuid

from app.core.database import get_pool


async def insert(cat_id: uuid.UUID, name: str, description: str | None) -> dict:
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO categories (id, name, description)
            VALUES ($1, $2, $3)
            RETURNING *
            """,
            cat_id,
            name,
            description,
        )
        return dict(row)


async def find_by_id(category_id: uuid.UUID) -> dict | None:
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM categories WHERE id = $1", category_id)
        return dict(row) if row else None


async def find_all() -> list[dict]:
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM categories ORDER BY name ASC")
        return [dict(r) for r in rows]


async def update(category_id: uuid.UUID, name: str, description: str | None) -> dict | None:
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "UPDATE categories SET name = $1, description = $2 WHERE id = $3 RETURNING *",
            name,
            description,
            category_id,
        )
        return dict(row) if row else None


async def delete(category_id: uuid.UUID) -> bool:
    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                "UPDATE posts SET category_id = NULL WHERE category_id = $1",
                category_id,
            )
            result = await conn.execute(
                "DELETE FROM categories WHERE id = $1",
                category_id,
            )
            return bool(result == "DELETE 1")


async def exists_by_name(name: str) -> bool:
    pool = get_pool()
    async with pool.acquire() as conn:
        count = await conn.fetchval("SELECT COUNT(*) FROM categories WHERE name = $1", name)
        return bool(count > 0)

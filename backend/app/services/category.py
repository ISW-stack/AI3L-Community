import uuid

from loguru import logger

from app.core.database import get_pool


async def create_category(name: str, description: str | None = None) -> dict:
    pool = get_pool()
    cat_id = uuid.uuid4()
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
        logger.info("Category created", extra={"category_id": str(cat_id), "name": name})
        return dict(row)


async def list_categories() -> list[dict]:
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM categories ORDER BY name ASC")
        return [dict(r) for r in rows]


async def get_category_by_id(category_id: uuid.UUID) -> dict | None:
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM categories WHERE id = $1", category_id)
        return dict(row) if row else None


async def category_exists(name: str) -> bool:
    pool = get_pool()
    async with pool.acquire() as conn:
        count = await conn.fetchval("SELECT COUNT(*) FROM categories WHERE name = $1", name)
        return count > 0

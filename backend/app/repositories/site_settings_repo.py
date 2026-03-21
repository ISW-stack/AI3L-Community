from typing import cast

from app.core.database import get_pool


async def get(key: str) -> str | None:
    pool = get_pool()
    async with pool.acquire() as conn:
        val = await conn.fetchval("SELECT value FROM site_settings WHERE key = $1", key)
        return cast(str | None, val)


async def get_many(keys: list[str]) -> dict[str, str]:
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT key, value FROM site_settings WHERE key = ANY($1)", keys)
        return {r["key"]: r["value"] for r in rows}


async def upsert(key: str, value: str) -> None:
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO site_settings (key, value, updated_at)
            VALUES ($1, $2, now())
            ON CONFLICT (key) DO UPDATE SET value = $2, updated_at = now()
            """,
            key,
            value,
        )

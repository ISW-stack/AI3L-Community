import uuid
from typing import Any

from app.core.database import get_pool


async def find_all_overrides() -> list[dict]:
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM org_chart_overrides ORDER BY entity_type, display_order"
        )
        return [dict(r) for r in rows]


async def find_override(entity_type: str, entity_id: uuid.UUID) -> dict | None:
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM org_chart_overrides WHERE entity_type = $1 AND entity_id = $2",
            entity_type,
            entity_id,
        )
        return dict(row) if row else None


async def upsert_override(
    entity_type: str,
    entity_id: uuid.UUID,
    updated_by: uuid.UUID,
    custom_title: str | None = None,
    custom_description: str | None = None,
    display_order: int | None = None,
    is_visible: bool | None = None,
) -> dict:
    pool = get_pool()
    async with pool.acquire() as conn:
        existing = await conn.fetchrow(
            "SELECT * FROM org_chart_overrides WHERE entity_type = $1 AND entity_id = $2",
            entity_type,
            entity_id,
        )

        if existing:
            row = await conn.fetchrow(
                """
                UPDATE org_chart_overrides
                SET custom_title = COALESCE($1, custom_title),
                    custom_description = COALESCE($2, custom_description),
                    display_order = COALESCE($3, display_order),
                    is_visible = COALESCE($4, is_visible),
                    updated_by = $5,
                    updated_at = NOW()
                WHERE entity_type = $6 AND entity_id = $7
                RETURNING *
                """,
                custom_title,
                custom_description,
                display_order,
                is_visible,
                updated_by,
                entity_type,
                entity_id,
            )
        else:
            row = await conn.fetchrow(
                """
                INSERT INTO org_chart_overrides
                    (entity_type, entity_id, custom_title, custom_description,
                     display_order, is_visible, updated_by)
                VALUES ($1, $2, $3, $4, COALESCE($5, 0), COALESCE($6, true), $7)
                RETURNING *
                """,
                entity_type,
                entity_id,
                custom_title,
                custom_description,
                display_order,
                is_visible,
                updated_by,
            )
        return dict(row)

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
    *,
    _provided_fields: set[str] | None = None,
) -> dict:
    """Upsert an org chart override.

    ``_provided_fields`` lists field names explicitly sent by the caller
    (including those set to ``None``).  Fields NOT in this set keep their
    current DB value on UPDATE; fields present in it are written as-is —
    allowing the caller to clear a value to NULL.

    On INSERT every field is written (missing ones default to 0 / true).
    """
    provided = _provided_fields or set()
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO org_chart_overrides
                (entity_type, entity_id, custom_title, custom_description,
                 display_order, is_visible, updated_by)
            VALUES ($1, $2, $3, $4, COALESCE($5, 0), COALESCE($6, true), $7)
            ON CONFLICT (entity_type, entity_id) DO UPDATE SET
                custom_title = CASE WHEN $8 THEN $3
                                    ELSE org_chart_overrides.custom_title END,
                custom_description = CASE WHEN $9 THEN $4
                                          ELSE org_chart_overrides.custom_description END,
                display_order = CASE WHEN $10 THEN COALESCE($5, 0)
                                     ELSE org_chart_overrides.display_order END,
                is_visible = CASE WHEN $11 THEN COALESCE($6, true)
                                  ELSE org_chart_overrides.is_visible END,
                updated_by = $7,
                updated_at = NOW()
            RETURNING *
            """,
            entity_type,
            entity_id,
            custom_title,
            custom_description,
            display_order,
            is_visible,
            updated_by,
            "custom_title" in provided,        # $8
            "custom_description" in provided,  # $9
            "display_order" in provided,       # $10
            "is_visible" in provided,          # $11
        )
        return dict(row)

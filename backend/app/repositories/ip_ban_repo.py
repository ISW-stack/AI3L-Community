import uuid
from datetime import datetime

from app.core.database import get_pool


async def find_by_ip(ip: str) -> dict | None:
    """Find an active (non-expired) ban for the given IP address."""
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT * FROM ip_bans
            WHERE ip_address = $1
              AND (expires_at IS NULL OR expires_at > NOW())
            """,
            ip,
        )
    return dict(row) if row else None


async def list_all(page: int = 1, page_size: int = 50) -> tuple[list[dict], int]:
    """Return paginated list of all IP bans with total count."""
    pool = get_pool()
    offset = (page - 1) * page_size
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT *, COUNT(*) OVER() AS _total
            FROM ip_bans
            ORDER BY created_at DESC
            LIMIT $1 OFFSET $2
            """,
            page_size,
            offset,
        )
    if not rows:
        return [], 0
    total = rows[0]["_total"]
    return [{k: v for k, v in dict(r).items() if k != "_total"} for r in rows], total


async def create(
    ban_id: uuid.UUID,
    ip: str,
    reason: str,
    banned_by: uuid.UUID,
    expires_at: datetime | None = None,
) -> dict:
    """Insert a new IP ban and return the created row."""
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO ip_bans (id, ip_address, reason, banned_by, expires_at)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING *
            """,
            ban_id,
            ip,
            reason,
            banned_by,
            expires_at,
        )
    return dict(row)  # type: ignore[arg-type]


async def delete(ban_id: uuid.UUID) -> bool:
    """Delete an IP ban by ID. Returns True if a row was deleted."""
    pool = get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM ip_bans WHERE id = $1",
            ban_id,
        )
    return bool(result == "DELETE 1")

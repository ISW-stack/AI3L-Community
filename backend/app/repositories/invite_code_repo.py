from app.core.database import get_pool


async def find_many(
    status_filter: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> tuple[list[dict], int]:
    pool = get_pool()
    async with pool.acquire() as conn:
        base_where = "WHERE 1=1"

        if status_filter == "active":
            base_where += (
                " AND ic.consumed_at IS NULL"
                " AND (ic.expires_at IS NULL OR ic.expires_at > NOW())"
            )
        elif status_filter == "consumed":
            base_where += " AND ic.consumed_at IS NOT NULL"
        elif status_filter == "expired":
            base_where += (
                " AND ic.consumed_at IS NULL"
                " AND ic.expires_at IS NOT NULL AND ic.expires_at <= NOW()"
            )

        total = await conn.fetchval(
            f"SELECT COUNT(*) FROM invite_codes ic {base_where}",
        )

        rows = await conn.fetch(
            f"""
            SELECT ic.id, ic.code, ic.creator_id, ic.consumed_by, ic.consumed_at,
                   ic.expires_at, ic.created_at,
                   u.username AS creator_username,
                   cu.username AS consumed_by_username
            FROM invite_codes ic
            LEFT JOIN users u ON u.id = ic.creator_id
            LEFT JOIN users cu ON cu.id = ic.consumed_by
            {base_where}
            ORDER BY ic.created_at DESC
            LIMIT $1 OFFSET $2
            """,
            limit,
            offset,
        )
        return [dict(r) for r in rows], total or 0

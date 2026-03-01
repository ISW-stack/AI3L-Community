"""Invite code listing service."""

from app.core.database import get_pool


async def list_invite_codes(
    status_filter: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> tuple[list[dict], int]:
    """Return paginated invite codes with status derived from consumed_at/expires_at."""
    pool = get_pool()
    async with pool.acquire() as conn:
        base_where = "WHERE 1=1"
        params: list = []
        param_idx = 1

        if status_filter == "active":
            base_where += (
                f" AND ic.consumed_at IS NULL"
                f" AND (ic.expires_at IS NULL OR ic.expires_at > NOW())"
            )
        elif status_filter == "consumed":
            base_where += f" AND ic.consumed_at IS NOT NULL"
        elif status_filter == "expired":
            base_where += (
                f" AND ic.consumed_at IS NULL"
                f" AND ic.expires_at IS NOT NULL AND ic.expires_at <= NOW()"
            )

        total = await conn.fetchval(
            f"SELECT COUNT(*) FROM invite_codes ic {base_where}",
            *params,
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
            LIMIT ${param_idx} OFFSET ${param_idx + 1}
            """,
            *params,
            limit,
            offset,
        )

        codes = []
        for r in rows:
            row = dict(r)
            if row.get("consumed_at"):
                row["status"] = "consumed"
            elif row.get("expires_at") and row["expires_at"].timestamp() < __import__("time").time():
                row["status"] = "expired"
            else:
                row["status"] = "active"
            codes.append(row)

        return codes, total or 0

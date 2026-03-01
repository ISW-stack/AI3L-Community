import uuid

from app.core.database import get_pool


async def insert(
    log_id: uuid.UUID,
    user_id: uuid.UUID,
    action: str,
    target_type: str | None,
    target_id: uuid.UUID | None,
    ip_address: str | None,
) -> None:
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO audit_logs (id, user_id, action, target_type, target_id, ip_address)
            VALUES ($1, $2, $3, $4, $5, $6)
            """,
            log_id,
            user_id,
            action,
            target_type,
            target_id,
            ip_address,
        )


async def find_many(
    page: int = 1,
    page_size: int = 50,
    user_id_filter: uuid.UUID | None = None,
) -> tuple[list[dict], int]:
    pool = get_pool()
    offset = (page - 1) * page_size

    where = ""
    params: list = []
    idx = 1

    if user_id_filter:
        where = f"WHERE al.user_id = ${idx}"
        params.append(user_id_filter)
        idx += 1

    async with pool.acquire() as conn:
        total = await conn.fetchval(
            f"SELECT COUNT(*) FROM audit_logs al {where}",
            *params,
        )

        params.extend([page_size, offset])
        rows = await conn.fetch(
            f"""
            SELECT al.*, u.username, u.display_name
            FROM audit_logs al
            LEFT JOIN users u ON u.id = al.user_id
            {where}
            ORDER BY al.created_at DESC
            LIMIT ${idx} OFFSET ${idx + 1}
            """,
            *params,
        )
        return [dict(r) for r in rows], total

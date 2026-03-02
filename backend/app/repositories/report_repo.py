import uuid

from app.core.database import get_pool


async def insert(
    report_id: uuid.UUID, post_id: uuid.UUID, user_id: uuid.UUID, reason: str
) -> dict | None:
    pool = get_pool()
    async with pool.acquire() as conn:
        existing = await conn.fetchval(
            "SELECT id FROM post_reports WHERE post_id = $1 AND user_id = $2 AND status = 'PENDING'",  # noqa: E501
            post_id,
            user_id,
        )
        if existing:
            return None  # duplicate

        row = await conn.fetchrow(
            """
            INSERT INTO post_reports (id, post_id, user_id, reason)
            VALUES ($1, $2, $3, $4)
            RETURNING *
            """,
            report_id,
            post_id,
            user_id,
            reason,
        )
        return dict(row)


async def find_many(
    status_filter: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> tuple[list[dict], int]:
    pool = get_pool()

    where = ""
    params: list = []
    idx = 1

    if status_filter:
        where = f"WHERE status = ${idx}"
        params.append(status_filter)
        idx += 1

    # Save params before extending with LIMIT/OFFSET for potential fallback count query
    count_params = list(params)

    async with pool.acquire() as conn:
        params.extend([limit, offset])
        rows = await conn.fetch(
            f"SELECT *, COUNT(*) OVER() AS _total FROM post_reports {where} ORDER BY created_at DESC LIMIT ${idx} OFFSET ${idx + 1}",  # noqa: E501
            *params,
        )
        if rows:
            total = rows[0]["_total"]
            result = [{k: v for k, v in dict(r).items() if k != "_total"} for r in rows]
        else:
            # Page may be out of range — do a separate count to get real total
            total = await conn.fetchval(
                f"SELECT COUNT(*) FROM post_reports {where}",
                *count_params,
            )
            result = []
        return result, total


async def update_status(
    report_id: uuid.UUID,
    reviewer_id: uuid.UUID,
    new_status: str,
) -> dict | None:
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            UPDATE post_reports
            SET status = $1, reviewed_by = $2, reviewed_at = NOW(), updated_at = NOW()
            WHERE id = $3 AND status = 'PENDING'
            RETURNING *
            """,
            new_status,
            reviewer_id,
            report_id,
        )
        return dict(row) if row else None

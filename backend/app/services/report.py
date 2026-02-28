import uuid

from loguru import logger

from app.core.database import get_pool


async def create_report(post_id: uuid.UUID, user_id: str, reason: str) -> dict:
    pool = get_pool()
    report_id = uuid.uuid4()

    async with pool.acquire() as conn:
        # Check for duplicate report
        existing = await conn.fetchval(
            "SELECT id FROM post_reports WHERE post_id = $1 AND user_id = $2 AND status = 'PENDING'",
            post_id,
            uuid.UUID(user_id),
        )
        if existing:
            raise ValueError("You have already reported this post.")

        row = await conn.fetchrow(
            """
            INSERT INTO post_reports (id, post_id, user_id, reason)
            VALUES ($1, $2, $3, $4)
            RETURNING *
            """,
            report_id,
            post_id,
            uuid.UUID(user_id),
            reason,
        )
        logger.info("Report created", extra={"report_id": str(report_id), "post_id": str(post_id)})
        return _row_to_report(dict(row))


async def list_reports(
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

    async with pool.acquire() as conn:
        total = await conn.fetchval(
            f"SELECT COUNT(*) FROM post_reports {where}",
            *params,
        )
        params.extend([limit, offset])
        rows = await conn.fetch(
            f"SELECT * FROM post_reports {where} ORDER BY created_at DESC LIMIT ${idx} OFFSET ${idx + 1}",
            *params,
        )
        return [_row_to_report(dict(r)) for r in rows], total


async def review_report(report_id: uuid.UUID, reviewer_id: str, new_status: str) -> dict | None:
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
            uuid.UUID(reviewer_id),
            report_id,
        )
        if not row:
            return None
        logger.info("Report reviewed", extra={"report_id": str(report_id), "status": new_status})
        return _row_to_report(dict(row))


def _row_to_report(row: dict) -> dict:
    return {
        "id": str(row["id"]),
        "post_id": str(row["post_id"]),
        "user_id": str(row["user_id"]),
        "reason": row["reason"],
        "status": row["status"],
        "reviewed_by": str(row["reviewed_by"]) if row.get("reviewed_by") else None,
        "reviewed_at": row["reviewed_at"].isoformat() if row.get("reviewed_at") else None,
        "created_at": row["created_at"].isoformat(),
    }

import uuid
from datetime import datetime, timezone

from app.core.database import get_pool


async def insert(app_id: uuid.UUID, user_id: uuid.UUID, description: str) -> dict | None:
    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                """
                INSERT INTO membership_applications (id, user_id, description, status, created_at)
                SELECT $1, $2, $3, 'PENDING', NOW()
                WHERE NOT EXISTS (
                    SELECT 1 FROM membership_applications
                    WHERE user_id = $2 AND status = 'PENDING'
                )
                RETURNING *
                """,
                app_id,
                user_id,
                description,
            )
            return dict(row) if row else None


async def find_many(
    status_filter: str | None = None, offset: int = 0, limit: int = 50
) -> tuple[list[dict], int]:
    pool = get_pool()
    async with pool.acquire() as conn:
        where = ""
        params: list = []
        idx = 1
        if status_filter:
            where = f"WHERE ma.status = ${idx}"
            params.append(status_filter)
            idx += 1

        total = await conn.fetchval(
            f"SELECT COUNT(*) FROM membership_applications ma {where}",
            *params,
        )

        params.extend([offset, limit])
        rows = await conn.fetch(
            f"""
            SELECT ma.*, u.username, u.display_name
            FROM membership_applications ma
            JOIN users u ON u.id = ma.user_id
            {where}
            ORDER BY ma.created_at DESC
            OFFSET ${idx} LIMIT ${idx + 1}
            """,
            *params,
        )
        return [dict(r) for r in rows], total


async def update_status(
    app_id: uuid.UUID,
    reviewer_id: uuid.UUID,
    action: str,
) -> dict | None:
    """Update application status and optionally promote user. Returns updated row."""
    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                """
                UPDATE membership_applications
                SET status = $1, reviewed_by = $2, reviewed_at = $3
                WHERE id = $4 AND status = 'PENDING'
                RETURNING *
                """,
                action,
                reviewer_id,
                datetime.now(timezone.utc),
                app_id,
            )
            if row is None:
                return None

            if action == "APPROVED":
                result = await conn.execute(
                    "UPDATE users SET role = 'MEMBER', updated_at = NOW() WHERE id = $1 AND role = 'GUEST'",  # noqa: E501
                    row["user_id"],
                )
                if result != "UPDATE 1":
                    raise ValueError(
                        "User role was not updated: user may have been deleted "
                        "or is no longer a guest."
                    )

            return dict(row)


async def find_pending_by_user(user_id: uuid.UUID) -> bool:
    pool = get_pool()
    async with pool.acquire() as conn:
        count = await conn.fetchval(
            "SELECT COUNT(*) FROM membership_applications WHERE user_id = $1 AND status = 'PENDING'",  # noqa: E501
            user_id,
        )
        return bool(count > 0)

import uuid
from datetime import datetime, timezone

from loguru import logger

from app.core.database import get_pool


async def create_application(user_id: uuid.UUID, description: str) -> dict:
    pool = get_pool()
    app_id = uuid.uuid4()
    async with pool.acquire() as conn:
        # Check for existing pending application
        existing = await conn.fetchval(
            "SELECT COUNT(*) FROM membership_applications WHERE user_id = $1 AND status = 'PENDING'",
            user_id,
        )
        if existing > 0:
            raise ValueError("You already have a pending application.")

        row = await conn.fetchrow(
            """
            INSERT INTO membership_applications (id, user_id, description)
            VALUES ($1, $2, $3)
            RETURNING *
            """,
            app_id,
            user_id,
            description,
        )
        logger.info("Membership application created", extra={"user_id": str(user_id)})
        return dict(row)


async def list_applications(
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


async def review_application(
    app_id: uuid.UUID, reviewer_id: uuid.UUID, action: str
) -> dict | None:
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

            # If approved, upgrade user role to MEMBER
            if action == "APPROVED":
                await conn.execute(
                    "UPDATE users SET role = 'MEMBER', updated_at = NOW() WHERE id = $1",
                    row["user_id"],
                )
                logger.info(
                    "Membership approved, user promoted",
                    extra={"user_id": str(row["user_id"])},
                )

            return dict(row)

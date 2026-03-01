import uuid

from app.core.database import get_pool


async def insert(
    notif_id: uuid.UUID,
    user_id: uuid.UUID,
    trigger_user_id: uuid.UUID | None,
    action_type: str,
    entity_type: str | None,
    entity_id: uuid.UUID | None,
    message: str,
) -> dict:
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            WITH inserted AS (
                INSERT INTO notifications (id, user_id, trigger_user_id, action_type, entity_type, entity_id, message)  # noqa: E501
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                RETURNING *
            )
            SELECT n.*,
                   u.display_name AS trigger_display_name,
                   u.avatar_url AS trigger_avatar_url
            FROM inserted n
            LEFT JOIN users u ON n.trigger_user_id = u.id
            """,
            notif_id,
            user_id,
            trigger_user_id,
            action_type,
            entity_type,
            entity_id,
            message,
        )
        return dict(row)


async def find_many(
    user_id: uuid.UUID,
    unread_only: bool = False,
    page_size: int = 20,
    offset: int = 0,
) -> tuple[list[dict], int, int]:
    """Returns (rows, total, unread_count)."""
    pool = get_pool()
    async with pool.acquire() as conn:
        unread_count = await conn.fetchval(
            "SELECT COUNT(*) FROM notifications WHERE user_id = $1 AND is_read = false",
            user_id,
        )

        where = "WHERE n.user_id = $1"
        params: list = [user_id]
        idx = 2

        if unread_only:
            where += " AND n.is_read = false"

        total = await conn.fetchval(
            f"SELECT COUNT(*) FROM notifications n {where}",
            *params,
        )

        if page_size == 0:
            return [], total, unread_count

        params.extend([page_size, offset])
        rows = await conn.fetch(
            f"""
            SELECT n.*,
                   u.display_name AS trigger_display_name,
                   u.avatar_url AS trigger_avatar_url
            FROM notifications n
            LEFT JOIN users u ON n.trigger_user_id = u.id
            {where}
            ORDER BY n.created_at DESC
            LIMIT ${idx} OFFSET ${idx + 1}
            """,
            *params,
        )
        return [dict(r) for r in rows], total, unread_count


async def mark_read(notification_id: uuid.UUID, user_id: uuid.UUID) -> bool:
    pool = get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "UPDATE notifications SET is_read = true WHERE id = $1 AND user_id = $2 AND is_read = false",  # noqa: E501
            notification_id,
            user_id,
        )
        return bool(result == "UPDATE 1")


async def mark_all_read(user_id: uuid.UUID) -> int:
    pool = get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "UPDATE notifications SET is_read = true WHERE user_id = $1 AND is_read = false",
            user_id,
        )
        count = int(result.split(" ")[1]) if result else 0
        return count


async def delete(notification_id: uuid.UUID, user_id: uuid.UUID) -> bool:
    pool = get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM notifications WHERE id = $1 AND user_id = $2",
            notification_id,
            user_id,
        )
        return bool(result == "DELETE 1")


async def count_unread(user_id: uuid.UUID) -> int:
    pool = get_pool()
    async with pool.acquire() as conn:
        return int(
            await conn.fetchval(
                "SELECT COUNT(*) FROM notifications WHERE user_id = $1 AND is_read = false",
                user_id,
            )
        )

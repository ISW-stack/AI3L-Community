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
    exclude_user_ids: list[uuid.UUID] | None = None,
) -> tuple[list[dict], int, int]:
    """Returns (rows, total, unread_count)."""
    pool = get_pool()
    async with pool.acquire() as conn:
        where = "WHERE n.user_id = $1"
        params: list = [user_id]
        idx = 2

        if unread_only:
            where += " AND n.is_read = false"

        if exclude_user_ids:
            where += f" AND (n.trigger_user_id IS NULL OR n.trigger_user_id != ALL(${idx}::uuid[]))"
            params.append(exclude_user_ids)
            idx += 1

        # Save params before extending with LIMIT/OFFSET for potential fallback count query
        count_params = list(params)

        params.extend([page_size, offset])
        rows = await conn.fetch(
            f"""
            SELECT n.*,
                   u.display_name AS trigger_display_name,
                   u.avatar_url AS trigger_avatar_url,
                   COUNT(*) OVER() AS _total
            FROM notifications n
            LEFT JOIN users u ON n.trigger_user_id = u.id
            {where}
            ORDER BY n.created_at DESC
            LIMIT ${idx} OFFSET ${idx + 1}
            """,
            *params,
        )

        if rows:
            total = rows[0]["_total"]
            result = [{k: v for k, v in dict(r).items() if k != "_total"} for r in rows]
        else:
            # Page may be out of range — do a separate count to get real total
            total = await conn.fetchval(
                f"SELECT COUNT(*) FROM notifications n {where}",
                *count_params,
            )
            result = []

        # Get unread count in same connection (respecting blocked-user filter)
        unread_where = "WHERE n.user_id = $1 AND n.is_read = false"
        unread_params: list = [user_id]
        if exclude_user_ids:
            unread_where += " AND (n.trigger_user_id IS NULL OR n.trigger_user_id != ALL($2::uuid[]))"
            unread_params.append(exclude_user_ids)
        unread_count = await conn.fetchval(
            f"SELECT COUNT(*) FROM notifications n {unread_where}",
            *unread_params,
        )
        return result, total, unread_count


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
        count = int(result.split()[-1]) if result else 0
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


async def bulk_delete(user_id: uuid.UUID, notification_ids: list[uuid.UUID] | None = None) -> int:
    """Delete specific notifications or all notifications for a user.
    Returns the number of deleted rows."""
    pool = get_pool()
    async with pool.acquire() as conn:
        if notification_ids:
            result = await conn.execute(
                "DELETE FROM notifications WHERE user_id = $1 AND id = ANY($2::uuid[])",
                user_id,
                notification_ids,
            )
        else:
            result = await conn.execute(
                "DELETE FROM notifications WHERE user_id = $1",
                user_id,
            )
        return int(result.split()[-1]) if result else 0


async def count_unread(user_id: uuid.UUID) -> int:
    pool = get_pool()
    async with pool.acquire() as conn:
        return int(
            await conn.fetchval(
                "SELECT COUNT(*) FROM notifications WHERE user_id = $1 AND is_read = false",
                user_id,
            )
        )

import uuid

from loguru import logger

from app.core.database import get_pool


def _row_to_notification(row: dict) -> dict:
    result: dict = {
        "id": str(row["id"]),
        "action_type": row["action_type"],
        "entity_type": row.get("entity_type"),
        "entity_id": str(row["entity_id"]) if row.get("entity_id") else None,
        "message": row["message"],
        "is_read": row["is_read"],
        "created_at": row["created_at"].isoformat(),
    }
    if row.get("trigger_user_id") and row.get("trigger_display_name") is not None:
        result["trigger_user"] = {
            "id": str(row["trigger_user_id"]),
            "display_name": row["trigger_display_name"],
            "avatar_url": row.get("trigger_avatar_url"),
        }
    else:
        result["trigger_user"] = None
    return result


async def create_notification(
    user_id: str,
    trigger_user_id: str | None,
    action_type: str,
    entity_type: str | None,
    entity_id: str | None,
    message: str,
) -> dict:
    pool = get_pool()
    notif_id = uuid.uuid4()
    trigger_uuid = uuid.UUID(trigger_user_id) if trigger_user_id else None
    entity_uuid = uuid.UUID(entity_id) if entity_id else None

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            WITH inserted AS (
                INSERT INTO notifications (id, user_id, trigger_user_id, action_type, entity_type, entity_id, message)
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
            uuid.UUID(user_id),
            trigger_uuid,
            action_type,
            entity_type,
            entity_uuid,
            message,
        )

    notif = _row_to_notification(dict(row))
    logger.info(
        "Notification created",
        extra={"notification_id": str(notif_id), "user_id": user_id, "type": action_type},
    )

    # Push via WebSocket if user is online
    try:
        from app.api.v1.endpoints.ws import send_to_user

        await send_to_user(user_id, {
            "type": "NEW_NOTIFICATION",
            "notification": notif,
        })
    except Exception:
        pass  # WS push is best-effort

    return notif


async def list_notifications(
    user_id: str,
    unread_only: bool = False,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[dict], int, int]:
    """Returns (notifications, total, unread_count)."""
    pool = get_pool()
    user_uuid = uuid.UUID(user_id)
    offset = (page - 1) * page_size

    async with pool.acquire() as conn:
        unread_count = await conn.fetchval(
            "SELECT COUNT(*) FROM notifications WHERE user_id = $1 AND is_read = false",
            user_uuid,
        )

        where = "WHERE n.user_id = $1"
        params: list = [user_uuid]
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
        return [_row_to_notification(dict(r)) for r in rows], total, unread_count


async def mark_as_read(notification_id: uuid.UUID, user_id: str) -> bool:
    pool = get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "UPDATE notifications SET is_read = true WHERE id = $1 AND user_id = $2 AND is_read = false",
            notification_id,
            uuid.UUID(user_id),
        )
        return result == "UPDATE 1"


async def mark_all_as_read(user_id: str) -> int:
    pool = get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "UPDATE notifications SET is_read = true WHERE user_id = $1 AND is_read = false",
            uuid.UUID(user_id),
        )
        # result format: "UPDATE N"
        count = int(result.split(" ")[1]) if result else 0
        return count


async def get_unread_count(user_id: str) -> int:
    pool = get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchval(
            "SELECT COUNT(*) FROM notifications WHERE user_id = $1 AND is_read = false",
            uuid.UUID(user_id),
        )

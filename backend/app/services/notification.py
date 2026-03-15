import asyncio
import uuid

from loguru import logger

from app.converters.notification_converter import async_row_to_notification
from app.core.event_bus import emit
from app.repositories import notification_repo


async def create_notification(
    user_id: str,
    trigger_user_id: str | None,
    action_type: str,
    entity_type: str | None,
    entity_id: str | None,
    message: str,
) -> dict:
    notif_id = uuid.uuid4()
    trigger_uuid = uuid.UUID(trigger_user_id) if trigger_user_id else None
    entity_uuid = uuid.UUID(entity_id) if entity_id else None

    row = await notification_repo.insert(
        notif_id,
        uuid.UUID(user_id),
        trigger_uuid,
        action_type,
        entity_type,
        entity_uuid,
        message,
    )

    notif = await async_row_to_notification(row)
    logger.info(
        "Notification created",
        extra={"notification_id": str(notif_id), "user_id": user_id, "type": action_type},
    )

    # Push via WebSocket (best-effort, through event bus)
    await emit("notification.created", user_id=user_id, notification=notif)

    return notif


async def list_notifications(
    user_id: str,
    unread_only: bool = False,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[dict], int, int]:
    """Returns (notifications, total, unread_count)."""
    offset = (page - 1) * page_size
    rows, total, unread_count = await notification_repo.find_many(
        uuid.UUID(user_id), unread_only, page_size, offset
    )
    notifications = list(await asyncio.gather(*[async_row_to_notification(r) for r in rows]))
    return notifications, total, unread_count


async def mark_as_read(notification_id: uuid.UUID, user_id: str) -> bool:
    return await notification_repo.mark_read(notification_id, uuid.UUID(user_id))


async def mark_all_as_read(user_id: str) -> int:
    return await notification_repo.mark_all_read(uuid.UUID(user_id))


async def delete_notification(notification_id: uuid.UUID, user_id: str) -> bool:
    """Hard-delete a notification (owner only)."""
    deleted = await notification_repo.delete(notification_id, uuid.UUID(user_id))
    if deleted:
        logger.info("Notification deleted", extra={"notification_id": str(notification_id)})
    return deleted


async def get_unread_count(user_id: str) -> int:
    return await notification_repo.count_unread(uuid.UUID(user_id))

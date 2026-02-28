import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.deps import get_current_user
from app.schemas.auth import MessageResponse
from app.schemas.notification import NotificationListResponse, NotificationResponse
from app.services.notification import list_notifications, mark_all_as_read, mark_as_read

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=NotificationListResponse)
async def get_notifications(
    unread: bool = Query(False),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=0, le=100),
    current_user: dict = Depends(get_current_user),
) -> NotificationListResponse:
    notifications, total, unread_count = await list_notifications(
        user_id=current_user["sub"],
        unread_only=unread,
        page=page,
        page_size=page_size,
    )
    return NotificationListResponse(
        notifications=[NotificationResponse(**n) for n in notifications],
        total=total,
        unread_count=unread_count,
    )


@router.put("/{notification_id}/read", response_model=MessageResponse)
async def read_notification(
    notification_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
) -> MessageResponse:
    updated = await mark_as_read(notification_id, current_user["sub"])
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found or already read.",
        )
    return MessageResponse(message="Notification marked as read.")


@router.put("/read-all", response_model=MessageResponse)
async def read_all_notifications(
    current_user: dict = Depends(get_current_user),
) -> MessageResponse:
    count = await mark_all_as_read(current_user["sub"])
    return MessageResponse(message=f"{count} notifications marked as read.")

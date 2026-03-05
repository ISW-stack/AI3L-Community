import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status

from app.core.deps import get_current_user
from app.core.rate_limit import check_rate_limit
from app.repositories import notification_repo
from app.schemas.auth import MessageResponse
from app.schemas.notification import (
    BulkDeleteNotificationsRequest,
    NotificationListResponse,
    NotificationResponse,
)
from app.services.notification import (
    delete_notification,
    list_notifications,
    mark_all_as_read,
    mark_as_read,
)

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=NotificationListResponse)
async def get_notifications(
    request: Request,
    unread: bool = Query(False),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
) -> NotificationListResponse:
    if not await check_rate_limit(f"rl:notif:{current_user['sub']}", 60, 60):
        raise HTTPException(status_code=429, detail="Too many requests. Try again later.")
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


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def bulk_delete_notifications(
    request: Request,
    req: BulkDeleteNotificationsRequest | None = None,
    current_user: dict = Depends(get_current_user),
) -> Response:
    if not await check_rate_limit(f"rl:notif_del:{current_user['sub']}", 30, 60):
        raise HTTPException(status_code=429, detail="Too many requests. Try again later.")
    ids = None
    if req and req.notification_ids:
        ids = [uuid.UUID(nid) for nid in req.notification_ids]
    await notification_repo.bulk_delete(uuid.UUID(current_user["sub"]), ids)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/{notification_id}", response_model=MessageResponse)
async def delete_notification_endpoint(
    notification_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
) -> MessageResponse:
    deleted = await delete_notification(notification_id, current_user["sub"])
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found.",
        )
    return MessageResponse(message="Notification deleted.")


@router.put("/read-all", response_model=MessageResponse)
async def read_all_notifications(
    current_user: dict = Depends(get_current_user),
) -> MessageResponse:
    count = await mark_all_as_read(current_user["sub"])
    return MessageResponse(message=f"{count} notifications marked as read.")

from pydantic import BaseModel


class TriggerUserResponse(BaseModel):
    id: str
    display_name: str
    avatar_url: str | None = None


class NotificationResponse(BaseModel):
    id: str
    action_type: str
    entity_type: str | None = None
    entity_id: str | None = None
    message: str
    is_read: bool
    created_at: str
    trigger_user: TriggerUserResponse | None = None


class NotificationListResponse(BaseModel):
    notifications: list[NotificationResponse]
    total: int
    unread_count: int


class BulkDeleteNotificationsRequest(BaseModel):
    notification_ids: list[str] | None = None

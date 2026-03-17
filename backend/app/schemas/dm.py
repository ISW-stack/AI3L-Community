"""Schemas for the Direct Messages feature."""

from pydantic import BaseModel, Field


class DMSenderResponse(BaseModel):
    id: str
    display_name: str
    avatar_url: str | None = None


class DMMessageResponse(BaseModel):
    id: str
    conversation_id: str
    sender: DMSenderResponse
    content: str | None = None
    attachment_url: str | None = None
    attachment_name: str | None = None
    attachment_size: int | None = None
    attachment_expires_at: str | None = None
    is_recalled: bool
    is_edited: bool
    read_at: str | None = None
    created_at: str
    updated_at: str


class ConversationResponse(BaseModel):
    id: str
    other_user: DMSenderResponse
    last_message: DMMessageResponse | None = None
    unread_count: int = 0
    updated_at: str


class ConversationListResponse(BaseModel):
    conversations: list[ConversationResponse]
    total: int


class MessageListResponse(BaseModel):
    messages: list[DMMessageResponse]
    total: int


class EditMessageRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=5000)


class DMUnreadCountResponse(BaseModel):
    unread_count: int

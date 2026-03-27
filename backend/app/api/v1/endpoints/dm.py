"""Direct messaging endpoints."""

import os
import re
import uuid

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile

from app.core.constants import (
    DEFAULT_PAGE_SIZE_DM,
    DM_MAX_ATTACHMENT_SIZE,
    DM_MAX_MESSAGE_LENGTH,
    MAX_PAGE_NUMBER,
    MAX_PAGE_SIZE,
    PRESIGNED_URL_FILE_SECONDS,
    RATE_LIMIT_DM_ADMIN,
    RATE_LIMIT_DM_EDIT,
    RATE_LIMIT_DM_CONV_LIST,
    RATE_LIMIT_DM_MSG_LIST,
    RATE_LIMIT_DM_MARK_READ,
    RATE_LIMIT_DM_RECALL,
    RATE_LIMIT_DM_SEND,
    RATE_LIMIT_DM_UNREAD,
)
from app.core.deps import require_role
from app.core.errors import AppError, ErrorCode
from app.core.rate_limit import check_rate_limit
from app.schemas.auth import MessageResponse
from app.schemas.dm import (
    ConversationListResponse,
    ConversationResponse,
    DMMessageResponse,
    DMUnreadCountResponse,
    EditMessageRequest,
    MessageListResponse,
)
from app.services import dm as dm_service

# Defense-in-depth: blocked extensions are checked first at the endpoint level.
# The service layer has an independent ALLOWED list (_DM_ALLOWED_EXTENSIONS in services/dm.py).
# Both must pass for a file to be accepted.
_DM_BLOCKED_EXTENSIONS: set[str] = {
    ".exe",
    ".bat",
    ".ps1",
    ".sh",
    ".cmd",
    ".vbs",
    ".js",
    ".html",
    ".htm",
    ".svg",
    ".msi",
    ".dll",
    ".scr",
    ".com",
}

router = APIRouter(prefix="/dm", tags=["dm"])


# ── Literal paths first ───────────────────────────────────────────────


@router.get("/unread-count", response_model=DMUnreadCountResponse)
async def get_unread_count(
    current_user: dict = Depends(require_role("MEMBER", "ADMIN", "SUPER_ADMIN")),
) -> DMUnreadCountResponse:
    """Get total unread DM count for the current user."""
    if not await check_rate_limit(f"rl:dm:unread:{current_user['sub']}", *RATE_LIMIT_DM_UNREAD):
        raise AppError(ErrorCode.SYS_429, 429, "Too many requests.")
    count = await dm_service.get_unread_count(current_user["sub"])
    return DMUnreadCountResponse(unread_count=count)


@router.get("/admin/conversations/{conversation_id}/messages", response_model=MessageListResponse)
async def admin_list_messages(
    conversation_id: uuid.UUID,
    page: int = Query(1, ge=1, le=MAX_PAGE_NUMBER),
    page_size: int = Query(DEFAULT_PAGE_SIZE_DM, ge=1, le=MAX_PAGE_SIZE),
    current_user: dict = Depends(require_role("SUPER_ADMIN")),
) -> MessageListResponse:
    """Admin: view messages in any conversation for moderation."""
    if not await check_rate_limit(f"rl:dm:admin:{current_user['sub']}", *RATE_LIMIT_DM_ADMIN):
        raise AppError(ErrorCode.SYS_429, 429, "Too many requests.")

    # P2: Audit log for admin DM access
    try:
        from app.core.event_bus import emit

        await emit(
            "audit.action",
            user_id=current_user["sub"],
            action="DM_ADMIN_VIEW",
            target_type="conversation",
            target_id=str(conversation_id),
        )
    except Exception:
        pass  # best-effort audit

    from app.converters.dm_converter import async_row_to_message
    from app.core.storage import generate_presigned_url
    from app.repositories import dm_repo

    # F-65: Check conversation exists before querying messages
    if not await dm_repo.conversation_exists(conversation_id):
        raise AppError(ErrorCode.SYS_404, 404, "Conversation not found.")

    offset = (page - 1) * page_size
    rows, total = await dm_repo.find_messages(conversation_id, page_size, offset)

    messages = []
    for row in rows:
        msg = await async_row_to_message(row)
        if row.get("attachment_key") and not row.get("is_recalled"):
            msg["attachment_url"] = generate_presigned_url(
                row["attachment_key"],
                expires_in=PRESIGNED_URL_FILE_SECONDS,
                filename=row.get("attachment_name"),
            )
        messages.append(msg)

    return MessageListResponse(messages=[DMMessageResponse(**m) for m in messages], total=total)


@router.get("/conversations", response_model=ConversationListResponse)
async def list_conversations(
    page: int = Query(1, ge=1, le=MAX_PAGE_NUMBER),
    page_size: int = Query(DEFAULT_PAGE_SIZE_DM, ge=1, le=MAX_PAGE_SIZE),
    current_user: dict = Depends(require_role("MEMBER", "ADMIN", "SUPER_ADMIN")),
) -> ConversationListResponse:
    """List the current user's DM conversations (paginated)."""
    if not await check_rate_limit(f"rl:dm:convlist:{current_user['sub']}", *RATE_LIMIT_DM_CONV_LIST):
        raise AppError(ErrorCode.SYS_429, 429, "Too many requests.")

    convos, total = await dm_service.list_conversations(current_user["sub"], page, page_size)
    return ConversationListResponse(
        conversations=[ConversationResponse(**c) for c in convos], total=total
    )


# ── Parameterized paths ───────────────────────────────────────────────


@router.get("/conversations/{conversation_id}/messages", response_model=MessageListResponse)
async def list_messages(
    conversation_id: uuid.UUID,
    page: int = Query(1, ge=1, le=MAX_PAGE_NUMBER),
    page_size: int = Query(DEFAULT_PAGE_SIZE_DM, ge=1, le=MAX_PAGE_SIZE),
    current_user: dict = Depends(require_role("MEMBER", "ADMIN", "SUPER_ADMIN")),
) -> MessageListResponse:
    """List messages in a conversation (paginated)."""
    if not await check_rate_limit(f"rl:dm:msglist:{current_user['sub']}", *RATE_LIMIT_DM_MSG_LIST):
        raise AppError(ErrorCode.SYS_429, 429, "Too many requests.")

    msgs, total = await dm_service.list_messages(
        current_user["sub"], str(conversation_id), page, page_size
    )
    return MessageListResponse(messages=[DMMessageResponse(**m) for m in msgs], total=total)


@router.post(
    "/conversations/{user_id}/messages",
    response_model=DMMessageResponse,
    status_code=201,
)
async def send_message(
    user_id: uuid.UUID,
    content: str | None = Form(None),
    file: UploadFile | None = File(None),
    current_user: dict = Depends(require_role("MEMBER", "ADMIN", "SUPER_ADMIN")),
) -> DMMessageResponse:
    """Send a message to a user. Lazy-creates conversation if needed.

    Send as multipart/form-data. ``content`` and/or ``file`` must be provided.
    """
    sender_id = current_user["sub"]
    if not await check_rate_limit(f"rl:dm:send:{sender_id}", *RATE_LIMIT_DM_SEND):
        raise AppError(ErrorCode.SYS_429, 429, "Too many requests.")

    # Strip whitespace from content
    if content:
        content = content.strip()

    # Validate: must have content or file
    if not content and not file:
        raise AppError(ErrorCode.SYS_422, 422, "Message must have content or an attachment.")

    # Validate content length
    if content and len(content) > DM_MAX_MESSAGE_LENGTH:
        raise AppError(
            ErrorCode.SYS_422,
            422,
            f"Message too long (max {DM_MAX_MESSAGE_LENGTH} chars).",
        )

    # Read file if present
    file_data: bytes | None = None
    file_name: str | None = None
    file_size: int | None = None
    file_content_type: str | None = None
    if file:
        # Block dangerous file extensions early (defense-in-depth)
        fname = file.filename or ""
        ext = os.path.splitext(fname)[1].lower()
        if ext in _DM_BLOCKED_EXTENSIONS:
            raise AppError(ErrorCode.SYS_422, 422, f"File type '{ext}' is not allowed.")

        # L-15: Read with size limit to avoid unbounded memory usage
        file_data = await file.read(DM_MAX_ATTACHMENT_SIZE + 1)
        file_size = len(file_data)
        if file_size > DM_MAX_ATTACHMENT_SIZE:
            raise AppError(ErrorCode.DM_005, 413, "File too large (max 10 MB).")
        if file_size == 0:
            raise AppError(ErrorCode.SYS_422, 422, "Empty file.")
        # L-16: Sanitize filename — strip path components, control chars, limit length
        raw_name = file.filename or "attachment"
        raw_name = os.path.basename(raw_name).replace("..", "")
        # Remove control characters and null bytes
        raw_name = re.sub(r"[\x00-\x1f\x7f]", "", raw_name)
        # Limit to 255 characters
        if len(raw_name) > 255:
            base, ext = os.path.splitext(raw_name)
            raw_name = base[: 255 - len(ext)] + ext
        file_name = raw_name or "attachment"
        file_content_type = file.content_type

    msg = await dm_service.send_message(
        sender_id=sender_id,
        recipient_id=str(user_id),
        content=content,
        file_data=file_data,
        file_name=file_name,
        file_size=file_size,
        file_content_type=file_content_type,
    )

    return DMMessageResponse(**msg)


@router.put("/messages/{message_id}", response_model=DMMessageResponse)
async def edit_message(
    message_id: uuid.UUID,
    req: EditMessageRequest,
    current_user: dict = Depends(require_role("MEMBER", "ADMIN", "SUPER_ADMIN")),
) -> DMMessageResponse:
    """Edit a previously sent message (within the edit window)."""
    if not await check_rate_limit(f"rl:dm:edit:{current_user['sub']}", *RATE_LIMIT_DM_EDIT):
        raise AppError(ErrorCode.SYS_429, 429, "Too many requests.")

    msg = await dm_service.edit_message(str(message_id), current_user["sub"], req.content)
    return DMMessageResponse(**msg)


@router.delete("/messages/{message_id}", response_model=DMMessageResponse)
async def recall_message(
    message_id: uuid.UUID,
    current_user: dict = Depends(require_role("MEMBER", "ADMIN", "SUPER_ADMIN")),
) -> DMMessageResponse:
    """Recall (unsend) a message (within the recall window)."""
    if not await check_rate_limit(f"rl:dm:recall:{current_user['sub']}", *RATE_LIMIT_DM_RECALL):
        raise AppError(ErrorCode.SYS_429, 429, "Too many requests.")

    msg = await dm_service.recall_message(str(message_id), current_user["sub"])
    return DMMessageResponse(**msg)


@router.put("/conversations/{conversation_id}/read", response_model=MessageResponse)
async def mark_read(
    conversation_id: uuid.UUID,
    current_user: dict = Depends(require_role("MEMBER", "ADMIN", "SUPER_ADMIN")),
) -> MessageResponse:
    """Mark all unread messages in a conversation as read."""
    if not await check_rate_limit(
        f"rl:dm:markread:{current_user['sub']}", *RATE_LIMIT_DM_MARK_READ
    ):
        raise AppError(ErrorCode.SYS_429, 429, "Too many requests.")

    await dm_service.mark_read(current_user["sub"], str(conversation_id))
    return MessageResponse(message="Marked as read.")

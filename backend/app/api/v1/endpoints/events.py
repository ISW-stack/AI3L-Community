import math
import uuid

from fastapi import APIRouter, Depends, Query, Request, status

from app.core.constants import (
    DEFAULT_PAGE_SIZE_EVENTS,
    RATE_LIMIT_COMMENT,
    RATE_LIMIT_EVENT_REACTION,
)
from app.core.deps import require_role
from app.core.errors import AppError, ErrorCode, RateLimitError
from app.core.file_validation import sanitize_html
from app.core.logging_utils import safe_error_detail
from app.core.rate_limit import check_rate_limit, get_client_ip
from app.core.event_bus import emit
from app.schemas.auth import MessageResponse
from app.schemas.comment import (
    CommentCreateRequest,
    CommentListResponse,
    CommentResponse,
    ReactionRequest,
)
from app.schemas.event import (
    EventCreateRequest,
    EventListResponse,
    EventResponse,
    EventUpdateRequest,
)
from app.services.comment import (
    create_comment,
    list_comments,
    soft_delete_comment,
)
from app.services.event import (
    create_event,
    delete_event,
    get_event,
    list_events,
    toggle_event_reaction,
    update_event,
)

router = APIRouter(prefix="/events", tags=["events"])


# ── Event CRUD ──


@router.post("", response_model=EventResponse, status_code=status.HTTP_201_CREATED)
async def create_new_event(
    req: EventCreateRequest,
    request: Request,
    current_user: dict = Depends(require_role("SUPER_ADMIN", "ADMIN")),
) -> EventResponse:
    content = sanitize_html(req.content)
    if not content or not content.strip():
        raise AppError(ErrorCode.SYS_422, 422, "Content cannot be empty after sanitization.")
    try:
        event = await create_event(
            user_id=current_user["sub"],
            title=req.title,
            content=content,
            sig_id=req.sig_id,
            visibility=req.visibility,
            allow_comments=req.allow_comments,
        )
    except RateLimitError as e:
        raise AppError(ErrorCode.SYS_429, 429, safe_error_detail(e, "Too many requests."))
    except ValueError as e:
        raise AppError(ErrorCode.SYS_422, 422, safe_error_detail(e, "Invalid event data."))

    return EventResponse(**event)


@router.get("", response_model=EventListResponse)
async def get_events_list(
    page: int = Query(1, ge=1, le=1000),
    page_size: int = Query(DEFAULT_PAGE_SIZE_EVENTS, ge=1, le=100),
    sig_id: str | None = None,
    current_user: dict = Depends(
        require_role("SUPER_ADMIN", "ADMIN", "MEMBER", "GUEST")
    ),
) -> EventListResponse:
    data = await list_events(
        page=page,
        page_size=page_size,
        sig_id=sig_id,
        user_role=current_user["role"],
        viewer_id=current_user["sub"],
    )
    total = data["total"]
    total_pages = max(1, math.ceil(total / page_size))
    return EventListResponse(
        events=[EventResponse(**e) for e in data["events"]],
        total=total,
        page=page,
        total_pages=total_pages,
    )


@router.get("/{event_id}", response_model=EventResponse)
async def get_event_detail(
    event_id: uuid.UUID,
    current_user: dict = Depends(
        require_role("SUPER_ADMIN", "ADMIN", "MEMBER", "GUEST")
    ),
) -> EventResponse:
    event = await get_event(
        event_id,
        viewer_id=current_user["sub"],
        user_role=current_user["role"],
    )
    if event is None:
        raise AppError(ErrorCode.SYS_404, 404, "Event not found.")
    return EventResponse(**event)


@router.put("/{event_id}", response_model=EventResponse)
async def update_existing_event(
    event_id: uuid.UUID,
    req: EventUpdateRequest,
    request: Request,
    current_user: dict = Depends(require_role("SUPER_ADMIN", "ADMIN")),
) -> EventResponse:
    content = req.content
    if content is not None:
        content = sanitize_html(content)
        if not content or not content.strip():
            raise AppError(
                ErrorCode.SYS_422, 422, "Content cannot be empty after sanitization."
            )
    # Distinguish "sig_id not sent" from "sig_id explicitly set to null"
    from app.services.event import _UNSET

    sig_id_value = req.sig_id if "sig_id" in req.model_fields_set else _UNSET

    try:
        event = await update_event(
            event_id=event_id,
            user_id=current_user["sub"],
            caller_role=current_user["role"],
            title=req.title,
            content=content,
            sig_id=sig_id_value,
            visibility=req.visibility,
            allow_comments=req.allow_comments,
            expected_version=req.version,
        )
    except PermissionError as e:
        raise AppError(ErrorCode.SYS_403, 403, safe_error_detail(e, "Permission denied."))
    except ValueError as e:
        detail = safe_error_detail(e, "Invalid event data.")
        if "conflict" in str(e).lower():
            raise AppError(ErrorCode.SYS_409, 409, detail)
        raise AppError(ErrorCode.SYS_422, 422, detail)

    return EventResponse(**event)


@router.delete("/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_existing_event(
    event_id: uuid.UUID,
    request: Request,
    current_user: dict = Depends(require_role("SUPER_ADMIN", "ADMIN")),
) -> None:
    try:
        result = await delete_event(
            event_id=event_id,
            user_id=current_user["sub"],
            caller_role=current_user["role"],
        )
    except PermissionError as e:
        raise AppError(ErrorCode.SYS_403, 403, safe_error_detail(e, "Permission denied."))
    except ValueError as e:
        raise AppError(ErrorCode.SYS_404, 404, safe_error_detail(e, "Event not found."))
    if not result:
        raise AppError(ErrorCode.SYS_404, 404, "Event not found.")

    ip = get_client_ip(request)
    try:
        await emit(
            "audit.action",
            user_id=current_user["sub"],
            action="USER_DELETE_EVENT",
            target_type="event",
            target_id=str(event_id),
            ip_address=ip,
        )
    except Exception:
        pass


# ── Event Reactions ──


@router.post("/{event_id}/reactions", response_model=EventResponse)
async def toggle_reaction(
    event_id: uuid.UUID,
    req: ReactionRequest,
    current_user: dict = Depends(require_role("SUPER_ADMIN", "ADMIN", "MEMBER")),
) -> EventResponse:
    if not await check_rate_limit(
        f"rl:event_reaction:{current_user['sub']}", *RATE_LIMIT_EVENT_REACTION
    ):
        raise AppError(ErrorCode.SYS_429, 429, "Too many requests. Try again later.")

    event = await toggle_event_reaction(event_id, current_user["sub"], req.reaction)
    if event is None:
        raise AppError(ErrorCode.SYS_404, 404, "Event not found.")
    return EventResponse(**event)


# ── Event Comments ──


@router.get("/{event_id}/comments", response_model=CommentListResponse)
async def get_event_comments(
    event_id: uuid.UUID,
    page: int = Query(1, ge=1, le=1000),
    page_size: int = Query(50, ge=1, le=100),
    root_only: bool = Query(False),
    sort: str = Query("asc", pattern="^(asc|desc)$"),
    current_user: dict = Depends(
        require_role("SUPER_ADMIN", "ADMIN", "MEMBER", "GUEST")
    ),
) -> CommentListResponse:
    # Verify event exists and user can see it
    event = await get_event(
        event_id, user_role=current_user["role"]
    )
    if event is None:
        raise AppError(ErrorCode.SYS_404, 404, "Event not found.")

    comments, total = await list_comments(
        event_id=event_id,
        page=page,
        page_size=page_size,
        viewer_id=current_user["sub"],
        root_only=root_only,
        sort=sort,
    )
    total_pages = max(1, math.ceil(total / page_size))
    return CommentListResponse(
        comments=[CommentResponse(**c) for c in comments],
        total=total,
        page=page,
        total_pages=total_pages,
    )


@router.post(
    "/{event_id}/comments",
    response_model=CommentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_event_comment(
    event_id: uuid.UUID,
    req: CommentCreateRequest,
    current_user: dict = Depends(require_role("SUPER_ADMIN", "ADMIN", "MEMBER")),
) -> CommentResponse:
    if not await check_rate_limit(
        f"rl:comment:{current_user['sub']}", *RATE_LIMIT_COMMENT
    ):
        raise AppError(ErrorCode.SYS_429, 429, "Too many requests. Try again later.")

    sanitized_content = sanitize_html(req.content)
    if not sanitized_content or not sanitized_content.strip():
        raise AppError(ErrorCode.SYS_422, 422, "Comment content cannot be empty.")

    try:
        comment = await create_comment(
            post_id=None,
            user_id=current_user["sub"],
            content=sanitized_content,
            parent_id=str(req.parent_id) if req.parent_id else None,
            mentions=req.mentions,
            event_id=event_id,
        )
    except ValueError as e:
        raise AppError(ErrorCode.SYS_422, 422, safe_error_detail(e, "Invalid comment data."))

    return CommentResponse(**comment)


@router.delete(
    "/{event_id}/comments/{comment_id}",
    response_model=MessageResponse,
)
async def delete_event_comment(
    event_id: uuid.UUID,
    comment_id: uuid.UUID,
    current_user: dict = Depends(require_role("SUPER_ADMIN", "ADMIN", "MEMBER")),
) -> MessageResponse:
    is_admin = current_user["role"] in ("SUPER_ADMIN", "ADMIN")
    deleted = await soft_delete_comment(
        comment_id,
        event_id=event_id,
        user_id=current_user["sub"],
        is_admin=is_admin,
    )
    if not deleted:
        raise AppError(ErrorCode.SYS_404, 404, "Comment not found or you are not the owner.")
    return MessageResponse(message="Comment deleted.")

import math
import uuid

from fastapi import APIRouter, Depends, Query, status

from app.core.constants import RATE_LIMIT_COMMENT, RATE_LIMIT_REACTION
from app.core.deps import get_current_user, require_role
from app.core.errors import AppError, ErrorCode
from app.core.file_validation import sanitize_html
from app.core.rate_limit import check_rate_limit
from app.schemas.auth import MessageResponse
from app.schemas.comment import (
    CommentCreateRequest,
    CommentListResponse,
    CommentResponse,
    CommentUpdateRequest,
    ReactionRequest,
)
from app.services.comment import (
    add_reaction,
    create_comment,
    list_comments,
    soft_delete_comment,
    update_comment,
)
from app.services.post import get_post_by_id

router = APIRouter(prefix="/posts/{post_id}/comments", tags=["comments"])


@router.get("", response_model=CommentListResponse)
async def get_comments(
    post_id: uuid.UUID,
    page: int = Query(1, ge=1, le=10000),
    page_size: int = Query(50, ge=1, le=200),
    current_user: dict = Depends(get_current_user),
) -> CommentListResponse:
    # Verify post exists
    post = await get_post_by_id(post_id)
    if post is None:
        raise AppError(ErrorCode.SYS_404, 404, "Post not found.")

    comments, total = await list_comments(post_id, page=page, page_size=page_size)
    total_pages = max(1, math.ceil(total / page_size))
    return CommentListResponse(
        comments=[CommentResponse(**c) for c in comments],
        total=total,
        current_page=page,
        total_pages=total_pages,
    )


@router.post("", response_model=CommentResponse, status_code=status.HTTP_201_CREATED)
async def create_new_comment(
    post_id: uuid.UUID,
    req: CommentCreateRequest,
    current_user: dict = Depends(require_role("SUPER_ADMIN", "ADMIN", "MEMBER")),
) -> CommentResponse:
    # Rate limit: 30 comments/minute per user
    if not await check_rate_limit(f"rl:comment:{current_user['sub']}", *RATE_LIMIT_COMMENT):
        raise AppError(ErrorCode.SYS_429, 429, "Too many requests. Try again later.")

    sanitized_content = sanitize_html(req.content)
    if not sanitized_content or not sanitized_content.strip():
        raise AppError(ErrorCode.SYS_422, 400, "Comment content cannot be empty.")

    try:
        comment = await create_comment(
            post_id=post_id,
            user_id=current_user["sub"],
            content=sanitized_content,
            parent_id=req.parent_id,
            mentions=req.mentions,
        )
    except ValueError as e:
        raise AppError(ErrorCode.SYS_422, 400, str(e))

    return CommentResponse(**comment)


@router.put("/{comment_id}", response_model=CommentResponse)
async def edit_comment(
    post_id: uuid.UUID,
    comment_id: uuid.UUID,
    req: CommentUpdateRequest,
    current_user: dict = Depends(require_role("SUPER_ADMIN", "ADMIN", "MEMBER")),
) -> CommentResponse:
    sanitized_content = sanitize_html(req.content)
    if not sanitized_content or not sanitized_content.strip():
        raise AppError(ErrorCode.SYS_422, 400, "Comment content cannot be empty.")
    comment = await update_comment(
        comment_id=comment_id,
        user_id=current_user["sub"],
        content=sanitized_content,
        post_id=post_id,
    )
    if comment is None:
        raise AppError(ErrorCode.SYS_404, 404, "Comment not found or you are not the owner.")
    return CommentResponse(**comment)


@router.delete("/{comment_id}", response_model=MessageResponse)
async def delete_comment(
    post_id: uuid.UUID,
    comment_id: uuid.UUID,
    current_user: dict = Depends(require_role("SUPER_ADMIN", "ADMIN", "MEMBER")),
) -> MessageResponse:
    is_admin = current_user["role"] in ("SUPER_ADMIN", "ADMIN")
    deleted = await soft_delete_comment(comment_id, post_id, current_user["sub"], is_admin)
    if not deleted:
        raise AppError(ErrorCode.SYS_404, 404, "Comment not found or you are not the owner.")
    return MessageResponse(message="Comment deleted.")


@router.post(
    "/{comment_id}/reactions",
    response_model=CommentResponse,
)
async def toggle_reaction(
    post_id: uuid.UUID,
    comment_id: uuid.UUID,
    req: ReactionRequest,
    current_user: dict = Depends(require_role("SUPER_ADMIN", "ADMIN", "MEMBER")),
) -> CommentResponse:
    if not await check_rate_limit(
        f"rl:comment_reaction:{current_user['sub']}", *RATE_LIMIT_REACTION
    ):
        raise AppError(ErrorCode.SYS_429, 429, "Too many requests. Try again later.")
    comment = await add_reaction(comment_id, current_user["sub"], req.reaction)
    if comment is None:
        raise AppError(ErrorCode.SYS_404, 404, "Comment not found.")
    return CommentResponse(**comment)

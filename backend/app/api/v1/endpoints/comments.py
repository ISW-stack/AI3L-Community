import math
import uuid

from fastapi import APIRouter, Depends, Query, status

from app.core.constants import RATE_LIMIT_COMMENT, RATE_LIMIT_REACTION
from app.core.deps import require_role
from app.core.errors import AppError, ErrorCode
from app.core.file_validation import sanitize_html
from app.core.logging_utils import safe_error_detail
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
    page_size: int = Query(50, ge=1, le=100),
    root_only: bool = Query(False),
    current_user: dict = Depends(require_role("MEMBER", "ADMIN", "SUPER_ADMIN", "GUEST")),
) -> CommentListResponse:
    # Verify post exists
    post = await get_post_by_id(post_id)
    if post is None:
        raise AppError(ErrorCode.SYS_404, 404, "Post not found.")

    comments, total = await list_comments(
        post_id, page=page, page_size=page_size, viewer_id=current_user["sub"],
        root_only=root_only,
    )
    total_pages = max(1, math.ceil(total / page_size))
    return CommentListResponse(
        comments=[CommentResponse(**c) for c in comments],
        total=total,
        page=page,
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
        raise AppError(ErrorCode.SYS_422, 422, "Comment content cannot be empty.")

    try:
        comment = await create_comment(
            post_id=post_id,
            user_id=current_user["sub"],
            content=sanitized_content,
            parent_id=str(req.parent_id) if req.parent_id else None,
            mentions=req.mentions,
        )
    except ValueError as e:
        raise AppError(ErrorCode.SYS_422, 422, safe_error_detail(e, "Invalid comment data."))

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
        raise AppError(ErrorCode.SYS_422, 422, "Comment content cannot be empty.")

    # F-23: Check existence and ownership BEFORE rate limit so that editing
    # a non-existent comment does not consume rate limit quota.
    from app.core.database import get_pool

    pool = get_pool()
    async with pool.acquire() as conn:
        comment_row = await conn.fetchrow(
            "SELECT user_id FROM comments WHERE id = $1 AND post_id = $2 AND is_deleted = false",
            comment_id,
            post_id,
        )
    if comment_row is None:
        raise AppError(ErrorCode.SYS_404, 404, "Comment not found or you are not the owner.")
    if str(comment_row["user_id"]) != current_user["sub"]:
        raise AppError(ErrorCode.SYS_404, 404, "Comment not found or you are not the owner.")

    # P3: Rate limit comment edits (only after confirming comment exists and user owns it)
    if not await check_rate_limit(f"rl:comment_edit:{current_user['sub']}", 30, 60):
        raise AppError(ErrorCode.SYS_429, 429, "Too many edit requests. Try again later.")

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

    # M-09: Validate that the comment belongs to the specified post_id
    from app.core.blacklist import get_blocked_user_ids
    from app.core.database import get_pool
    from app.core.redis import get_redis
    from app.repositories import comment_repo

    pool = get_pool()
    async with pool.acquire() as conn:
        comment_row = await conn.fetchrow(
            "SELECT user_id, post_id FROM comments WHERE id = $1 AND is_deleted = false",
            comment_id,
        )
    if comment_row is None:
        raise AppError(ErrorCode.SYS_404, 404, "Comment not found.")
    if comment_row["post_id"] != post_id:
        raise AppError(ErrorCode.SYS_404, 404, "Comment not found on this post.")

    comment_owner_id = str(comment_row["user_id"])
    if comment_owner_id and comment_owner_id != current_user["sub"]:
        redis = get_redis()
        blocked_ids = await get_blocked_user_ids(redis, current_user["sub"])
        if comment_owner_id in blocked_ids:
            raise AppError(ErrorCode.SYS_403, 403, "Cannot react to this comment.")
        owner_blocked = await get_blocked_user_ids(redis, comment_owner_id)
        if current_user["sub"] in owner_blocked:
            raise AppError(ErrorCode.SYS_403, 403, "Cannot react to this comment.")

    comment = await add_reaction(comment_id, current_user["sub"], req.reaction)
    if comment is None:
        raise AppError(ErrorCode.SYS_404, 404, "Comment not found.")
    return CommentResponse(**comment)

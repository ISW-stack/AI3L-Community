import uuid

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.deps import get_current_user, require_role
from app.core.file_validation import sanitize_html
from app.schemas.comment import (
    CommentCreateRequest,
    CommentListResponse,
    CommentResponse,
    ReactionRequest,
)
from app.schemas.auth import MessageResponse
from app.services.comment import add_reaction, create_comment, list_comments, soft_delete_comment
from app.services.post import get_post_by_id

router = APIRouter(prefix="/posts/{post_id}/comments", tags=["comments"])


@router.get("", response_model=CommentListResponse)
async def get_comments(
    post_id: uuid.UUID,
    offset: int = 0,
    limit: int = 50,
    current_user: dict = Depends(get_current_user),
) -> CommentListResponse:
    # Verify post exists
    post = await get_post_by_id(post_id)
    if post is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found.")

    comments, total = await list_comments(post_id, offset=offset, limit=limit)
    return CommentListResponse(
        comments=[CommentResponse(**c) for c in comments],
        total=total,
    )


@router.post("", response_model=CommentResponse, status_code=status.HTTP_201_CREATED)
async def create_new_comment(
    post_id: uuid.UUID,
    req: CommentCreateRequest,
    current_user: dict = Depends(require_role("SUPER_ADMIN", "ADMIN", "MEMBER")),
) -> CommentResponse:
    try:
        comment = await create_comment(
            post_id=post_id,
            user_id=current_user["sub"],
            content=sanitize_html(req.content),
            parent_id=req.parent_id,
            mentions=req.mentions,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    return CommentResponse(**comment)


@router.delete("/{comment_id}", response_model=MessageResponse)
async def delete_comment(
    post_id: uuid.UUID,
    comment_id: uuid.UUID,
    current_user: dict = Depends(require_role("SUPER_ADMIN", "ADMIN", "MEMBER")),
) -> MessageResponse:
    is_admin = current_user["role"] in ("SUPER_ADMIN", "ADMIN")
    deleted = await soft_delete_comment(comment_id, current_user["sub"], is_admin)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found.")
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
    comment = await add_reaction(comment_id, current_user["sub"], req.reaction)
    if comment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found.")
    return CommentResponse(**comment)

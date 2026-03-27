import uuid

from fastapi import APIRouter, Depends, status

from app.core.deps import require_role
from app.core.errors import AppError, ErrorCode
from app.core.rate_limit import check_rate_limit
from app.schemas.qa import MarkBestAnswerRequest, VoteRequest
from app.services.qa import get_user_votes, mark_best_answer, unmark_best_answer, vote_on_answer

router = APIRouter(prefix="/qa", tags=["qa"])


@router.post("/{post_id}/best-answer", status_code=status.HTTP_200_OK)
async def mark_best_answer_endpoint(
    post_id: uuid.UUID,
    req: MarkBestAnswerRequest,
    current_user: dict = Depends(require_role("SUPER_ADMIN", "ADMIN", "MEMBER")),
) -> dict:
    """Mark a comment as the best answer for a question."""
    if not await check_rate_limit(f"rl:qa_action:{current_user['sub']}", 30, 60):
        raise AppError(ErrorCode.SYS_429, 429, "Too many requests. Try again later.")
    return await mark_best_answer(
        post_id=post_id,
        comment_id=req.comment_id,
        user_id=current_user["sub"],
    )


@router.delete("/{post_id}/best-answer", status_code=status.HTTP_200_OK)
async def unmark_best_answer_endpoint(
    post_id: uuid.UUID,
    current_user: dict = Depends(require_role("SUPER_ADMIN", "ADMIN", "MEMBER")),
) -> dict:
    """Remove the best answer mark from a question."""
    await unmark_best_answer(
        post_id=post_id,
        user_id=current_user["sub"],
    )
    return {"message": "Best answer unmarked."}


@router.post("/comments/{comment_id}/vote", status_code=status.HTTP_200_OK)
async def vote_on_answer_endpoint(
    comment_id: uuid.UUID,
    req: VoteRequest,
    current_user: dict = Depends(require_role("SUPER_ADMIN", "ADMIN", "MEMBER")),
) -> dict:
    """Vote on an answer (upvote, downvote, or remove vote)."""
    if not await check_rate_limit(f"rl:qa_action:{current_user['sub']}", 30, 60):
        raise AppError(ErrorCode.SYS_429, 429, "Too many requests. Try again later.")
    return await vote_on_answer(
        comment_id=comment_id,
        user_id=current_user["sub"],
        vote=req.vote,
    )


@router.get("/{post_id}/votes")
async def get_user_votes_endpoint(
    post_id: uuid.UUID,
    current_user: dict = Depends(require_role("SUPER_ADMIN", "ADMIN", "MEMBER", "GUEST")),
) -> list[dict]:
    """Get all votes by the current user on comments in a post."""
    return await get_user_votes(
        post_id=post_id,
        user_id=current_user["sub"],
    )

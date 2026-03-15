"""Service layer for Q&A features: best answer marking and voting."""

import uuid

from loguru import logger

from app.core.constants import RATE_LIMIT_VOTE
from app.core.database import get_pool
from app.core.errors import AppError, ErrorCode, ForbiddenError, NotFoundError
from app.core.event_bus import emit
from app.core.rate_limit import check_rate_limit
from app.repositories import vote_repo


async def mark_best_answer(
    pool: object,
    post_id: uuid.UUID,
    comment_id: str,
    user_id: str,
) -> dict:
    """Mark a comment as the best answer for a question post."""
    pool = get_pool()
    comment_uuid = uuid.UUID(comment_id)

    async with pool.acquire() as conn:
        async with conn.transaction():
            # Verify post exists and is a question
            post = await conn.fetchrow(
                "SELECT id, user_id, type, best_answer_id, title FROM posts "
                "WHERE id = $1 AND is_deleted = false FOR UPDATE",
                post_id,
            )
            if not post:
                raise AppError(ErrorCode.QA_003, 404, "Question not found.")
            if post["type"] != "question":
                raise AppError(ErrorCode.QA_003, 400, "This post is not a question.")
            if str(post["user_id"]) != user_id:
                raise AppError(
                    ErrorCode.QA_001, 403, "Only the question author can mark the best answer."
                )

            # Verify comment exists and belongs to this post
            comment = await conn.fetchrow(
                "SELECT id, user_id, post_id FROM comments "
                "WHERE id = $1 AND is_deleted = false",
                comment_uuid,
            )
            if not comment or comment["post_id"] != post_id:
                raise NotFoundError("Comment", comment_id)

            # Unmark previous best answer if any
            if post["best_answer_id"]:
                await conn.execute(
                    "UPDATE comments SET is_best_answer = false WHERE id = $1",
                    post["best_answer_id"],
                )

            # Mark new best answer
            await conn.execute(
                "UPDATE comments SET is_best_answer = true WHERE id = $1",
                comment_uuid,
            )
            await conn.execute(
                "UPDATE posts SET best_answer_id = $1 WHERE id = $2",
                comment_uuid,
                post_id,
            )

    # Emit event for notification
    try:
        pool2 = get_pool()
        async with pool2.acquire() as conn2:
            marker = await conn2.fetchrow(
                "SELECT display_name FROM users WHERE id = $1", uuid.UUID(user_id)
            )
        await emit(
            "best_answer.marked",
            post_id=str(post_id),
            answer_author_id=str(comment["user_id"]),
            question_title=post["title"],
            marker_name=marker["display_name"] if marker else "Someone",
        )
    except Exception as e:
        logger.warning(
            "Failed to emit best_answer.marked event",
            extra={"error": str(e), "post_id": str(post_id)},
        )

    return {"post_id": str(post_id), "best_answer_id": comment_id}


async def unmark_best_answer(
    pool: object,
    post_id: uuid.UUID,
    user_id: str,
) -> bool:
    """Unmark the best answer for a question post."""
    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            post = await conn.fetchrow(
                "SELECT id, user_id, best_answer_id FROM posts "
                "WHERE id = $1 AND is_deleted = false FOR UPDATE",
                post_id,
            )
            if not post:
                raise AppError(ErrorCode.QA_003, 404, "Question not found.")
            if str(post["user_id"]) != user_id:
                raise AppError(
                    ErrorCode.QA_001, 403, "Only the question author can unmark the best answer."
                )
            if not post["best_answer_id"]:
                return True  # Nothing to unmark

            await conn.execute(
                "UPDATE comments SET is_best_answer = false WHERE id = $1",
                post["best_answer_id"],
            )
            await conn.execute(
                "UPDATE posts SET best_answer_id = NULL WHERE id = $1",
                post_id,
            )
    return True


async def vote_on_answer(
    pool: object,
    comment_id: uuid.UUID,
    user_id: str,
    vote: int,
) -> dict:
    """Vote on an answer (upvote=1, downvote=-1, remove=0)."""
    pool = get_pool()

    # Rate limit check
    if not await check_rate_limit(f"rl:vote:{user_id}", *RATE_LIMIT_VOTE):
        raise AppError(ErrorCode.SYS_429, 429, "Too many votes. Please try again later.")

    async with pool.acquire() as conn:
        # Get comment and verify it belongs to a question post
        comment = await conn.fetchrow(
            """
            SELECT c.id, c.user_id, c.post_id, p.type AS post_type
            FROM comments c
            JOIN posts p ON c.post_id = p.id
            WHERE c.id = $1 AND c.is_deleted = false AND p.is_deleted = false
            """,
            comment_id,
        )
        if not comment:
            raise NotFoundError("Comment", str(comment_id))
        if comment["post_type"] != "question":
            raise AppError(ErrorCode.SYS_422, 400, "Voting is only available on question answers.")

        # Cannot vote on own answer
        if str(comment["user_id"]) == user_id:
            raise AppError(ErrorCode.QA_002, 400, "You cannot vote on your own answer.")

        async with conn.transaction():
            new_score = await vote_repo.upsert_vote(
                conn, comment_id, uuid.UUID(user_id), vote
            )

    return {
        "comment_id": str(comment_id),
        "vote_score": new_score,
        "your_vote": vote,
    }


async def get_user_votes(
    pool: object,
    post_id: uuid.UUID,
    user_id: str,
) -> list[dict]:
    """Get all votes by a user on comments in a post."""
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await vote_repo.get_user_votes_for_post(
            conn, post_id, uuid.UUID(user_id)
        )
    return [{"comment_id": str(r["comment_id"]), "vote": r["vote"]} for r in rows]

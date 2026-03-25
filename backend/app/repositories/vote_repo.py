import uuid
from typing import Any

from app.core.errors import AppError, ErrorCode


async def upsert_vote(conn: Any, comment_id: uuid.UUID, user_id: uuid.UUID, vote: int) -> int:
    """Atomic upsert of a vote and update of comment vote_score.

    If vote=0, removes the vote row and subtracts the old vote from score.
    Returns the new vote_score.
    Raises AppError if the comment does not exist.
    """
    if vote == 0:
        # Remove vote and adjust score atomically via CTE
        row = await conn.fetchrow(
            """
            WITH deleted AS (
                DELETE FROM comment_votes
                WHERE comment_id = $1 AND user_id = $2
                RETURNING vote
            )
            UPDATE comments SET vote_score = vote_score - COALESCE(
                (SELECT SUM(vote) FROM deleted), 0
            )
            WHERE id = $1
            RETURNING vote_score
            """,
            comment_id,
            user_id,
        )
        # L-03: If row is None, the UPDATE matched nothing — comment doesn't exist
        if row is None:
            exists = await conn.fetchval(
                "SELECT EXISTS(SELECT 1 FROM comments WHERE id = $1)",
                comment_id,
            )
            if not exists:
                raise AppError(ErrorCode.SYS_404, 404, "Comment not found.")
            return 0
        return row["vote_score"]

    # Upsert vote and update score atomically
    row = await conn.fetchrow(
        """
        WITH old AS (
            SELECT vote FROM comment_votes WHERE comment_id = $1 AND user_id = $2 FOR UPDATE
        ),
        upserted AS (
            INSERT INTO comment_votes (id, comment_id, user_id, vote)
            VALUES ($3, $1, $2, $4)
            ON CONFLICT (comment_id, user_id) DO UPDATE SET vote = $4
            RETURNING vote
        )
        UPDATE comments SET vote_score = vote_score + (
            $4 - COALESCE((SELECT vote FROM old), 0)
        )
        WHERE id = $1
        RETURNING vote_score
        """,
        comment_id,
        user_id,
        uuid.uuid4(),
        vote,
    )
    # L-03: If row is None, the UPDATE matched nothing — comment doesn't exist
    if row is None:
        exists = await conn.fetchval(
            "SELECT EXISTS(SELECT 1 FROM comments WHERE id = $1)",
            comment_id,
        )
        if not exists:
            raise AppError(ErrorCode.SYS_404, 404, "Comment not found.")
        return 0
    return row["vote_score"]


async def get_user_vote(conn: Any, comment_id: uuid.UUID, user_id: uuid.UUID) -> int | None:
    """Return the current vote value or None if no vote exists."""
    row = await conn.fetchrow(
        "SELECT vote FROM comment_votes WHERE comment_id = $1 AND user_id = $2",
        comment_id,
        user_id,
    )
    return row["vote"] if row else None


async def get_user_votes_for_post(conn: Any, post_id: uuid.UUID, user_id: uuid.UUID) -> list[dict]:
    """Return all votes by a user on comments in a given post."""
    rows = await conn.fetch(
        """
        SELECT cv.comment_id, cv.vote
        FROM comment_votes cv
        JOIN comments c ON cv.comment_id = c.id
        WHERE c.post_id = $1 AND cv.user_id = $2
        """,
        post_id,
        user_id,
    )
    return [dict(r) for r in rows]


async def delete_by_user_id(conn: Any, user_id: uuid.UUID) -> int:
    """Delete all votes by a user (GDPR cleanup)."""
    result = await conn.execute(
        "DELETE FROM comment_votes WHERE user_id = $1",
        user_id,
    )
    return int(result.split()[-1])
